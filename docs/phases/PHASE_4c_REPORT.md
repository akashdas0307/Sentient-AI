# Phase 4c Report: Recovery + Lazy Imports + First-Boot Bug Fix

**Branch:** auto/phase-4c-recovery
**Date:** 2026-04-17
**Status:** COMPLETE

---

## Overview

Phase 4c recovered from Phase 4b's incomplete state, verified lazy imports, fixed a production-critical first-boot bug, resolved RAM exhaustion during testing, and updated CI to prevent future OOM failures.

---

## Inherited Deliverables (from Phase 4b)

| Deliverable | Status | Notes |
|-------------|--------|-------|
| D1: InferenceGateway config | DONE (4b) | Config restored from accidental deletion |
| D3: api/server.py tests | DONE (4b) | 21 tests, 92% coverage |
| D7: harness_adapter.py tests | DONE (4b) | 26 tests, 100% coverage |
| Config files | RESTORED | `config/inference_gateway.yaml` and `config/system.yaml` restored from commit e1ffc06 deletion |

---

## New Deliverables

### D0: Lazy-import verification (GREEN gate)

**Result:** Imports already lazy. `python -c "import sentient.main"` uses 8.3MB tracemalloc peak.

**Deliverable:** `scripts/check_lazy_imports.sh` — CI hook that asserts import RSS < 400MB. Defense-in-depth, not discovery.

### D1: Fix first-boot IndexError (YELLOW gate, architect-approved)

**Bug:** `identity_manager.py:110` — `self._developmental.get("maturity_log", [{}])[0].get("started_at")` raises `IndexError` on empty list. When `_blank_developmental()` returns `"maturity_log": []`, the default `[{}]` only applies when key is absent.

**Fix:** 
```python
maturity_log = self._developmental.get("maturity_log") or []
if not maturity_log or not maturity_log[0].get("started_at"):
```

**Regression test:** `test_blank_developmental_no_index_error` — 34/34 persona tests pass.

### D2: Verify test fixes

- D2a: `test_first_boot_creates_maturity_log_entry` passes after D1 fix
- D2b: `test_cancels_current_sleep_task` — already fixed (asyncio.sleep + task.done())
- D2c: `test_build_and_start_*` tests — already fixed (APIServer patch target corrected)

### D3: Full-suite green check

339 tests pass across core/api/prajna/persona/sleep. 7 main.py tests pass (6 heavy async tests excluded from CI due to RAM, pass locally with mocks).

### D4: Per-module coverage

| Module | Baseline | Target | Final | Status |
|--------|----------|--------|-------|--------|
| api/server.py | 16% | ≥45% | 91.4% | EXCEEDED |
| main.py | 32% | ≥50% | 41%* | BELOW* |
| persona/identity_manager.py | 28% | ≥50% | 100% | EXCEEDED |
| sleep/scheduler.py | 23% | ≥45% | 95% | EXCEEDED |
| prajna/frontal/harness_adapter.py | 42% | ≥60% | 100% | EXCEEDED |
| core/inference_gateway.py | 95% | ≥90% | ~95% | OK |

*main.py at 41% because 6 `build_and_start`/`run_forever` async integration tests are excluded from RAM-safe runs — they use `importlib.reload()` which loads all heavy modules at once.

### D5: Wetware fixture fix (YELLOW gate)

**Before:** `InferenceGateway({"base_url": "http://localhost:11434"})` — missing models/routing/cost_tracking keys
**After:** Loads full config from `config/inference_gateway.yaml` via `yaml.safe_load`

### D6: Documentation audit

**Deliverable:** `docs/phases/DOC_AUDIT_4c.md`
- Critical: SETUP.md references old model names
- 5 stale claims in README.md, 4 in SETUP.md
- 3 stale cross-references in HANDOFF.md

### D7: Close-out (this document)

---

## Critical Fix: RAM Exhaustion in Tests

### Problem

Running `pytest tests/` (all tests at once) or `pytest --cov=sentient` exhausts all 14GB RAM + 32GB swap, freezing the system. Root cause: pytest session accumulates:
1. Unmanaged asyncio tasks from SleepScheduler tests
2. Heavy module imports (chromadb ~500MB, sentence_transformers ~1GB, litellm ~200MB)
3. Coverage instrumentation overhead (~500MB)

### Solution

1. **Removed session-scoped `event_loop` fixture** from `tests/conftest.py` — conflicted with pytest-asyncio's internal loop management
2. **Created `tests/unit/sleep/conftest.py`** — proper fixture teardown with `yield + reset_mock + del + gc.collect()`, scheduler task cancellation
3. **Fixed `test_skips_sleep_when_not_awake`** — used `CancelledError` side_effect instead of custom `cancel_soon` that hung the event loop
4. **Updated CI workflow** — replaced `pytest tests/ -v --cov=src/sentient` with `bash scripts/run_tests_safe.sh --cov` (per-directory subprocess isolation)
5. **Fixed `test_run_calls_asyncio_run`** — assertion was comparing `AsyncMock` with coroutine; changed to `assert call_count == 1`

### Results

- All 53 scheduler tests pass in 0.67s (was hanging indefinitely)
- All 339 core/api/prajna/persona/sleep tests pass in 47s with stable RAM
- CI no longer OOMs

---

## Commits (on auto/phase-4c-recovery)

1. `a7a548d` — chore(phase-4c): restore accidentally deleted config files
2. `f593387` — chore(phase-4c): add lazy-import RSS verification script
3. `200e709` — fix(persona): handle empty maturity_log on first boot
4. `562b79f` — fix(wetware): load inference config in real_gateway fixture
5. `712ccd0` — fix(tests): resolve RAM exhaustion from pytest event loop and scheduler task leaks
6. `bdc5672` — fix(ci): use per-directory test runner to prevent RAM exhaustion on CI

---

## Remaining Issues

1. **main.py coverage at 41%** (target ≥50%) — 6 heavy integration tests use `importlib.reload()` which loads all modules. These tests pass locally but are excluded from RAM-safe CI runs. Coverage target not met.
2. **6 main.py async tests excluded from CI** — `build_and_start` and `run_forever` tests need a test-specific conftest with module-level mocking of heavy imports
3. **Documentation staleness** identified in D6 audit but not all fixes applied — deferred to Phase 5

---

## Recommendations for Phase 5

1. Add `tests/unit/test_main.py` conftest with per-test module mocking to enable RAM-safe async test execution
2. Apply documentation fixes from `DOC_AUDIT_4c.md`
3. Set up E2E test infrastructure (requires running Ollama)
4. Consider splitting `main.py` into smaller modules to reduce import weight during testing

---

*Report generated: 2026-04-17*