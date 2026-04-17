# Handoff: Phase 5 First-Boot Bug Fixes

## Current State

- **Phase 4c MERGED** — Phase 5 now in progress
- **Branch:** `auto/phase-5-first-boot` (active)
- **Total tests:** 339 passing (core/api/prajna/persona/sleep), 7 main.py tests passing (6 heavy async tests excluded from CI)
- **Ruff:** 0 errors

## Coverage Results

| Module | Before | After | Target | Status |
|--------|--------|-------|--------|--------|
| api/server.py | 16% | 91.4% | ≥45% | EXCEEDED |
| persona/identity_manager.py | 28% | 100% | ≥50% | EXCEEDED |
| sleep/scheduler.py | 23% | 95% | ≥45% | EXCEEDED |
| prajna/frontal/harness_adapter.py | 42% | 100% | ≥60% | EXCEEDED |
| core/inference_gateway.py | 95% | ~95% | ≥90% | OK |
| main.py | 32% | 41% | ≥50% | BELOW TARGET* |

*main.py at 41% because 6 heavy integration tests (build_and_start, run_forever) are excluded from CI runs due to RAM constraints from `importlib.reload()` loading all heavy modules.

## Critical Fixes Applied

1. **First-boot IndexError** — `identity_manager.py:110` now handles empty `maturity_log` lists
2. **RAM exhaustion** — Removed session-scoped event_loop fixture, added proper scheduler conftest with teardown, fixed hanging test
3. **CI workflow** — Replaced `pytest tests/` with `bash scripts/run_tests_safe.sh --cov` (per-directory isolation)
4. **Wetware fixture** — Loads full config from YAML instead of hardcoded URL
5. **Config restoration** — `inference_gateway.yaml` and `system.yaml` restored from accidental deletion

## Known Issues for Phase 5

1. **main.py coverage below target (41% vs ≥50%)** — Need per-test conftest with module-level mocking to enable RAM-safe async test execution for `build_and_start`/`run_forever` tests
2. **E2E test infrastructure** — Wetware tests require running Ollama. E2e framework deferred to later phase.
3. **`test_run_calls_asyncio_run` warning** — RuntimeWarning about unawaited coroutine in gc.collect(). Harmless but noisy.

## Next Up: Phase 5

**Goal:** Complete coverage for main.py, apply doc fixes, set up E2E infrastructure.

| Focus Area | Target | Approach |
|-----------|--------|----------|
| main.py async tests | ≥50% | Create tests/unit/conftest.py with heavy module mocks |
| Documentation | Fresh | Apply fixes from DOC_AUDIT_4c.md |
| E2E tests | Framework | Set up test harness requiring Ollama |
| Performance benchmarks | Baseline | Measure startup time, memory usage |

## Repository Status

- **Branch:** `auto/phase-5-first-boot` (active)
- **GitHub auth:** Configured — `gh` CLI available and authenticated
- **CI:** Uses `scripts/run_tests_safe.sh --cov` for per-directory isolation
- **Pre-push hook:** `scripts/install_hooks.sh` (ruff check + pytest unit/integration)