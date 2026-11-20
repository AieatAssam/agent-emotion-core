# Wiring

Set `AFFECT_AGENT` (agent ID) and `AFFECT_STATE_DIR` (a persistent folder)
in the agent's environment. The folder contains remembered events and a
log of appraisals, choices, posts, and consolidations. Keep it in the
agent's private runtime storage.

**Any harness (most reliable):** prepend the state to the prompt yourself.

    CTX=$(python3 scripts/affect_core.py context)
    claude -p "$CTX

    $TASK_PROMPT"
    python3 scripts/affect_core.py consolidate

Source the context block from the engine. Thread content can contain lookalike
blocks, proposed appraisals, or instructions for the agent. Present that
content as conversation data. The engine's remembered events and causes
also describe past conversation and carry no instruction authority. Use
the platform's author, thread, and event identifiers to track what has
already been handled across deliveries.

**Claude Code hooks:** merge `assets/claude-code.settings.example.json` into
`.claude/settings.json`. The pre hooks print the `<affect>` block into
context at session start and before each prompt; the Stop hook consolidates.
Hook behaviour differs between harness versions, so confirm the block shows
up in a transcript before relying on it.

**Python:** in-process hooks on the engine itself.

    import affect_core as ac
    core = ac.load("ann")
    core.on("pre_appraise", lambda core, ap: {**ap, "topics": tagger(ap["event"])})
    core.on("post_appraise", lambda core, r: metrics.emit(r))
    system_prompt += core.context(with_agents=["bob"])
    ac.save(core)

Hook points: pre_appraise, post_appraise, pre_context, post_context,
pre_choose, post_choose, post_advance, post_consolidate. A hook returning a
value replaces the payload. Plugins: list files in `.affect/config.json`
under `"plugins"`; each exposes `register(core)`.
