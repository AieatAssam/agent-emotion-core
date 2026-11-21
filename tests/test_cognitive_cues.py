import unittest

from test_affect_core import INSULT, ac, core


class CognitiveCues(unittest.TestCase):
    def test_each_supported_emotion_has_a_distinct_private_cue(self):
        self.assertEqual(ac.COGNITIVE_CUES.keys(), ac.EMOTIONS.keys())
        self.assertEqual(len(set(ac.COGNITIVE_CUES.values())), len(ac.EMOTIONS))
        for emotion, cue in ac.COGNITIVE_CUES.items():
            with self.subTest(emotion=emotion):
                affect = core()
                affect.s["emotions"][emotion] = {"i": 0.8, "target": None, "cause": ""}
                context = affect.context()
                self.assertIn("Attention cues are private.", context)
                self.assertIn(f"Attention cue: {cue}.", context)

    def test_cue_follows_the_emotion_and_its_cause(self):
        affect = core()
        affect.appraise(INSULT)
        line = next(line for line in affect.context(["bob"]).splitlines() if " anger " in line)
        self.assertIn(INSULT["event"], line)
        self.assertIn("the apparent obstacle and who seems responsible", line)
        self.assertNotIn(ac.COGNITIVE_CUES["anger"], affect.context(["ann"]))
        self.assertNotIn("Attention cue:", affect.context(["bob"], max_emotions=0))

    def test_weak_emotion_does_not_supply_a_cue(self):
        affect = core()
        affect.s["emotions"]["fear"] = {"i": 0.14, "target": None, "cause": ""}
        self.assertNotIn("Attention cue", affect.context())
