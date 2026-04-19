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
| **GLM-5.1** | Reasoning-heavy tasks, multi-file edits, architectural decisions, test design, anything ambiguous | Routine edits, linting |
| **MiniMax-M2.7** | Routine edits, file creation, linting-level tasks, templates, documentation, hook scripts | Complex logic, test design |
| **Kimi K2.5** | Long-context work: reading whole files or codebases simultaneously, cross-module analysis | Short tasks where context isn't needed |

**Default:** GLM-5.1 for any task that doesn't clearly match MiniMax-M2.7 or Kimi K2.5.

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
- Any change to `CLAUDE.md` itself without explicit creator authorization
- Any change to `PRD.md` or `DESIGN_DECISIONS.md`
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

### Verification Hierarchy Policy

Before a phase can be merged to main, it must pass ALL of these checks in order:

1. **Unit tests pass** — `pytest tests/unit -v` exits 0
2. **Integration tests pass** — `pytest tests/integration -v` exits 0
3. **Lint passes** — `ruff check src/ tests/` exits 0
4. **Live verification** (for any phase touching API or frontend):
   - Server starts without errors
   - Dashboard renders and WebSocket connects
   - Feature-specific event flow verified via Playwright or manual inspection
5. **No new test regressions** — any previously-passing test that now fails must be resolved or explicitly waived

If live verification requires a server restart with new code, document the gap and schedule a follow-up verification.

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

## Agent Orchestration

### Agent Roster and Tier Mapping

| Agent | Model | Role | Use For |
|-------|-------|------|---------|
| GLM-5.1 | glm-5.1:cloud | Architect, Planner, Critic | Reasoning-heavy tasks, multi-file edits, architectural decisions |
| Kimi-K2.5 | kimi-k2.5 | Writer, Explorer | Long-context work, documentation, cross-module analysis |
| MiniMax-M2.7 | minimax-m2.7 | Executor, Test Engineer | Routine edits, file creation, linting, test scaffolding |
| Gemma4 | gemma4:31b-cloud | UI Verifier | Browser automation via Playwright MCP, visual UI assertions, screenshot interpretation |

### UI Verification Agent

The `ui-verifier` agent uses Gemma4 (gemma4:31b-cloud) with Playwright MCP tools to visually verify the chat interface:
- Drives Playwright MCP tools: `browser_navigate`, `browser_click`, `browser_type`, `browser_take_screenshot`, `browser_evaluate`, `browser_wait_for`
- Uses vision capability to reason about UI state from screenshots
- NEVER edits source code (RED gate — violations require immediate phase restart)
- Produces findings reports: "Send button triggers network request: YES/NO", "Response renders in chat panel: YES/NO", "Recent Events populates: YES/NO"
- Always tears down browser sessions explicitly — no leaked Playwright contexts

### ORCHESTRATION — HARD RULES (RED gates)
1. The main Claude Code session MUST NOT edit production code (src/**) or test code (tests/**).
   All edits flow through dispatched agents via /team, /team ralph, or direct agent calls.
   If the main session edits code, this is a RED gate violation; stop and restart the phase.
2. Plans are files, not context. Every phase starts with /ralplan --deliberate writing to
   .omc/plans/ralplan-phase-N.md. Agents read the plan file; they do not receive the plan
   in their dispatch prompt.
3. Execution uses /team ralph N:executor with N ≤ 3 for parallel independent work, or
   /team ralph 1:executor for sequential work. team-fix handles test failures; the main
   session does not.
4. Every phase includes a documentation audit deliverable:
   a. explore reads SETUP.md, README.md, docs/, module READMEs against current code
   b. writer regenerates stale sections
   c. document-specialist verifies cross-references
   Documentation staleness is a phase-blocking gate, equivalent to failing CI.
5. notepad_write_priority holds: current phase number, current branch, active RED gates,
   InferenceGateway model label mapping (once fixed). Kept under 500 chars.
6. notepad_write_working is updated at each deliverable boundary by the orchestrator,
   not by agents.

### Branch Rules

- Phases branch from `main` after the previous phase is merged
- If the previous phase hasn't merged yet, branch from the previous phase tip
- Phase branch naming: `auto/phase-N-description`
- Never branch from an unmerged phase

### Merge Rules

- Every phase merges to `main` on green CI + architect approval
- Always use `--no-ff` for phase merges (preserves merge history)
- Tag each merged phase: `v0.N-milestone`
- Delete merged phase branches after merge

### Test Tiers

| Tier | Directory | Purpose | Runs By Default |
|------|-----------|---------|-----------------|
| Unit | `tests/unit/` | Fast, isolated, no I/O | Yes |
| Integration | `tests/integration/` | Multi-module with mocks | Yes |
| Wetware | `tests/wetware/` | Real LLM calls, requires Ollama | No (`pytest -m wetware`) |

## RESOURCE AND PROCESS RULES

### Lazy-import policy
Heavy dependencies (chromadb, sentence_transformers, litellm, torch, transformers) MUST be imported inside the function that uses them, not at module top level. Violations caught during review are a YELLOW gate.

### Pre-test RAM check (hard rule)
Any agent running `pytest` MUST first run:
    free -m | awk 'NR==2 {if ($7 < 4000) exit 1}'
If this check fails, the agent aborts with status "RAM_INSUFFICIENT" and notifies the orchestrator. No ulimit workarounds, no mid-run memory tricks.

### Coverage measurement
The command `pytest --cov=sentient` across the full codebase is BANNED. Coverage runs use `scripts/coverage_per_module.sh MODULE_NAME` one module at a time, and only in the phase close-out deliverable.

### Commit cadence
Every completed deliverable gets its own commit before the next deliverable starts. Use the existing safe_push.sh. If a deliverable fails, previous commits stay on the branch.

### Phase wall-clock budget
Every phase has an absolute budget set in its prompt. At 85% of budget, orchestrator forces close-out (write PHASE_N_PROGRESS.md, commit, push) regardless of deliverable state. No open-ended runs.

### Main session fix prohibition (restated)
If main session edits any file under src/ or tests/, RED gate, stop phase immediately, no exceptions.

## Resource Safety

### MUST check before any test run
1. NEVER run `pytest --cov=sentient` on all modules at once — it instruments every source file and can consume all RAM
2. For coverage, use per-module mode: `bash scripts/run_tests_safe.sh --cov sentient.api`
3. For quick verification (no coverage): `bash scripts/run_tests_safe.sh`
4. Max 3 parallel agents at any time — more causes RAM exhaustion

### How the safe runner works
- Checks available RAM before running; aborts if < 25% free
- For coverage, runs per-module instead of all-at-once to limit instrumentation overhead
- Location: `scripts/run_tests_safe.sh`

### Pre-Push Hook Contract

Before every push, the pre-push hook runs:
```bash
ruff check src/ tests/ && pytest -x --ff -q tests/unit tests/integration
```
Install: `bash scripts/install_hooks.sh`

### CI Feedback Contract

After every push:
1. `scripts/safe_push.sh` pushes and watches CI
2. If `gh` CLI is available, it monitors the workflow run
3. If CI fails, a debugger agent is dispatched to investigate
4. Manual fallback: check GitHub Actions UI directly