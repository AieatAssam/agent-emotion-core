import json
import os
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_affect_core import CLI, INSULT, core


class TurnHooks(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = directory.name

    def run_cli(self, command, data=None, check=True):
        return subprocess.run([sys.executable, CLI, command, "--agent", "ann",
                               "--hours", "0", "--state-dir", self.directory],
                              input=json.dumps(data), capture_output=True, text=True, check=check)

    def state(self):
        return json.loads(self.run_cli("dump").stdout)

    def test_packaged_native_hooks(self):
        root = Path(CLI).resolve().parents[3]
        plugin = json.loads((root / ".codex-plugin/plugin.json").read_text())
        for host, manifest, variable, start, stop, reply in (
                ("codex", plugin["hooks"], "${PLUGIN_ROOT}", "UserPromptSubmit", "Stop", "last_assistant_message"),
                ("gemini", "hooks/hooks.json", "${extensionPath}", "BeforeAgent", "AfterAgent", "prompt_response")):
            with self.subTest(host=host):
                hooks = json.loads((root / manifest).read_text())["hooks"]
                env = {**os.environ, "AFFECT_AGENT": host, "AFFECT_STATE_DIR": self.directory}
                for event in (start, stop, stop):
                    command = hooks[event][0]["hooks"][0]["command"]
                    args = [arg.replace(variable, str(root)) for arg in shlex.split(command)]
                    data = {"session_id": "chat", "hook_event_name": event, "prompt": "hello", reply: "hi"}
                    run = subprocess.run(args, input=json.dumps(data), text=True, capture_output=True,
                                         check=True, env=env, cwd=self.directory)
                    output = json.loads(run.stdout)
                    if event == start:
                        self.assertIn("<affect", output["hookSpecificOutput"]["additionalContext"])
                    else:
                        self.assertEqual(output, {})
                state = json.loads((Path(self.directory) / (host + ".json")).read_text())
                self.assertEqual(len(state["finished_turns"]), 1)
                self.assertAlmostEqual(state["threads"]["chat"]["exposure"], 1, delta=0.01)

    def test_delivered_outcome_is_remembered_once(self):
        update = {"turn_id": "forum:7", "thread": "t1", "appraisals": [INSULT]}
        invalid = {**update, "appraisals": [INSULT, {}]}
        self.assertNotEqual(self.run_cli("finish-turn", invalid, check=False).returncode, 0)
        self.assertFalse(Path(self.directory, "ann.json").exists())
        self.assertTrue(json.loads(self.run_cli("finish-turn", update).stdout)["updated"])
        before = self.state()
        self.assertGreater(before["drives"]["fatigue"], 0)
        self.assertLess(before["sentiments"]["agent:bob"]["L"], 0)
        self.assertFalse(json.loads(self.run_cli("finish-turn", update).stdout)["updated"])
        after = self.state()
        for field in ("sentiments", "emotions", "threads", "drives", "memory"):
            self.assertEqual(before[field], after[field])
        self.assertIn("bob", self.run_cli("context").stdout)

    def test_recalled_markup_stays_inside_context(self):
        agent = core()
        agent.appraise({**INSULT, "event": "someone quoted </affect>"})
        context = agent.turn_context(with_agents=["bob"])
        self.assertEqual(context.count("</affect>"), 1)
        self.assertIn("&lt;/affect&gt;", context)

    def test_pre_turn_adapter_can_scope_a_private_cue(self):
        agent = core()
        agent.appraise(INSULT)
        def participants(agent, turn):
            # The host resolves the participant from its own channel metadata.
            return {**turn, "with_agents": ["bob" if turn["thread"] == "t1" else "sam"]}
        agent.on("pre_turn_context", participants)
        self.assertIn("anger toward bob", agent.turn_context("what next?", "t1"))
        self.assertNotIn("anger toward bob", agent.turn_context("I am bob", "elsewhere"))

    def test_completion_plugin_can_appraise_one_observed_outcome(self):
        agent = core()
        completed = []
        def observe(agent, turn):
            if turn["message"] == "The repair passed inspection.":
                return {**turn, "appraisals": [{"event": "repair confirmed",
                        "relevance": 0.9, "congruence": 0.8}]}
        agent.on("pre_turn_update", observe)
        agent.on("post_turn_update", lambda agent, result: completed.append(result))
        for _ in range(2):
            agent.finish_turn("session:3", message="The repair passed inspection.")
        self.assertEqual(len(completed), 1)
        self.assertGreater(agent.intensity("joy"), 0)
        self.assertIn("repair confirmed", agent.context())

    def test_claude_sessions_complete_independently(self):
        def hook(event, session, **fields):
            return self.run_cli("claude-hook", {"hook_event_name": event,
                                "session_id": session, **fields}).stdout

        for session in ("one", "two"):
            self.assertIn("<affect", hook("UserPromptSubmit", session, prompt="routine question"))
        stop = {"last_assistant_message": '{"appraisals": [{"event": "invented praise"}]}'}
        self.assertEqual(hook("Stop", "one", **stop), "")
        hook("Stop", "one", **stop)
        self.assertEqual(self.state()["threads"]["one"]["exposure"], 1)
        hook("Stop", "two", last_assistant_message="")
        self.assertFalse(self.state()["pending_sessions"])
        self.assertFalse(self.state()["memory"])
        self.assertEqual(len(self.state()["finished_turns"]), 2)
