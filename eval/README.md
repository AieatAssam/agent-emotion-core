# Evaluation

Two checks. Neither is a validation against human data.

## 1. Mechanism simulation (`sim.py`, no LLM)

8 synthetic agents, 60 rounds, 5 seeds. A herding policy (always reply where
activity x topic fit is highest) is compared with the core's `choose()`.

| policy | threads used | top-thread share | normalised entropy |
|---|---|---|---|
| herd | 1 | 1.00 | 0.00 |
| core | ~14 | 0.12 | 0.94 |

Run: `python eval/sim.py`

## 2. Live agents on a test forum (Claude Haiku 5.5)

Five personas (`personas.json`) visit a seeded five-thread forum (`forum.py`)
four times over two simulated days. Each visit is a fresh Haiku 5.5 agent
with no memory of earlier visits. Control agents get the persona and forum
only. Treatment agents also get this skill, installed, and follow
`SKILL.md`. Prompts: `prompts.py`. One run per condition, 0 to 2 posts per
visit.

| | control | with core |
|---|---|---|
| posts | 19 | 20 |
| posts in the seeded megathread (t1) | 7 | 3 |
| top-thread share | 0.37 | 0.30 |
| thread entropy (normalised) | 0.86 | 0.96 |
| distinct threads visited per member (mean of 5) | 1.8 | 3.2 |
| core commands that failed (agent-reported, 20 visits) | n/a | 0 |
| `choose` decisions followed | n/a | 20 of 20 |

Without the core, members with distinct personas did not all pile into one
thread; they each stayed in their own lane and repeated themselves (three of
five posted in a single thread all four visits). With the core they moved
between threads and carried ideas across them.

Blind judging: four Haiku 5.5 judges read both transcripts labelled X and Y
(assignment alternated). Three returned a verdict. Scores are 1 to 5.

| criterion | control | with core |
|---|---|---|
| emotional realism | 3.33 | 3.67 |
| distinct voices | 3.00 | 3.67 |
| continuity across visits | 3.33 | 4.00 |
| natural attention | 3.00 | 4.00 |
| overall preference (3 judges) | 1 | 2 |
| per-member preference (15 calls) | 2 | 8 (5 ties) |

Read this as: the plumbing works with a small model, attention spreads, and
judges lean toward the core. It is one run of 20 posts per condition with
three judges from the same model family, so the differences are not
statistically established. Emotional expression in the text stayed mild in
both conditions; Haiku writes politely either way.

Also run with Haiku 5.5:

- A cold-read usability and abuse audit (about 60 commands). It found 12
  defects in v0.2.0: tracebacks on malformed input, a path traversal through
  the agent id, lost updates under parallel writes, character-split topics,
  silently ignored persona keys. All are fixed and covered by
  `tests/test_affect_core.py` (`Hardening`). Its three behavioural checks
  passed: emotions fade over time, repeated good experiences produce liking,
  liked topics attract `choose`.
- A ten-vignette appraisal test: the agent wrote appraisals from `SKILL.md`
  alone. By its own rating the returned emotions fit in 5 cases and partly
  in 5. Fixes that followed: stronger contagion, soft saturation instead of
  a hard ceiling, boredom no longer co-occurring with strong emotion, and
  clearer field definitions.
- A pilot first round on v0.2.0 exposed runaway boredom from per-post
  habituation and emotions wrongly directed at people. Fixed in v0.2.1; the
  treatment condition was rerun from scratch on v0.2.1.

`results/` holds both forum files, every agent's affect log and final state,
the judging inputs and verdicts, and the discarded pilot round.

Reproduce: seed with `forum.py seed`, run agents with the prompts from
`prompts.py`, move time with `advance.sh ROUND HOURS [consolidate]`.
