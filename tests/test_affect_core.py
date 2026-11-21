import json, os, random, subprocess, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "agent-emotion-core", "scripts"))
import affect_core as ac

FLAT = {k: 0 for k in ac.TRAITS}
CLI = os.path.join(os.path.dirname(__file__), "..", "skills", "agent-emotion-core", "scripts", "affect_core.py")


def core(traits=None, agent="a"):
    return ac.EmotionalCore(agent, persona={"traits": {**FLAT, **(traits or {})}})


INSULT = {"event": "bob called my proof sloppy", "source": "bob", "thread": "t1",
          "topics": ["proofs"], "relevance": 0.9, "congruence": -0.8, "agency": "other",
          "praiseworthiness": -0.8, "control": 0.8, "novelty": 0.5}
PRAISE = {"event": "ann built on my idea", "source": "ann", "thread": "t2",
          "topics": ["optics"], "relevance": 0.8, "congruence": 0.8, "agency": "other",
          "praiseworthiness": 0.7, "novelty": 0.5}
HUMILIATION = {"event": "public takedown I cannot answer", "source": "bob", "relevance": 1,
               "congruence": -1, "agency": "other", "praiseworthiness": -1, "control": 0.05}


class Emotions(unittest.TestCase):
    def test_baseline_mehrabian(self):
        b = ac.baseline_from_traits({**FLAT, "E": 1})
        self.assertAlmostEqual(b[0], 0.21); self.assertAlmostEqual(b[2], 0.60)

    def test_appraisal_rules(self):
        c = core(); out = c.appraise(INSULT)
        self.assertIn("anger", out); self.assertIn("reproach", out); self.assertNotIn("joy", out)
        self.assertLess(c.affinity("bob"), 0)
        c2 = core(); out2 = c2.appraise(PRAISE)
        self.assertIn("gratitude", out2); self.assertGreater(c2.affinity("ann"), 0)

    def test_low_control_gives_fear_not_anger(self):
        out = core().appraise({"event": "x", "relevance": .9, "congruence": -.8,
                               "certainty": .3, "control": .1})
        self.assertIn("fear", out); self.assertNotIn("anger", out)

    def test_half_life(self):
        c = core(); c.s["emotions"]["joy"] = {"i": 0.8, "target": None, "cause": ""}
        c.advance(4.0)
        self.assertAlmostEqual(c.intensity("joy"), 0.4, places=3)

    def test_step_size_invariance(self):
        a, b = core(), core()
        for x in (a, b): x.appraise(INSULT)
        a.advance(5.0)
        for _ in range(10): b.advance(0.5)
        self.assertAlmostEqual(a.intensity("anger"), b.intensity("anger"), places=2)
        for i in range(3):
            self.assertAlmostEqual(a.s["mood"][i], b.s["mood"][i], places=1)

    def test_mood_persists_then_recovers(self):
        c = core(); base = list(c.s["baseline"])
        for _ in range(3): c.appraise(INSULT)
        c.advance(2)
        self.assertLess(c.s["mood"][0], base[0] - 0.15)
        c.advance(24 * 30)
        self.assertAlmostEqual(c.s["mood"][0], base[0], places=1)
        self.assertEqual(c.s["emotions"], {})

    def test_neuroticism_amplifies_and_prolongs(self):
        lo, hi = core({"N": -0.8}), core({"N": 0.8})
        for x in (lo, hi): x.appraise(INSULT)
        r0 = hi.intensity("anger") / lo.intensity("anger")
        self.assertGreater(r0, 1)
        for x in (lo, hi): x.advance(3)
        self.assertGreater(hi.intensity("anger") / lo.intensity("anger"), r0)

    def test_contagion_scales_with_affinity(self):
        a, b = core(), core()
        a.s["sentiments"]["agent:z"] = {"L": 0.8, "W": 0, "n": 3, "ep": None}
        b.s["sentiments"]["agent:z"] = {"L": -0.8, "W": 0, "n": 3, "ep": None}
        ev = {"event": "z is thrilled", "source": "z", "relevance": 0, "novelty": 0,
              "perceived_emotion": {"label": "joy", "intensity": 0.9}}
        self.assertGreater(a.appraise(ev).get("joy", 0), b.appraise(ev).get("joy", 0))

    def test_relief(self):
        c = core()
        c.appraise({"event": "review pending", "relevance": .9, "congruence": -.8,
                    "certainty": .3, "control": .2})
        self.assertIn("relief", c.appraise({"event": "passed", "relevance": .9, "congruence": .8}))

    def test_blends(self):
        c = core()
        c.appraise({"event": "shipped it, but ann is leaving", "relevance": .9, "congruence": .9})
        c.s["emotions"]["distress"] = {"i": 0.5, "target": None, "cause": "ann is leaving"}
        self.assertEqual(c.blends()[0][0], "bittersweet")
        self.assertIn("bittersweet", c.context())
        d = core()
        d.appraise({"event": "result pending", "relevance": .9, "congruence": -.8,
                    "certainty": .3, "control": .2})
        d.appraise({"event": "early signs good", "relevance": .9, "congruence": .8, "certainty": .4})
        self.assertIn("suspense", [b[0] for b in d.blends()])

    def test_transition_inertia(self):
        calm, angry = core(), core()
        for _ in range(3): angry.appraise(INSULT)
        self.assertLess(angry.appraise(PRAISE)["joy"], calm.appraise(PRAISE)["joy"])


class Neurochemistry(unittest.TestCase):
    def test_cortisol_needs_uncontrollable_social_threat(self):
        hi, lo = core(), core()
        hi.appraise(HUMILIATION)
        lo.appraise({**HUMILIATION, "control": 0.95})
        for x in (hi, lo): x.advance(0.5)
        self.assertGreater(hi.dev("cort"), 0.2)
        self.assertGreater(hi.dev("cort"), 4 * max(lo.dev("cort"), 1e-9))

    def test_cortisol_peaks_late_then_clears(self):
        c = core(); c.appraise(HUMILIATION)
        at0 = c.dev("cort"); c.advance(0.5); peak = c.dev("cort")
        self.assertGreater(peak, at0 + 0.1)
        c.advance(12); self.assertLess(c.dev("cort"), 0.02)

    def test_reward_prediction_error_habituates(self):
        c = core(); bursts = []
        for _ in range(8):
            before = c.s["chem"]["da"]
            c.appraise({**PRAISE, "novelty": 0.0})
            bursts.append(c.s["chem"]["da"] - before)
            c.advance(12)
        self.assertGreater(bursts[0], 2 * bursts[-1])   # expected rewards stop exciting

    def test_low_serotonin_shortens_fuse(self):
        a, b = core(), core()
        b.s["chem"]["sht"] -= 0.3
        self.assertGreater(b.appraise(INSULT)["anger"], a.appraise(INSULT)["anger"])

    def test_excitation_transfer(self):
        a, b = core(), core()
        b.s["chem"]["ne"] += 0.4
        self.assertGreater(b.appraise(PRAISE)["joy"], a.appraise(PRAISE)["joy"])

    def test_oxytocin_buffers_stress(self):
        a, b = core(), core()
        b.s["chem"]["oxt"] += 0.4
        for x in (a, b): x.appraise(HUMILIATION)
        self.assertLess(b.s["stress"], a.s["stress"])

    def test_opponent_process_comedown(self):
        c = core(); base = c.s["baseline"][0]
        flat = ac.EmotionalCore("a", persona={"traits": FLAT}, config={"opponent_gain": 0})
        for x in (c, flat):
            for _ in range(4):
                x.appraise({"event": "win", "relevance": 1, "congruence": 1}); x.advance(1)
        self.assertGreater(c.s["opp"], 0.05)
        for x in (c, flat): x.advance(10)
        self.assertLess(c.s["mood"][0], flat.s["mood"][0] - 0.03)   # the comedown
        self.assertIn("comedown", c.context())
        c.advance(24 * 20)
        self.assertAlmostEqual(c.s["mood"][0], base, places=2)

    def test_relief_after_stress_ends(self):
        c = core()
        flat = ac.EmotionalCore("a", persona={"traits": FLAT}, config={"opponent_gain": 0})
        for x in (c, flat):
            for _ in range(4):
                x.appraise({"event": "loss", "relevance": 1, "congruence": -1, "control": 1})
                x.advance(1)
            x.advance(14)
        self.assertGreater(c.s["mood"][0], flat.s["mood"][0] + 0.02)

    def test_crosstalk(self):
        a = core(); a.s["chem"]["cort"] += 0.4; a.advance(0.5)
        self.assertGreater(a.dev("ne"), 0.03)            # stress raises arousal
        self.assertLess(a.dev("sht"), 0)                 # and erodes serotonin
        b, n = core(), core()
        for x in (b, n): x.s["chem"]["cort"] += 0.4
        b.s["chem"]["oxt"] += 0.4
        for x in (b, n): x.advance(1)
        self.assertLess(b.dev("cort"), n.dev("cort"))    # company clears stress faster
        o = core(); o.s["chem"]["opi"] += 0.4; o.advance(0.3)
        self.assertGreater(o.dev("da"), 0.01)            # pleasure feeds wanting

    def test_cocktails_read_as_combinations(self):
        c = core(); c.s["chem"]["cort"] += 0.3; c.s["chem"]["ne"] += 0.3
        self.assertIn("tense and keyed up", " ".join(c.body()))
        d = core(); d.s["chem"]["da"] += 0.3; d.s["chem"]["ne"] += 0.3
        self.assertIn("excited and driven", " ".join(d.body()))

    def test_chronic_stress_builds_load_and_sours_mood(self):
        c = core(); base = c.s["baseline"][0]
        for _ in range(14 * 4):
            c.appraise(HUMILIATION); c.advance(5)
        self.assertGreater(c.s["load"], 0.1)
        c.advance(24)                                    # a quiet day is not enough
        self.assertLess(c.s["mood"][0], base - 0.03)
        c.advance(24 * 60)
        self.assertLess(c.s["load"], 0.01)

    def test_lovheim_corner(self):
        c = core()
        for k, v in (("sht", -0.2), ("da", 0.2), ("ne", 0.2)): c.s["chem"][k] += v
        self.assertEqual(c.lovheim(), "anger/rage")


class EmotionalTrajectories(unittest.TestCase):
    def test_stronger_appraisals_have_diminishing_returns(self):
        win = {"event": "project succeeded", "relevance": 1, "novelty": 0}
        low, medium, high = [core({"E": 0.8}).appraise({**win, "congruence": strength})["joy"]
                             for strength in (0.5, 0.75, 1)]
        self.assertGreater(high, medium)
        self.assertGreater(medium - low, high - medium)
        self.assertLess(high, 1)

    def test_strong_anger_retains_more_of_its_peak_during_cooldown(self):
        mild, strong = core(), core()
        insult = {**INSULT, "relevance": 1, "control": 1, "novelty": 0}
        mild.appraise({**insult, "congruence": -0.5, "praiseworthiness": -0.5})
        strong.appraise({**insult, "congruence": -1, "praiseworthiness": -1})
        mild_peak, strong_peak = mild.intensity("anger"), strong.intensity("anger")
        self.assertGreater(strong_peak, mild_peak)
        for c in (mild, strong):
            c.advance(1)
        self.assertLess(strong.intensity("anger"), strong_peak)
        self.assertGreater(strong.intensity("anger") / strong_peak,
                           mild.intensity("anger") / mild_peak)

    def test_reminder_revives_anger_after_initial_cooldown(self):
        quiet, reminded = core(), core()
        for c in (quiet, reminded):
            c.appraise(INSULT)
            c.advance(3)
        before_reminder = reminded.intensity("anger")
        reminded.appraise({**INSULT, "event": "remembered bob calling my proof sloppy"})
        self.assertGreater(reminded.intensity("anger"), before_reminder)
        for c in (quiet, reminded):
            c.advance(3)
        self.assertLess(quiet.intensity("anger"), before_reminder)
        self.assertGreater(reminded.intensity("anger"), quiet.intensity("anger"))
        reminded.advance(24)
        self.assertEqual(reminded.intensity("anger"), 0)

    def test_repeated_small_wins_stay_proportional(self):
        small, major = core(), core()
        small_win = {"event": "a typo was fixed", "relevance": 0.4, "congruence": 0.3}
        major_win = {"event": "critical project succeeded", "relevance": 1, "congruence": 1}
        self.assertLess(small.appraise(small_win)["joy"], major.appraise(major_win)["joy"])
        for _ in range(39):
            small.appraise(small_win)
            major.appraise(major_win)
        self.assertLess(small.intensity("joy"), 0.5)
        self.assertGreater(major.intensity("joy"), small.intensity("joy") + 0.2)
        self.assertLess(major.intensity("joy"), 1)
        self.assertGreater(major.s["mood"][0], small.s["mood"][0] + 0.1)
        for c in (small, major):
            self.assertLess(max(abs(axis) for axis in c.s["mood"]), 1)

    def test_adaptation_survives_changed_event_identity_and_recovers_with_rest(self):
        c = core()
        first = c.appraise({"event": "first win", "source": "peer-0", "thread": "project-0",
                           "relevance": 1, "congruence": 1})["joy"]
        for i in range(1, 31):
            c.advance(1 / 60)
            repeated = c.appraise({"event": f"win {i}", "source": f"peer-{i}",
                                   "thread": f"project-{i}", "relevance": 1, "congruence": 1})["joy"]
        self.assertLess(repeated, 0.8 * first)
        c.advance(12)
        recovered = c.appraise({"event": "a win after rest", "source": "new-peer",
                               "thread": "new-project", "relevance": 1, "congruence": 1})["joy"]
        self.assertGreater(recovered, repeated + 0.15)
        self.assertAlmostEqual(recovered, first, delta=0.1)

    def test_adaptation_roundtrip_and_legacy_state(self):
        c = core()
        win = {"event": "project succeeded", "relevance": 1, "congruence": 1}
        for _ in range(20):
            c.appraise(win)
        with tempfile.TemporaryDirectory() as directory:
            ac.save(c, directory)
            reloaded = ac.load("a", directory)
            save_path = Path(directory, "a.json")
            legacy_state = json.loads(save_path.read_text())
            legacy_state.pop("emotion_adaptation")
            save_path.write_text(json.dumps(legacy_state))
            legacy = ac.load("a", directory)
        for agent in (c, reloaded, legacy):
            agent.advance(0.1)
        expected = c.appraise(win)["joy"]
        self.assertAlmostEqual(reloaded.appraise(win)["joy"], expected)
        self.assertGreater(legacy.appraise(win)["joy"], expected + 0.15)

    def test_burst_of_threats_has_bounded_stress_and_recovers(self):
        single, burst = core(), core()
        single.appraise(HUMILIATION)
        for _ in range(40):
            burst.appraise(HUMILIATION)
        self.assertLessEqual(burst.s["stress"], 1)
        self.assertAlmostEqual(burst.dev("cort"), 0)
        for c in (single, burst):
            c.advance(0.5)
        self.assertGreater(burst.dev("cort"), 0.2)
        self.assertLess(burst.dev("cort") - single.dev("cort"), 0.2)
        self.assertLess(burst.s["mood"][0], -0.1)
        burst.advance(24)
        self.assertLess(burst.dev("cort"), 0.1)
        burst.advance(24 * 30)
        self.assertEqual(burst.s["emotions"], {})
        for mood, baseline in zip(burst.s["mood"], burst.s["baseline"]):
            self.assertAlmostEqual(mood, baseline, places=2)

    def test_new_context_changes_outlook_without_erasing_history(self):
        c = core()
        for _ in range(10):
            c.appraise(INSULT)
        down = c.s["mood"][0]
        initial_anger = c.intensity("anger")
        self.assertLess(down, 0)
        peer_support = c.appraise(PRAISE)
        self.assertIn("gratitude", peer_support)
        self.assertGreater(c.intensity("anger"), 0)
        self.assertGreater(c.s["mood"][0], down)
        for _ in range(4):
            c.advance(1)
            c.appraise(PRAISE)
        self.assertGreater(c.intensity("joy"), c.intensity("anger"))
        self.assertLess(c.intensity("anger"), initial_anger)
        self.assertGreater(c.s["mood"][0], down)
        self.assertGreater(c.affinity("ann"), 0)
        self.assertLess(c.affinity("bob"), 0)

    def test_confirmation_resolves_fear_in_the_relevant_thread(self):
        c = core()
        c.appraise({"event": "review pending", "thread": "review", "relevance": 0.9,
                    "congruence": -0.8, "certainty": 0.3, "control": 0.2})
        positive = {"event": "passed", "relevance": 0.9, "congruence": 0.8}
        self.assertNotIn("relief", c.appraise({**positive, "thread": "unrelated"}))
        lingering_fear = c.intensity("fear")
        self.assertGreater(lingering_fear, 0.3)
        self.assertIn("relief", c.appraise({**positive, "thread": "review"}))
        self.assertLess(c.intensity("fear"), lingering_fear)

    def test_blends_follow_threads_and_targets(self):
        prospect = {"relevance": 0.9, "certainty": 0.3, "control": 0.2}
        fear = {**prospect, "event": "review may fail", "thread": "review", "congruence": -0.8}
        for thread, expected_blend in (("review", True), ("unrelated", False)):
            with self.subTest(thread=thread):
                c = core()
                c.appraise(fear)
                c.appraise({**prospect, "event": "early signs good", "thread": thread, "congruence": 0.8})
                self.assertGreater(c.intensity("fear"), 0.3)
                self.assertGreater(c.intensity("hope"), 0.3)
                self.assertEqual(any(blend[0] == "suspense" for blend in c.blends()), expected_blend)

        c = core()
        c.appraise(PRAISE)
        self.assertIn("affection", [blend[0] for blend in c.blends()])
        c.appraise({"event": "impressive proof", "source": "bob", "relevance": 1,
                    "agency": "other", "praiseworthiness": 1})
        self.assertEqual(c.s["emotions"]["admiration"]["target"], "bob")
        self.assertEqual(c.s["emotions"]["gratitude"]["target"], "ann")
        self.assertNotIn("affection", [blend[0] for blend in c.blends()])

    def test_directed_tendencies_follow_the_current_company(self):
        c = core()
        c.appraise(PRAISE)
        self.assertIn("toward ann", c.context(["ann"]))
        self.assertNotIn("toward ann", c.context(["kai"]))
        self.assertNotIn("merge into", "\n".join(line for line in c.context(["kai"]).splitlines()
                                                 if "gratitude" in line or "admiration" in line))
        self.assertIn("toward ann", c.context())


class Sentiments(unittest.TestCase):
    def day(self, c, ev, n=1):
        for _ in range(n): c.appraise(ev)
        c.advance(12)                                    # sleep gap consolidates

    def test_likes_develop_and_phase_advances(self):
        c = core(); seen = []
        for _ in range(14):
            self.day(c, PRAISE, 2); seen.append(c.interest_phase("topic:optics"))
        L = c.s["sentiments"]["topic:optics"]["L"]
        self.assertGreater(L, 0.5)
        self.assertEqual(seen[-1], "well-developed interest")
        self.assertIn("maintained interest", seen)
        self.assertGreater(c.affinity("ann"), 0.4)
        self.assertIn("optics", c.context())

    def test_negativity_bias(self):
        g, b = core(), core()
        self.day(g, {"event": "e", "topics": ["x"], "relevance": .8, "congruence": .8, "novelty": 0})
        self.day(b, {"event": "e", "topics": ["x"], "relevance": .8, "congruence": -.8,
                     "novelty": 0, "control": 0})
        self.assertGreater(-b.liking("topic:x"), g.liking("topic:x"))

    def test_attitudes_crystallise(self):
        fresh, old = core(), core()
        for _ in range(15): self.day(old, PRAISE)
        bad = {**PRAISE, "congruence": -.8, "praiseworthiness": -.7}
        before = old.liking("topic:optics")
        self.day(fresh, PRAISE); f0 = fresh.liking("topic:optics")
        self.day(old, bad); self.day(fresh, bad)
        self.assertLess(before - old.liking("topic:optics"), f0 - fresh.liking("topic:optics"))

    def test_peak_end_rule(self):
        good = {"event": "e", "topics": ["x"], "relevance": .9, "congruence": .9}
        bad = {"event": "e", "topics": ["x"], "relevance": .9, "congruence": -.9, "control": 1}
        a, b = core(), core()                            # same events, different order
        for ev in (bad, good, good): a.appraise(ev); a.s["emotions"].clear()
        for ev in (good, good, bad): b.appraise(ev); b.s["emotions"].clear()
        self.assertGreater(a.liking("topic:x"), b.liking("topic:x"))

    def test_mere_exposure_then_satiation(self):
        neutral = {"event": "saw it", "topics": ["x"], "relevance": 1.0, "novelty": 0.0}
        c = core()
        for _ in range(5): self.day(c, neutral)
        self.assertGreater(c.s["sentiments"]["topic:x"]["L"], 0.05)
        m = core()
        for _ in range(5): self.day(m, neutral, 14)      # massed over-exposure
        self.assertLess(m.s["sentiments"]["topic:x"]["L"], c.s["sentiments"]["topic:x"]["L"])

    def test_evaluative_conditioning_by_association(self):
        c = core()
        for _ in range(4):
            self.day(c, {"event": "great result while dee was around", "source": "dee",
                         "relevance": .9, "congruence": .9})
        self.assertGreater(c.affinity("dee"), 0.05)

    def test_wanting_dissociates_from_liking(self):
        c = core()
        for _ in range(6): self.day(c, {**PRAISE, "thread": "hot"}, 2)
        self.assertGreater(c.wanting("thread:hot"), 0.4)
        for _ in range(4): self.day(c, {**INSULT, "thread": "hot"}, 2)
        self.assertLess(c.liking("thread:hot"), 0.1)
        self.assertGreater(c.wanting("thread:hot"), 0.1)

    def test_grudges_outlast_goodwill(self):
        c = core()
        c.s["sentiments"] = {"agent:x": {"L": .5, "W": 0, "n": 1, "ep": None},
                             "agent:y": {"L": -.5, "W": 0, "n": 1, "ep": None}}
        c.advance(24 * 90)
        self.assertGreater(abs(c.affinity("y")), abs(c.affinity("x")))
        self.assertLess(abs(c.affinity("x")), 0.5)


class Behaviour(unittest.TestCase):
    def test_habituation_moves_attention(self):
        c = core(); rng = random.Random(1)
        ths = [{"id": "big", "recent_posts": 60, "topic_match": .7},
               {"id": "small", "recent_posts": 2, "topic_match": .7}]
        p0 = c.choose(ths, rng)["probs"]["big"]
        for _ in range(5): c.acted("reply", "big")
        p1 = c.choose(ths, rng)["probs"]["big"]
        self.assertLess(p1, p0 * 0.5)
        c.advance(72)
        self.assertGreater(c.choose(ths, rng)["probs"]["big"], p1)

    def test_learned_taste_steers_choice(self):
        c = core()
        for _ in range(8):
            c.appraise(PRAISE); c.advance(12)
        ths = [{"id": "a", "tags": ["optics"]}, {"id": "b", "tags": ["tax"]}]
        p = c.choose(ths)["probs"]
        self.assertGreater(p["a"], p["b"])

    def test_fatigue_and_stress_raise_skip(self):
        c = core(); ths = [{"id": "t", "topic_match": .6}]
        p0 = c.choose(ths)["probs"]["skip"]
        for _ in range(6): c.acted("reply", "other")
        self.assertGreater(c.choose(ths)["probs"]["skip"], p0)
        s = core(); s.s["chem"]["cort"] += 0.4
        self.assertGreater(s.choose(ths)["probs"]["skip"], p0)

    def test_hooks(self):
        c = core(); seen = []
        c.on("pre_appraise", lambda core, ap: {**ap, "relevance": 0.0, "novelty": 1.0})
        c.on("post_appraise", lambda core, r: seen.append(r))
        self.assertNotIn("anger", c.appraise(INSULT)); self.assertEqual(len(seen), 1)

    def test_fuzz_bounds_and_context(self):
        c = core({"C": .8, "A": .8}); rng = random.Random(0)
        for _ in range(400):
            c.appraise({"event": "e", "source": rng.choice("pqr"), "thread": rng.choice("12"),
                        "topics": [rng.choice("xyz")],
                        "relevance": rng.random(), "congruence": rng.uniform(-1, 1),
                        "novelty": rng.random(),
                        "agency": rng.choice(["self", "other", "circumstance"]),
                        "praiseworthiness": rng.uniform(-1, 1), "control": rng.random(),
                        "certainty": rng.random()})
            c.advance(rng.random() * 8)
            self.assertTrue(all(-1 <= x <= 1 for x in c.s["mood"]))
            self.assertTrue(all(0 <= e["i"] <= 1 for e in c.s["emotions"].values()))
            self.assertTrue(all(0 <= v <= 1 for v in c.s["chem"].values()))
            self.assertTrue(all(-1 <= r["L"] <= 1 and 0 <= r["W"] <= 1
                                for r in c.s["sentiments"].values()))
        txt = c.context()
        self.assertTrue(txt.startswith("<affect") and txt.endswith("</affect>"))
        json.dumps(c.summary())

    def test_cli_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            def run(*a, hours="0", **k):
                return subprocess.run(
                    [sys.executable, CLI, *a, "--agent", "kim", "--state-dir", d, "--hours", hours],
                    capture_output=True, text=True, check=True, **k).stdout
            run("init")
            run("appraise", "--json", "-", input=json.dumps(INSULT))
            self.assertIn("bob", run("context"))
            dec = json.loads(run("choose", "--json", json.dumps([{"id": "t1"}, {"id": "t9"}])))
            self.assertIn(dec["action"], ("reply", "new_thread", "skip"))
            run("acted", "--thread", "t9")
            self.assertIn("agent:bob", json.loads(run("consolidate")))
            st = json.loads(run("state", hours="1"))
            self.assertLess(st["sentiments"]["agent:bob"]["liking"], 0)
            self.assertEqual(len(Path(d, "kim.log.jsonl").read_text().splitlines()), 4)


class Hardening(unittest.TestCase):
    def cli(self, d, *a, agent="kim", stdin=None):
        return subprocess.run([sys.executable, CLI, *a, "--agent", agent, "--state-dir", d,
                               "--hours", "0"], capture_output=True, text=True, input=stdin)

    def test_bad_input_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as d:
            for args in (("appraise", "--json", '{"event":"x",'),
                         ("appraise", "--json", "{}"),
                         ("appraise", "--json", '{"event":null}'),
                         ("appraise", "--json", "[1,2]"),
                         ("choose", "--json", '{"id":"t1"}'),
                         ("init", "--persona", '{"traits":{"charisma":1}}')):
                r = self.cli(d, *args)
                self.assertNotEqual(r.returncode, 0, args)
                self.assertNotIn("Traceback", r.stderr, args)
                self.assertIn("affect_core", r.stderr, args)
            for agent in ("../escape", "team/alpha", "bad id", ".hidden", ""):
                r = self.cli(d, "state", agent=agent)
                self.assertNotEqual(r.returncode, 0, agent)
                self.assertNotIn("Traceback", r.stderr, agent)
            self.assertFalse(Path(d, "..", "escape.json").exists())
            r = subprocess.run([sys.executable, CLI, "tick", "--agent", "kim", "--state-dir", d,
                                "--hours", "-5"], capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0)

    def test_sloppy_input_is_tolerated(self):
        c = core()
        c.appraise({"event": "x", "relevance": "high", "congruence": None, "novelty": 99,
                    "agency": "aliens", "perceived_emotion": "anger", "topics": "optics",
                    "control": float("nan"), "certainty": float("inf")})
        c.appraise({"event": "y", "topics": [{"a": 1}, 7, "  Optics "], "source": 12,
                    "perceived_emotion": {"label": "smugness", "intensity": "lots"}})
        self.assertEqual([k for k in c.s["sentiments"] if k.startswith("topic:")], ["topic:optics"])
        dec = c.choose([None, {"title": "no id"}, {"id": "a", "recent_posts": "many", "tags": "x"},
                        {"id": "a"}, {"id": "b", "recent_posts": -50, "last_activity_hours": -3,
                                      "participants": [None, 3]}])
        self.assertEqual(set(dec["probs"]), {"a", "b", "new_thread", "skip"})
        self.assertLess(dec["probs"]["b"], 0.9)
        self.assertEqual(c.choose([])["action"] in ("new_thread", "skip"), True)

    def test_trait_names_and_self_source(self):
        c = ac.EmotionalCore("me", persona={"traits": {"openness": 0.9, "Neuroticism": "0.5", "e": "loud"}})
        self.assertEqual((c.traits["O"], c.traits["N"], c.traits["E"]), (0.9, 0.5, 0.0))
        c.appraise({"event": "my own post went well", "source": "me", "agency": "self",
                    "praiseworthiness": .8, "relevance": .8, "congruence": .8})
        self.assertNotIn("agent:me", c.s["sentiments"])
        self.assertIsNone(c.s["emotions"]["pride"]["target"])

    def test_no_boredom_while_moved_and_no_ceiling_pinning(self):
        c = core({"N": .9})
        for _ in range(8):
            out = c.appraise({**INSULT, "novelty": 0.0})
        self.assertLess(out.get("boredom", 0), 0.15)
        self.assertLess(max(out.values()), 1.0)
        self.assertNotIn("boredom toward", c.context())

    def test_first_impression_is_not_yet_a_taste(self):
        c = core(); c.appraise({"event": "meh", "topics": ["x"], "relevance": .5, "congruence": -.4})
        self.assertNotIn("Dislikes", c.context())

    def test_parallel_writes_are_not_lost(self):
        with tempfile.TemporaryDirectory() as d:
            ev = json.dumps({"event": "nice", "topics": ["same"], "relevance": .8, "congruence": .8})
            ps = [subprocess.Popen([sys.executable, CLI, "appraise", "--json", ev, "--agent", "kim",
                                    "--state-dir", d, "--hours", "0"], stdout=subprocess.DEVNULL)
                  for _ in range(12)]
            self.assertTrue(all(p.wait() == 0 for p in ps))
            st = json.loads(self.cli(d, "dump").stdout)
            self.assertEqual(st["sentiments"]["topic:same"]["ep"]["k"], 12)


if __name__ == "__main__":
    unittest.main()
