"""Exercise the shell commands as distributed, in installations with spaces."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

from test_affect_core import CLI, INSULT

ROOT = Path(CLI).resolve().parents[3]
SKILL = ROOT / "skills" / "agent-emotion-core"
EVENTS = {
    "claude": ("UserPromptSubmit", "Stop", "last_assistant_message"),
    "codex": ("UserPromptSubmit", "Stop", "last_assistant_message"),
    "gemini": ("BeforeAgent", "AfterAgent", "prompt_response"),
}


class PackagedClientLifecycle(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="emotion integration ")
        self.addCleanup(directory.cleanup)
        self.base = Path(directory.name)
        self.project = self.base / "two word project"
        self.project.mkdir()
        self.package = self.base / "installed package"
        self.package.symlink_to(ROOT, target_is_directory=True)
        self.state_dir = self.base / "affect state"
        self.config = self.base / "claude config"

    def install_claude(self, directory):
        skills = directory / "skills"
        skills.mkdir(parents=True)
        (skills / SKILL.name).symlink_to(SKILL, target_is_directory=True)

    def invoke(self, host, event, *, agent=None, session="chat", **fields):
        env = {"PATH": os.environ["PATH"], "AFFECT_STATE_DIR": str(self.state_dir)}
        if agent:
            env["AFFECT_AGENT"] = agent
        if host == "claude":
            env.update(CLAUDE_PROJECT_DIR=str(self.project), CLAUDE_CONFIG_DIR=str(self.config))
            # The bundled frontmatter uses a YAML folded block for the shell command.
            frontmatter = (SKILL / "SKILL.md").read_text().split("---", 2)[1]
            pattern = rf"^  {event}:\n(?:    .*\n)*?          command: >-\n((?:            .+\n)+)"
            block = re.search(pattern, frontmatter, re.MULTILINE)
            self.assertIsNotNone(block, f"missing {event} command in SKILL.md")
            command = " ".join(line.strip() for line in block[1].splitlines())
        else:
            if host == "codex":
                manifest = json.loads((self.package / ".codex-plugin/plugin.json").read_text())
                hooks_file = self.package / manifest["hooks"]
                env["PLUGIN_ROOT"] = str(self.package)
            else:
                hooks_file = self.package / "hooks/hooks.json"
            hooks = json.loads(hooks_file.read_text())["hooks"]
            command = hooks[event][0]["hooks"][0]["command"]
            if host == "gemini":
                command = command.replace("${extensionPath}", str(self.package))
        data = {"hook_event_name": event, "session_id": session, **fields}
        result = subprocess.run(command, shell=True, cwd=self.project, env=env,
                                input=json.dumps(data), text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        if host == "claude":
            return result.stdout
        output = json.loads(result.stdout)
        if event == EVENTS[host][1]:
            self.assertEqual(output, {})
            return ""
        return output["hookSpecificOutput"]["additionalContext"]

    def state(self, agent):
        return json.loads((self.state_dir / (agent + ".json")).read_text())

    def test_next_prompt_remembers_appraisal_only_for_its_agent(self):
        self.install_claude(self.project / ".claude")
        for host, (start, end, reply_key) in EVENTS.items():
            with self.subTest(host=host):
                self.assertNotIn(INSULT["event"], self.invoke(host, start, prompt="first turn"))
                subprocess.run([sys.executable, CLI, "appraise", "--agent", host, "--state-dir",
                                str(self.state_dir), "--json", "-"], input=json.dumps(INSULT),
                               cwd=self.project, check=True, capture_output=True, text=True)
                self.invoke(host, end, **{reply_key: "I will check the proof."})
                next_prompt = self.invoke(host, start, prompt="continue")
                self.assertIn(INSULT["event"], next_prompt)
                self.assertIn("anger toward bob", next_prompt)
                self.assertIn("Attention cue:", next_prompt)
                self.invoke(host, end, **{reply_key: ""})
                self.assertEqual(len(self.state(host)["finished_turns"]), 2)
                self.assertAlmostEqual(self.state(host)["threads"]["chat"]["exposure"], 1, delta=.01)
                visitor = self.invoke(host, start, agent=host + "-visitor", prompt="continue")
                self.assertNotIn(INSULT["event"], visitor)
                self.assertNotIn("anger toward bob", visitor)

    def test_shared_persona_crosses_client_installations(self):
        self.install_claude(self.config)
        agent = "shared"
        self.invoke("gemini", "BeforeAgent", agent=agent)
        subprocess.run([sys.executable, CLI, "appraise", "--agent", agent, "--state-dir",
                        str(self.state_dir), "--json", "-"], input=json.dumps(INSULT),
                       check=True, capture_output=True, text=True)
        self.invoke("gemini", "AfterAgent", agent=agent, prompt_response="okay")
        for host in ("claude", "codex"):
            start, end, key = EVENTS[host]
            self.assertIn(INSULT["event"], self.invoke(host, start, agent=agent))
            self.invoke(host, end, agent=agent, **{key: "next response"})
        self.assertEqual(len(self.state(agent)["finished_turns"]), 3)
        self.assertLess(self.state(agent)["sentiments"]["agent:bob"]["L"], 0)

    def test_completed_reply_reaches_trusted_appraisal_plugin_and_next_prompt(self):
        self.install_claude(self.project / ".claude")
        plugin = self.base / "appraise outcome.py"
        plugin.write_text(
            "def register(core):\n"
            "    def appraise(core, turn):\n"
            "        if turn['message'] == 'Inspection passed.':\n"
            "            return {**turn, 'appraisals': [{'event': 'repair verified',\n"
            "                    'relevance': 1, 'congruence': 1}]}\n"
            "    core.on('pre_turn_update', appraise)\n")
        self.state_dir.mkdir()
        (self.state_dir / "config.json").write_text(json.dumps({"plugins": [str(plugin)]}))
        for host, (start, end, reply_key) in EVENTS.items():
            with self.subTest(host=host):
                first = self.invoke(host, start, prompt="Inspection passed.")
                self.assertNotIn("repair verified", first)
                for _ in range(2):
                    self.invoke(host, end, **{reply_key: "Inspection passed."})
                next_prompt = self.invoke(host, start)
                self.assertIn("repair verified", next_prompt)
                self.assertIn("joy", next_prompt)
                remembered = [m for m in self.state(host)["memory"] if m["event"] == "repair verified"]
                self.assertEqual(len(remembered), 1)

    def test_late_codex_stop_does_not_consume_the_next_turn(self):
        self.invoke("codex", "UserPromptSubmit", turn_id="one")
        self.invoke("codex", "Stop", turn_id="one", last_assistant_message="first reply")
        self.invoke("codex", "UserPromptSubmit", turn_id="two")
        self.invoke("codex", "Stop", turn_id="one", last_assistant_message="first reply")
        self.assertEqual(len(self.state("codex")["finished_turns"]), 1)
        self.invoke("codex", "Stop", turn_id="two", last_assistant_message="")
        self.assertEqual(len(self.state("codex")["finished_turns"]), 2)
        self.assertAlmostEqual(self.state("codex")["threads"]["chat"]["exposure"], 1, delta=.01)
