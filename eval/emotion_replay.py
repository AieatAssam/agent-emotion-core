"""Replay targeted appraisals. Pass an engine .py path to compare an earlier version."""
import importlib.util
import sys
from pathlib import Path


def event(**kw):
    return dict(event='probe', relevance=1, novelty=0, congruence=0, **kw)

def outcome(congruence, **kw):
    return dict(event='probe', relevance=1, novelty=0, congruence=congruence, **kw)

fear = outcome(-1, control=0, certainty=0)
hope = outcome(1, certainty=0)
probes = {
    'joy': [outcome(1)],
    'distress': [outcome(-1, control=0)],
    'hope': [hope],
    'fear': [fear],
    'relief': [fear, outcome(1)],
    'disappointment': [hope, outcome(-1, control=0)],
    'pride': [event(agency='self', praiseworthiness=1)],
    'shame': [event(agency='self', praiseworthiness=-1)],
    'admiration': [event(agency='other', praiseworthiness=1, source='other')],
    'reproach': [event(agency='other', praiseworthiness=-1, source='other')],
    'gratitude': [outcome(1, agency='other', praiseworthiness=1, source='other')],
    'anger': [outcome(-1, agency='other', praiseworthiness=-1, source='other', control=1)],
    'interest': [dict(event='probe', relevance=1, novelty=1, control=1)],
    'boredom': [dict(event='probe', relevance=0, novelty=0, thread='same')],
    'surprise': [dict(event='probe', relevance=1, novelty=1, control=0)],
}



def peak(engine, name, events, traits, gap):
    core = engine.EmotionalCore("probe", persona={"traits": traits})
    maximum = 0.0
    for _ in range(1000):
        for appraisal in events:
            core.appraise(appraisal)
            maximum = max(maximum, core.intensity(name))
        core.advance(gap)
    return maximum


def main():
    default = Path(__file__).resolve().parents[1] / "skills/agent-emotion-core/scripts/affect_core.py"
    spec = importlib.util.spec_from_file_location("affect_core", sys.argv[1] if len(sys.argv) > 1 else default)
    engine = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(engine)
    high = dict.fromkeys("OCEAN", 1)
    print("emotion           targeted peak    contagion peak")
    for name in engine.EMOTIONS:
        targeted = max(peak(engine, name, probes[name], traits, gap)
                       for traits in ({}, high) for gap in (0, 1 / 60, 1))
        cue = event(perceived_emotion={"label": name, "intensity": 1})
        contagion = peak(engine, name, [cue], high, 0)
        print(f"{name:15} {targeted:15.9f} {contagion:17.9f}")


if __name__ == "__main__":
    main()
