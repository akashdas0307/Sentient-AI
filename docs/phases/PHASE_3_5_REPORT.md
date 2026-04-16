# Phase 3.5 Report: Infrastructure

## Status
COMPLETED

## Deliverables checklist
- [x] D1: Merge phase branches to main (already merged via PR #1, tagged v0.3-mvs-pipeline, local branches deleted)
- [x] D2: Create docs structure (docs/phases/, reports moved, HANDOFF.md, SEASON_LOG.md)
- [x] D3: Update CLAUDE.md with orchestration rules (agent roster, branch/merge/test tier rules)
- [x] D4: CI feedback loop scripts (safe_push.sh, pre-push hook, install_hooks.sh)
- [x] D5: Restructure tests into tiers (unit/, integration/, wetware/)
- [x] D6: Phase 3.5 report (this file)

## D1: Merge phase branches to main

Phase branches had already been merged to main via GitHub PR #1 (`auto/phase-3-integration` → `main`). Local main was synced with `git pull origin main` (fast-forward, 21 commits).

- Tag `v0.3-mvs-pipeline` applied to main
- Local branches deleted: `auto/phase-1-foundation`, `auto/phase-2-hardening`, `auto/phase-3-integration`
- **HANDOFF**: Remote branch deletion and tag push require manual action — GitHub auth not configured in dev environment (`gh` CLI not installed)

## D2: Create docs structure

- Created `docs/phases/` directory
- Moved `PHASE_1_REPORT.md`, `PHASE_2_REPORT.md`, `PHASE_3_REPORT.md` into `docs/phases/` (via `git mv`)
- Created `docs/HANDOFF.md` — current state handoff for Phase 4
- Created `docs/SEASON_LOG.md` — one paragraph per completed phase (1, 2, 3, 3.5)

## D3: Update CLAUDE.md

Appended the following sections to CLAUDE.md (original content preserved):

- **Agent Roster and Tier Mapping** — GLM-5.1 (architect/planner/critic), Kimi-K2.5 (writer/explorer), MiniMax-M2.7 (executor/test engineer)
- **Orchestration Rules** — dispatch/read/write/verify/approve separation
- **Branch Rules** — phase branches from main after merge, naming convention
- **Merge Rules** — --no-ff, tagging, branch cleanup
- **Test Tiers** — unit (fast), integration (mocked multi-module), wetware (real LLM, deselected by default)
- **Pre-Push Hook Contract** — ruff + pytest before push
- **CI Feedback Contract** — safe_push.sh, gh run watch, debugger dispatch

## D4: CI feedback loop scripts

Created three scripts:
- `scripts/safe_push.sh` — pushes to remote, watches CI via `gh run watch` if available, warns if `gh` not installed
- `scripts/pre-push` — runs `ruff check src/ tests/` and `pytest -x --ff -q tests/unit tests/integration` before push
- `scripts/install_hooks.sh` — copies pre-push hook to `.git/hooks/`

## D5: Restructure tests into tiers

### New structure
```
tests/
  __init__.py
  conftest.py              (shared fixtures)
  unit/
    __init__.py
    test_smoke.py
    core/
      __init__.py
      test_event_bus.py
      test_inference_gateway.py
      test_module_interface.py
  integration/
    __init__.py
    test_pipeline_e2e.py
  wetware/
    __init__.py
    conftest.py            (real-Ollama InferenceGateway fixture)
    test_pipeline_real.py  (full pipeline with real LLM calls)
```

### pytest configuration (pyproject.toml)
- `wetware` marker registered, deselected by default
- `pytest` runs unit + integration (98 tests)
- `pytest -m wetware` runs wetware only (1 test, requires Ollama)

### Verification
- 98 tests pass in unit + integration
- Ruff: 0 errors
- Wetware marker registered, 1 test collected / 98 deselected by default
- **HANDOFF**: Wetware smoke test requires running Ollama with GLM-4.6 and MiniMax-M2 — expected to fail without local LLM server

## Files created
- `docs/phases/` — Phase report directory
- `docs/HANDOFF.md` — Current state handoff
- `docs/SEASON_LOG.md` — Chronological phase log
- `scripts/safe_push.sh` — CI feedback push script
- `scripts/pre-push` — Pre-push hook content
- `scripts/install_hooks.sh` — Hook installation script
- `tests/unit/__init__.py` — Unit test package
- `tests/unit/core/__init__.py` — Unit core package
- `tests/wetware/__init__.py` — Wetware test package
- `tests/wetware/conftest.py` — Real-Ollama fixture
- `tests/wetware/test_pipeline_real.py` — Wetware smoke test
- `docs/phases/PHASE_3_5_REPORT.md` — This report

## Files moved
- `PHASE_1_REPORT.md` → `docs/phases/PHASE_1_REPORT.md`
- `PHASE_2_REPORT.md` → `docs/phases/PHASE_2_REPORT.md`
- `PHASE_3_REPORT.md` → `docs/phases/PHASE_3_REPORT.md`
- `tests/test_smoke.py` → `tests/unit/test_smoke.py`
- `tests/core/test_event_bus.py` → `tests/unit/core/test_event_bus.py`
- `tests/core/test_inference_gateway.py` → `tests/unit/core/test_inference_gateway.py`
- `tests/core/test_module_interface.py` → `tests/unit/core/test_module_interface.py`

## Files modified
- `CLAUDE.md` — Appended orchestration rules (lines 92-146)
- `pyproject.toml` — Added pytest wetware marker and addopts

## HANDOFF items

1. **GitHub auth not configured**: `gh` CLI not installed. Remote branch deletion and tag push need manual action:
   ```bash
   git push origin --delete auto/phase-1-foundation auto/phase-2-hardening auto/phase-3-integration
   git push origin v0.3-mvs-pipeline
   ```
2. **Wetware smoke test untested**: Requires running Ollama locally. Test is correctly skipped by default.
3. **Pre-push hook not installed**: Run `bash scripts/install_hooks.sh` to install.

## Model usage
- **GLM-5.1**: Orchestration, task decomposition, verification
- **Kimi-K2.5**: Documentation (D2: HANDOFF.md, SEASON_LOG.md; D3: CLAUDE.md sections)
- **MiniMax-M2.7**: CI scripts (D4), test restructure (D5)