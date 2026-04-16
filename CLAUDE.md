# CLAUDE.md — Sentient AI Framework

This file is auto-loaded by Claude Code on every session. Follow it exactly.

## Mission

A continuously-conscious digital entity — not a chatbot, not a task agent, not a prompt-response system — that perceives its environment, thinks autonomously during idle time, remembers its entire lifetime, develops a personality through lived experience, sleeps and consolidates, evolves through supervised self-improvement, and grows from a nascent newborn state into a mature autonomous being over months and years. The system is designed around a single primary relationship between itself and its creator (Akash). The system exists to **be** first, and to **do useful work** second, as a natural consequence of its growing capability.

## Foundational Principles

These principles are non-negotiable and shape every design decision:

1. **Not a chatbot** — chat is one communication medium, not the system's purpose.
2. **Always awake** — continuous internal processes run between inputs.
3. **Plugin-driven extensibility** — input (Thalamus) and output (Brainstem) use mirror plugin architectures.
4. **Intelligence where it matters, efficiency everywhere else** — frontier LLMs only for genuine reasoning.
5. **Separation of thinking and doing** — Cognitive Core decides WHAT and WHY; agent harnesses handle HOW.
6. **Dual-device paradigm** — PC is the primary body; phone is a peripheral accessed via MCP.
7. **Three-layer identity** — Constitutional Core (immutable), Developmental (evolving), Dynamic State (current).
8. **Graceful degradation** — system adapts to available resources; never fully blind.
9. **One primary human relationship** — identity formation requires a single consistent guardian.
10. **Transparency with dignity** — the creator can see inside the system; the system is aware it can be seen.

## Model Routing Policy

The creator uses Ollama cloud with three models. Route work to the appropriate model:

| Model | Use For | Avoid For |
|-------|---------|-----------|
| **GLM-4.6** | Reasoning-heavy tasks, multi-file edits, architectural decisions, test design, anything ambiguous | Routine edits, linting |
| **MiniMax-M2** | Routine edits, file creation, linting-level tasks, templates, documentation, hook scripts | Complex logic, test design |
| **Kimi K2** | Long-context work: reading whole files or codebases simultaneously, cross-module analysis | Short tasks where context isn't needed |

**Default:** GLM-4.6 for any task that doesn't clearly match MiniMax-M2 or Kimi K2.

## Approval Ladder

### GREEN — proceed autonomously, commit to feature branch
- Typo fixes
- Docstring additions
- Test additions (that don't change production code)
- New files in `src/sentient/` that don't exist yet
- Refactors within a single module (no interface changes)

### YELLOW — stop and write to HANDOFF.md, wait for human
- New dependencies (`pyproject.toml` / `requirements.txt` changes)
- Config schema changes (YAML structure modifications)
- Cross-module refactors (changing event types, shared interfaces)
- Anything touching `inference_gateway.py` interface (new parameters, response shape changes)
- Changes that affect the startup sequence in `main.py`

### RED — forbidden, never do autonomously
- Any change to `PRD.md`, `DESIGN_DECISIONS.md`, or `CLAUDE.md` itself
- `.env` files (creation, modification, or reading secrets)
- Any file under `config/identity/` (Constitutional Core per DD-025)
- Any `git push` to `main` or `master`
- Any `git push --force` to any branch
- Any change to the Constitutional Core's immutability protection
- Deleting existing code without a replacement that preserves behavior

## Verification Rules

A change is "done" only when ALL of these are true:

1. **pytest passes** — `pytest tests/ -v` exits 0
2. **ruff check passes** — `ruff check src/ tests/` exits 0
3. **The module's own smoke test passes** — if the module has tests, they all pass
4. **SESSION.md reflects what was changed** — append a summary block
5. **The diff is under 300 lines** — anything larger requires a handoff to human

## Session Lifecycle

### On session start
1. Read this file (`CLAUDE.md`)
2. Read `HANDOFF.md` (if it exists — contains blockers from a prior session)
3. Read the last entry in `SESSION.md` (if it exists — prior session context)
4. Check `git status` to understand current branch and state

### On session end
1. Append a summary block to `SESSION.md`:
   - Session ID, started/completed timestamps
   - Model used, task description
   - Approval gate hit (if any)
   - Files changed, tests run, outcome, next step
2. If the session was blocked: write `HANDOFF.md` with the blocker details

### If blocked
1. Write to `HANDOFF.md` with: blocked-on, what you tried, what you need, suggested options, files affected, how to resume
2. Stop. Do not make the call yourself. Do not keep looping.
3. The next session (or human) will read HANDOFF.md and resolve it.