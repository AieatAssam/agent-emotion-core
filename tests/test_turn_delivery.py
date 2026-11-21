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
