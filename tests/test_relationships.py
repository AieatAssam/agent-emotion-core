import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "agent-emotion-core", "scripts"))
import affect_core as ac


class RelationshipAppraisals(unittest.TestCase):
    def core(self):
        return ac.EmotionalCore("me", persona={"traits": {k: 0 for k in ac.TRAITS}})

    def test_generic_positive_event_does_not_infer_romance(self):
        c = self.core()
        c.appraise({"event": "kind feedback", "source": "alex", "agency": "other",
                    "praiseworthiness": .8, "congruence": .8, "relevance": .9})
        self.assertNotIn("alex", c.s["relationships"])
        self.assertNotIn("Romantic relationship context", c.context(["alex"]))

    def test_explicit_romantic_appraisal_is_person_specific_and_guardedness_decays(self):
        c = self.core()
        c.appraise({"event": "repaired a broken promise", "source": "alex",
                    "relationship": {"type": "romantic", "affection": .9,
                                     "trust_violation": .8}})
        self.assertGreater(c.s["relationships"]["alex"]["affection"], .1)
        self.assertGreater(c.s["relationships"]["alex"]["guardedness"], .1)
        self.assertIn("Romantic relationship context: alex (affectionate, guarded)", c.context(["alex"]))
        self.assertNotIn("alex", c.context(["sam"]))
        self.assertNotIn("Romantic relationship context", c.context())
        for event in ("shared an old memory", "offered comfort", "made time together", "remembered our plans"):
            c.appraise({"event": event, "source": "alex",
                        "relationship": {"type": "romantic", "affection": .9}})
        self.assertIn("alex (loving/attached, guarded)", c.context(["alex"]))
        before = c.s["relationships"]["alex"]["guardedness"]
        c.advance(24 * 30)
        self.assertLess(c.s["relationships"]["alex"]["guardedness"], before)

    def test_inspiration_is_admiration_with_interest_toward_same_person(self):
        c = self.core()
        c.appraise({"event": "alex's elegant proof changed my view", "source": "alex",
                    "agency": "other", "praiseworthiness": .9, "congruence": .8,
                    "relevance": .9, "novelty": .9, "control": .9})
        labels = {item[0] for item in c.blends()}
        self.assertIn("inspiration", labels)


if __name__ == "__main__":
    unittest.main()
