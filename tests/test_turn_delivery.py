"""Exercise competing host deliveries against a single on-disk agent."""
import concurrent.futures
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_affect_core import CLI, INSULT, ac


class TurnDelivery(unittest.TestCase):
    @unittest.skipUnless(ac.fcntl, "multiple CLI writers require POSIX advisory locking")
    def test_concurrent_retries_match_one_delivery_in_every_persisted_layer(self):
        def deliver(directory):
            payload = {"turn_id": "chat:reply-31", "thread": "t1", "appraisals": [INSULT]}
            result = subprocess.run(
                [sys.executable, CLI, "finish-turn", "--agent", "ada",
                 "--state-dir", directory, "--hours", "0"],
                input=json.dumps(payload), capture_output=True, text=True, check=True)
            return json.loads(result.stdout)["updated"]

        def state(directory):
            result = json.loads(Path(directory, "ada.json").read_text())
            result.pop("wall")  # Subprocess launch times differ.
            return result

        with tempfile.TemporaryDirectory() as once, tempfile.TemporaryDirectory() as repeated:
            self.assertTrue(deliver(once))
            with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
                applied = list(pool.map(deliver, [repeated] * 8))
            self.assertEqual(applied.count(True), 1)
            self.assertEqual(state(repeated), state(once))


class EventReplay(unittest.TestCase):
    def test_duplicate_skips_callbacks_even_if_observer_reenters(self):
        agent = ac.EmotionalCore("ada")
        event = {**INSULT, "event_id": "t1:17"}
        callbacks = []
        def observe(agent, result):
            callbacks.append("after")
            if callbacks.count("after") == 1:
                agent.appraise(event)
        agent.on("pre_appraise", lambda agent, event: callbacks.append("before"))
        agent.on("post_appraise", observe)
        agent.appraise(event)
        agent.appraise(event)
        self.assertEqual(callbacks, ["before", "after"])
        self.assertEqual(agent.s["seen_event_ids"], ["t1:17"])

    def test_invalid_ids_rejected_before_any_event_in_the_turn_is_applied(self):
        agent = ac.EmotionalCore("ada")
        before = json.dumps(agent.s, sort_keys=True)
        for invalid in (None, 17, "  ", "x" * 129):
            with self.subTest(invalid=invalid), self.assertRaisesRegex(ValueError, "event_id"):
                agent.finish_turn("turn-2", appraisals=[INSULT, {**INSULT, "event_id": invalid}])
            self.assertEqual(json.dumps(agent.s, sort_keys=True), before)

    def test_persisted_replay_leaves_one_audit_record_and_compact_hook_prompt(self):
        with tempfile.TemporaryDirectory() as directory:
            def call(command, data, *options):
                return subprocess.run([sys.executable, CLI, command, "--agent", "ada",
                                       "--state-dir", directory, "--hours", "0", *options],
                                      input=json.dumps(data), capture_output=True,
                                      text=True, check=True).stdout
            event = {**INSULT, "event_id": "forum:1"}
            call("appraise", event)
            self.assertEqual(json.loads(call("appraise", event)), [{}])
            self.assertEqual(len(Path(directory, "ada.log.jsonl").read_text().splitlines()), 1)
            prompt = {"hook_event_name": "UserPromptSubmit", "session_id": "chat"}
            def context(*flags):
                output = json.loads(call("codex-hook", prompt, *flags))
                return output["hookSpecificOutput"]["additionalContext"]
            full, brief = context(), context("--brief")
            self.assertLess(len(brief), len(full))
            self.assertIn("anger toward bob", brief)
            self.assertIn(event["event"], brief)
            for cue in ("Attention cue:", "Tendency:", "Voice:", "pleasure "):
                self.assertIn(cue, full)
                self.assertNotIn(cue, brief)
