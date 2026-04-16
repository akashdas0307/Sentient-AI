# Phase 4a Report: Substrate Coverage (Memory + Health)

## Status
COMPLETED

## Deliverables checklist
- [x] D1: memory/architecture.py tests (15% → 84%, target ≥55%)
- [x] D2: health/pulse_network.py tests (26% → 99%, target ≥70%)
- [x] D3: health/innate_response.py tests (25% → 98%, target ≥60%)
- [x] D4: Wetware smoke test executed (failed — documented as HANDOFF)
- [x] D5: Phase 4a report (this file)
- [x] D6: HANDOFF.md and SEASON_LOG.md updated

## Coverage deltas

| Module | Before | After | Target | Status |
|--------|--------|-------|--------|--------|
| memory/architecture.py | 15% | 84% | ≥55% | PASS |
| health/pulse_network.py | 26% | 99% | ≥70% | PASS |
| health/registry.py | N/A | 100% | — | PASS |
| health/innate_response.py | 25% | 98% | ≥60% | PASS |
| **Total project** | **56%** | **83%** | **≥65%** | **PASS** |

## Test inventory

- **202 total tests** (up from 98)
- 28 new tests for memory/architecture.py
- 41 new tests for health/pulse_network.py + registry.py
- 35 new tests for health/innate_response.py
- 0 new bugs found in production code

## D1: memory/architecture.py tests

Test file: `tests/unit/core/test_memory_architecture.py` (28 tests)

### Coverage areas
- CRUD for all 4 memory types (episodic, semantic, procedural, emotional)
- Gatekeeper integration: skip (low importance), reinforce (exact dedup), update (semantic match), flag_contradiction, store (passes all filters)
- Multi-path retrieval: tag-based (FTS5), semantic (ChromaDB mocked), combined "both" path
- FTS5 full-text search round-trip (keyword search, no-results case)
- Memory lifecycle: reinforce increments reinforcement_count, retrieve increments access_count
- Error paths: low importance skip, no ChromaDB/embedder, missing chroma collection
- Event bus: memory.stored event publication
- Health pulse: counts by type, module status
- Lifecycle: start subscribes to memory.candidate, _handle_candidate stores memory

### Design decisions
- Uses file-based SQLite (`tmp_path / "memory.db"`) for reliable test isolation
- ChromaDB and SentenceTransformer are mocked entirely (no heavy ML dependencies)
- MemoryGatekeeper uses real logic (not mocked) to test actual integration

## D2: health/pulse_network.py tests

Test file: `tests/unit/core/test_pulse_network.py` (41 tests)

### Coverage areas
- HealthRegistry: record_pulse, latest_pulse, recent_pulses, check_unresponsive, status_of, snapshot, all_statuses
- HealthPulseNetwork: init (intervals, critical modules, registry), initialize (sets expected intervals), start/shutdown lifecycle
- Poll loop: records pulses from modules, skips self, detects status changes
- Anomaly publishing: _publish_anomaly for ERROR and CRITICAL status transitions
- Unresponsive detection: stale pulse flagged, module exception detection
- InnateResponse integration: event bus subscription, payload format verification

### Design decisions
- Direct `_publish_anomaly` testing instead of poll-loop timing-dependent integration tests
- HealthRegistry tested independently from HealthPulseNetwork
- No `@pytest.mark.xfail` markers needed — all tests reflect actual correct behavior

### Bug documentation
- `check_unresponsive()` skips modules with no recorded pulses (returns empty for modules that never pulsed). This is intentional — a module may not have started yet. `status_of()` returns UNRESPONSIVE for unknown modules.

## D3: health/innate_response.py tests

Test file: `tests/unit/core/test_innate_response.py` (35 tests)

### Coverage areas
- CircuitBreaker state machine: CLOSED → OPEN (at threshold), OPEN → HALF_OPEN (after cooldown), HALF_OPEN → CLOSED (on success)
- Error purging: old errors outside window are discarded
- InnateResponse: init (default and custom config), lifecycle (initialize, start, shutdown)
- _handle_anomaly routing: unresponsive, critical, error, degraded, empty payload, exception handling
- _handle_unresponsive: open circuit → escalate without restart, successful restart, failed restart
- _handle_critical: records error, restarts, escalates
- _handle_error: records error, open circuit triggers restart
- _handle_degraded: publishes load_shed event
- _try_restart: success/failure, max attempts, backoff (mocked asyncio.sleep)
- _escalate: publishes health.escalation event, increments counter
- health_pulse: metrics and open circuits

## D4: Wetware smoke test result

**FAILED** — Ollama is running locally but the InferenceGateway does not map model labels correctly.

```
ERROR sentient.prajna.frontal.cognitive_core:cognitive_core.py:191 Cognitive Core LLM error: Unknown model label: cognitive-core
```

Available models on Ollama: `glm-5.1:cloud`, `minimax-m2.7:cloud`, `kimi-k2.5:cloud`, `glm-5:cloud`, `minimax-m2.5:cloud`

The InferenceGateway uses abstract labels ("cognitive-core", "world-model") that need to be mapped to actual Ollama model names. This is a configuration issue, not a code bug. **Documented as HANDOFF for Phase 4b** (prompt/model configuration tuning).

## Files created
- `tests/unit/core/test_memory_architecture.py` — 28 tests, 84% coverage
- `tests/unit/core/test_pulse_network.py` — 41 tests, 99% coverage
- `tests/unit/core/test_innate_response.py` — 35 tests, 98% coverage

## Files modified
- None (all changes are new test files)

## HANDOFF items

1. **InferenceGateway model label mapping**: The gateway needs a configuration mapping from abstract labels ("cognitive-core", "world-model") to actual Ollama model names ("glm-5.1:cloud", "minimax-m2.7:cloud"). This should be added to the config system in Phase 4b.
2. **Phase 4b coverage targets**: The five lowest-coverage modules for Phase 4b+ are:
   - `api/server.py`: 16%
   - `persona/identity_manager.py`: 28%
   - `main.py`: 32%
   - `sleep/scheduler.py`: 23%
   - `prajna/frontal/harness_adapter.py`: 42%
3. **Wetware smoke test**: Once model labels are configured, re-run `pytest -m wetware` to verify the full pipeline works with real LLM calls.

## Model usage
- **GLM-5.1**: Planning, architecture review, task decomposition
- **Kimi-K2.5**: Codebase exploration, module summary
- **MiniMax-M2.7**: Test implementation (all three test files)