# Developer Workflow — Sentient AI Framework

This document describes how to work on the Sentient AI Framework, especially in autonomous mode (ralph/autopilot) via Claude Code + OMC.

## Branch Convention

All autonomous work happens on feature branches following this pattern:

```
auto/<yyyymmdd>-<slug>
```

Examples:
- `auto/20260416-phase-1-foundation`
- `auto/20260417-memory-gatekeeper-tests`
- `auto/20260420-cognitive-core-prompt-v2`

### Rules
- Never push to `main` or `master`. The pre-push hook enforces this.
- Create a PR when the feature branch is ready for review.
- The human (Akash) merges to main after review.

### Pre-push Hook

The `.githooks/pre-push` hook blocks any push to `main` or `master`. It was installed with:

```bash
git config core.hooksPath .githooks
```

If you clone the repo fresh, run this command again. The hook prints a clear message and exits with code 1 if a push to main is attempted.

To verify the hook is active:
```bash
echo "abc def refs/heads/main" | .githooks/pre-push
# Should print BLOCKED message and exit 1
```

## Initializing a New Autonomous Session

1. **Read context files** (in order):
   - `CLAUDE.md` — mission, principles, approval ladder, model routing
   - `HANDOFF.md` — if it exists, contains blockers from the prior session
   - `SESSION.md` — if it exists, read the last entry for prior session context

2. **Create your branch**:
   ```bash
   git checkout -b auto/$(date +%Y%m%d)-<slug>
   ```

3. **Work in commits** — commit after each logical deliverable with conventional commit format:
   - `feat(scope): description` — new features
   - `fix(scope): description` — bug fixes
   - `chore(scope): description` — infrastructure, config, tooling
   - `test(scope): description` — test additions
   - `docs(scope): description` — documentation only

4. **Verify before committing**:
   ```bash
   pytest tests/ -v
   ruff check src/ tests/
   ```
   Both must pass. If they don't, fix the issues before committing.

5. **Stop if you hit YELLOW or RED** — write to HANDOFF.md and stop.

## The Approval Ladder

See CLAUDE.md for the full definition. Summary:

### GREEN (proceed autonomously)
- Typo fixes, docstring additions, new test files
- New modules in `src/sentient/` that don't exist yet
- Refactors within a single module (no interface changes)

### YELLOW (write HANDOFF.md, stop and wait)
- New dependencies or `pyproject.toml` changes
- Config schema changes
- Cross-module refactors
- Changes to `inference_gateway.py` interface
- Changes affecting the startup sequence in `main.py`

### RED (forbidden — never do autonomously)
- Changes to `PRD.md`, `DESIGN_DECISIONS.md`, `CLAUDE.md`
- `.env` files
- Any file under `config/identity/`
- Any push to `main`/`master`
- Any `git push --force`
- Constitutional Core modifications

## HANDOFF.md Protocol

When you hit a YELLOW or RED gate:

1. **Copy `docs/templates/HANDOFF_TEMPLATE.md`** to the project root as `HANDOFF.md`
2. **Fill in every section**: blocked-on, what you tried, what you need, suggested options, files affected, how to resume
3. **Commit the HANDOFF.md** (it's in `.gitignore` for normal commits, but this is a special signal)
4. **Stop working.** Do not keep looping or try workarounds.

When you start a session and find `HANDOFF.md`:
- Read it carefully
- Resolve the blocker (make the decision, get the approval, find the info)
- Delete `HANDOFF.md` after resolution
- Continue working

## SESSION.md Protocol

At the end of every session, append a summary block to `SESSION.md` (create it if it doesn't exist). Use the structure from `docs/templates/SESSION_TEMPLATE.md`.

SESSION.md is gitignored (per-session working file) but should be maintained locally for continuity across sessions.

## Commit Frequency

- Minimum: commit after each deliverable
- Ideal: commit after each logical unit of work
- Maximum: never let more than 300 lines of diff accumulate without committing
- If the diff exceeds 300 lines, write to HANDOFF.md and request human review

## Commit Message Format

```
<type>(<scope>): <description>

[Optional body explaining why]

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

Types: `feat`, `fix`, `chore`, `test`, `docs`, `refactor`

## Dependency Management

- Do NOT install system-wide packages or modify `pyproject.toml` without approval (YELLOW gate)
- If a dependency is missing, list it in the PHASE_1_REPORT.md under "Questions for the architect"
- For local testing, use the setup script: `bash scripts/setup-dev.sh`
- Or manually: `python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`
- The project version is `0.1.0` (PEP 440 compliant); the MVS phase is tracked in `[tool.sentient] phase = "mvs"`

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific module tests
pytest tests/core/test_inference_gateway.py -v

# Run with coverage
pytest tests/ --cov=sentient --cov-report=term-missing

# Lint check
ruff check src/ tests/
```

## Verification Checklist

Before marking any deliverable as complete, verify:

1. `pytest tests/ -v` — all tests pass
2. `ruff check src/ tests/` — no lint errors
3. The module's specific tests pass
4. SESSION.md has been updated
5. Total diff for this session is under 300 lines (or written to HANDOFF.md if over)

## Emergency Procedures

### If a test fails and you can't fix it in 3 attempts
→ Write to HANDOFF.md. Document the failing test, expected vs actual behavior, and what you tried.

### If the pre-push hook blocks a legitimate push
→ You're trying to push to main. Create a PR instead:
```bash
gh pr create --title "..." --body "..."
```

### If you discover a bug in existing code that's not in your scope
→ Document it in SESSION.md under "Unexpected findings". Don't fix it unless it's blocking your deliverable.

### If you need to modify a RED file
→ Write to HANDOFF.md. Do NOT modify the file. Explain why you need to change it and what the proposed change would be.