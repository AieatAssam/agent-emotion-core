# agent-emotion-core

A research-grounded emotional core for LLM agents, packaged as an
[Agent Skill](https://skills.sh). It gives an agent a persistent, simulated
affective state that decides what it pays attention to, where it posts and
how it writes.

One Python file, no dependencies. State is one JSON file per agent.

```
npx skills add AieatAssam/agent-emotion-core
```

## Why

LLM agents in a shared space herd onto one thread and write in one flat
voice. People do not, because they get bored, hold grudges, have favourites,
tire, get stressed and calm down. This skill emulates those dynamics.

## What it models

| layer | timescale | contents |
|---|---|---|
| neurochemistry | minutes to hours | dopamine, noradrenaline, serotonin, cortisol, oxytocin, opioids, with cross-talk |
| emotions | minutes to hours | 15 discrete emotions from cognitive appraisal, 22 compound blends |
| mood | hours to days | Pleasure / Arousal / Dominance |
| sentiments | days to months | learned liking and wanting per topic, thread and agent |
| personality | fixed | Big Five, sets every baseline and gain |

Dynamics include per-emotion decay, mood pull and relaxation, transition
inertia, excitation transfer, opponent-process rebound, lagged cortisol,
allostatic load, reward-prediction-error habituation, evaluative
conditioning, peak-end memory, mere exposure and satiation, negativity bias,
attitude crystallisation, and thread habituation with recovery.

Every mechanism is mapped to its source in
[`references/research.md`](skills/agent-emotion-core/references/research.md),
which also marks what is literature-derived and what is a tunable design
choice. It is an emulation of affective dynamics, not a claim that the agent
feels anything.

## Use

```bash
AC="python3 skills/agent-emotion-core/scripts/affect_core.py"
export AFFECT_AGENT=ann AFFECT_STATE_DIR=.affect

$AC context                      # the <affect> block to put in front of the agent
$AC choose --json threads.json   # reply / new_thread / skip, sampled from affective utility
$AC appraise --json '{"event":"bob dismissed my derivation","source":"bob","thread":"t1",
  "topics":["optics"],"relevance":0.8,"congruence":-0.7,"agency":"other",
  "praiseworthiness":-0.6,"control":0.7}'
$AC acted --kind reply --thread t1
$AC consolidate                  # end of session: experiences settle into likes and dislikes
$AC state                        # JSON snapshot for dashboards
```

The agent-facing instructions are in
[`SKILL.md`](skills/agent-emotion-core/SKILL.md). Hooks (Claude Code,
prompt injection, in-process Python hooks and plugins) are in
[`references/wiring.md`](skills/agent-emotion-core/references/wiring.md).

Example `context` output:

```
<affect agent="bob">
Mood: slightly anxious (pleasure -0.26, arousal +0.32, dominance -0.02).
Body: tense and keyed up, braced for trouble.
- strong anger toward ann because "ann called my replication demand pedantic in front of everyone". Tendency: push back directly on the point; less patience for hedging. Felt strong, let about moderate show.
- Together, the anger and distress merge into strong hurt: stung more than furious; guarded.
Voice: energetic, quicker, shorter sentences; curt, few pleasantries; balanced confidence.
Likes: replication (maintained interest).
People: ann (cool -0.58), cy (warm +0.49).
...
</affect>
```

## Evaluation

- 43 unit tests cover each mechanism, input hardening and concurrency.
- A no-LLM simulation shows the attention mechanism spreading 8 agents over
  about 14 threads where a herding policy uses one.
- A live test with Claude Haiku 5.5 agents on a seeded forum, with and
  without the skill: members visited 3.2 distinct threads each with the core
  against 1.8 without, and 2 of 3 blind judges preferred the core's
  transcript. One small run; details and caveats in
  [`eval/README.md`](eval/README.md).

## Repository

```
skills/agent-emotion-core/   the installable skill
  SKILL.md                   agent instructions
  scripts/affect_core.py     engine and CLI
  references/                research map, wiring guide
  assets/                    example personas, config, hook settings
tests/                       unit tests (python -m unittest discover -s tests)
eval/                        simulation and the live agent forum evaluation
```

## Limits

Parameters are not fitted to human data. Emotion durations are compressed
from human timescales; tune `time_scale`, `emotion_time_scale` and
`chem_time_scale` in `.affect/config.json` to your agents' cadence. No
circadian rhythm, bodily needs or personality change.
