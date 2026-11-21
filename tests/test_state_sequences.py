import random
import tempfile
import unittest

from test_affect_core import INSULT, PRAISE, ac, core


class StateSequences(unittest.TestCase):
    def test_all_emotions_fade_after_their_eliciting_event(self):
        # Drive each state through the public appraisal API, including prospect resolution.
        pending = {"event": "decision pending", "thread": "review", "relevance": 1,
                   "certainty": 0.2, "control": 0.1}
        decided = {"event": "decision announced", "thread": "review", "relevance": 1}
        scenarios = [
            ([PRAISE], ("joy", "admiration", "gratitude")),
            ([INSULT], ("anger", "distress", "reproach")),
            ([{**PRAISE, "agency": "self"}], ("pride",)),
            ([{**INSULT, "agency": "self"}], ("shame",)),
            ([{**pending, "congruence": -1}], ("fear",)),
            ([{**pending, "congruence": 1}], ("hope",)),
            ([{**pending, "congruence": -1}, {**decided, "congruence": 1}], ("relief",)),
            ([{**pending, "congruence": 1}, {**decided, "congruence": -1}], ("disappointment",)),
            ([{"event": "unexpected discovery", "novelty": 1, "control": 1}], ("surprise", "interest")),
            ([{"event": "routine paperwork", "novelty": 0, "relevance": 0}], ("boredom",)),
        ]
        covered = set()
        for events, emotions in scenarios:
            with self.subTest(emotions=emotions):
                agent = core()
                for event in events:
                    agent.appraise(event)
                covered.update(emotions)
                for hours in (0.25, 1, 2):
                    previous = {name: agent.intensity(name) for name in emotions}
                    agent.advance(hours)
                    for name in emotions:
                        current = agent.intensity(name)
                        self.assertLess(current, previous[name], name)
                        self.assertGreaterEqual(current, 0, name)
                agent.advance(24 * 30)
                for name in emotions:
                    self.assertEqual(agent.intensity(name), 0, name)
        self.assertEqual(covered, set(ac.EMOTIONS))

    def test_negative_history_changes_social_choice_after_anger_cools(self):
        agent = core({"E": -0.5, "N": 0.5})
        threads = [{"id": peer, "participants": [peer]} for peer in ("ann", "bob")]
        def probabilities():
            return agent.choose(threads, random.Random(7), allow_new=False, allow_skip=False)["probs"]

        before = probabilities()
        self.assertEqual(before["ann"], before["bob"])
        for day in range(5):
            for event in (INSULT, PRAISE):
                agent.appraise({**event, "event": f"{event['event']} on day {day}"})
            agent.consolidate()
            agent.advance(24)
        agent.advance(24 * 7)
        self.assertEqual(agent.intensity("anger"), 0)
        self.assertEqual(agent.intensity("gratitude"), 0)
        self.assertLess(agent.affinity("bob"), 0)
        self.assertGreater(agent.affinity("ann"), 0)
        after = probabilities()
        self.assertGreater(after["ann"], after["bob"])
        self.assertLess(after["bob"], before["bob"])

    def test_relationship_and_appraisal_trajectory_survive_disk_restart(self):
        agent = core()
        warmth = {**PRAISE, "relationship": {"type": "romantic", "affection": 1}}
        betrayal = {**INSULT, "source": "ann", "relationship": {"type": "romantic", "trust_violation": 1}}
        for turn in range(5):
            agent.finish_turn(str(turn), appraisals=[warmth])
            agent.advance(2)
        with tempfile.TemporaryDirectory() as directory:
            ac.save(agent, directory)
            resumed = ac.load(agent.s["agent"], directory)
        for state in (agent, resumed):
            state.finish_turn("broken promise", appraisals=[betrayal])
            state.advance(48)
            self.assertEqual(state.intensity("anger"), 0)
            self.assertIn("ann (loving/attached, guarded)", state.context(["ann"]))
            self.assertNotIn("Romantic relationship context", state.context(["bob"]))
        self.assertEqual(agent.summary(), resumed.summary())
        self.assertEqual(agent.context(["ann"]), resumed.context(["ann"]))

    def test_explicit_disaffection_reverses_attachment_without_erasing_guardedness(self):
        agent = core()
        def appraise(affection, violation=0):
            agent.appraise({"event": "relationship reassessment", "source": "ann", "relationship": {
                "type": "romantic", "affection": affection, "trust_violation": violation}})
            return agent.summary()["relationships"]["ann"]
        levels = [appraise(1)["affection"] for _ in range(8)]
        gains = [now - old for old, now in zip([0] + levels, levels)]
        self.assertTrue(all(0 < smaller < larger for larger, smaller in zip(gains, gains[1:])))
        guard = appraise(0, 1)["guardedness"]
        for _ in range(6):
            state = appraise(-1)
        self.assertLess(state["affection"], 0)
        self.assertEqual(state["guardedness"], guard)
        self.assertIn("ann (less affectionate, guarded)", agent.context(["ann"]))

    def test_equal_wording_preserves_distinct_encounters_and_refreshes_only_one(self):
        agent = core()
        event = {**INSULT, "event": "dismissed the proposal", "relevance": 1,
                 "praiseworthiness": -1, "congruence": -1}
        places = [("bob", "design"), ("ann", "design"), ("bob", "release")]
        for source, thread in places + [places[0]]:
            agent.appraise({**event, "source": source, "thread": thread})
            agent.advance(0.25)
        remembered = [item for item in agent.s["memory"] if item["event"] == event["event"]]
        self.assertCountEqual([(item["source"], item["thread"]) for item in remembered], places)
        latest = max(remembered, key=lambda item: item["t"])
        self.assertEqual((latest["source"], latest["thread"]), places[0])

    def test_inspiration_requires_interest_in_the_same_source(self):
        agent = core()
        agent.appraise({"event": "ann gave an admirable example", "thread": "work",
                        "source": "ann", "agency": "other", "praiseworthiness": 1,
                        "novelty": 0, "relevance": 1})
        discovery = {"event": "explained an unexpected technique", "thread": "work",
                     "novelty": 1, "control": 1, "relevance": 1}
        agent.appraise({**discovery, "source": "bob"})
        self.assertGreater(agent.intensity("admiration"), 0.25)
        self.assertGreater(agent.intensity("interest"), 0.25)
        self.assertNotIn("inspiration", agent.summary()["blends"])
        agent.appraise({**discovery, "source": "ann"})
        self.assertIn("inspiration", agent.summary()["blends"])
