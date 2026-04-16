# Phase 3 Report

## Status
COMPLETED

## Deliverables checklist
- [x] Fix ruff lint failures (7 unused imports removed, noqa added to test_smoke.py)
- [x] Split chromadb into optional extra (pyproject.toml [memory] extra)
- [x] Update CI workflow (ruff --output-format=github, already after install)
- [x] End-to-end pipeline integration test (6 test functions, all passing)
- [x] Create tests/conftest.py with shared fixtures
- [x] Coverage report for the full project (56% total coverage)
- [x] PHASE_3_REPORT.md

## Files created
- `tests/integration/__init__.py` — Integration test package marker
- `tests/integration/test_pipeline_e2e.py` — 6 E2E pipeline integration tests
- `tests/conftest.py` — Shared test fixtures (EventBus, MockInferenceGateway, MockMemory, MockPersona, Envelope fixtures)

## Files modified
- `src/sentient/api/server.py` — Removed unused StaticFiles and ModuleStatus imports
- `src/sentient/health/pulse_network.py` — Removed unused time import
- `src/sentient/main.py` — Removed unused sys import
- `src/sentient/prajna/checkpost.py` — Removed unused InferenceRequest import
- `src/sentient/prajna/frontal/cognitive_core.py` — Removed unused SourceType import
- `src/sentient/thalamus/plugins/base.py` — Removed unused ModuleStatus import
- `tests/test_smoke.py` — Added `# ruff: noqa: F401` for intentional load-verification imports
- `pyproject.toml` — Split chromadb/sentence-transformers into [memory] optional extra
- `.github/workflows/ci.yml` — Added --output-format=github to ruff check

## Commits made
```
af7b998 fix(phase-3): resolve all ruff lint failures
8562e1f refactor(phase-3): split heavy ML deps into optional memory extra
7ac5670 ci(phase-3): add github output format to ruff lint step
f0d8c71 test(phase-3): add end-to-end pipeline integration tests
9b6f7d1 test(phase-3): create shared conftest.py with pipeline fixtures
```
(5 commits on this branch)

## Tests run

### pytest — full suite
```
98 passed in 5.58s
```

### ruff check — all files
```
All checks passed! (0 errors)
```

### pip install verification
```
pip install -e ".[dev]" → success (includes chromadb via memory extra)
pip install -e . → success (lighter install without chromadb)
```

## Integration test results

### Pipeline steps successfully tested
- Thalamus → Checkpost (input.classified event, heuristic classification, Tier 1 urgency bypass)
- Checkpost → QueueZone (checkpost.tagged event, envelope tagging with checkpost_processed flag)
- QueueZone → TLP (input.delivered event, priority-based delivery)
- TLP → CognitiveCore (tlp.enriched event, context assembly, significance weighting)
- CognitiveCore → WorldModel (decision.proposed event, structured JSON reasoning with mocked LLM)
- WorldModel → Brainstem (decision.approved event, 5-dimension review with mocked LLM)
- Brainstem → ChatOutput (action.executed event, text_chat command routing)
- WorldModel veto path (decision.vetoed event, safety violation detection)
- Envelope metadata enrichment (checkpost_processed, tlp_enriched, significance)

### Pipeline steps blocked (with reasons)
None. All pipeline stages were testable with the current module interfaces.

### HANDOFF items for production code changes needed
None. The pipeline modules have clean dependency injection through constructors, and all event subscriptions/publishing uses the shared EventBus, making integration testing straightforward with mocked LLM and memory.

## Full project coverage baseline

```
Name                                             Stmts   Miss  Cover   Missing
------------------------------------------------------------------------------
src/sentient/__init__.py                             1      0   100%
src/sentient/api/__init__.py                         2      0   100%
src/sentient/api/server.py                         128    108    16%   42-59, 62, 72-151, 157-181, 184-191, 195-209, 213-225, 232
src/sentient/brainstem/__init__.py                   3      0   100%
src/sentient/brainstem/gateway.py                  109     30    72%   63-64, 71, 83, 94-97, 115-132, 136-137, 141, 146-148, 169-170, 190-196, 206, 220
src/sentient/brainstem/plugins/__init__.py           3      0   100%
src/sentient/brainstem/plugins/base.py              41      6    85%   58, 61, 64, 67-75
src/sentient/brainstem/plugins/chat_output.py       34      4    88%   47, 71-73
src/sentient/core/__init__.py                        5      0   100%
src/sentient/core/envelope.py                       75      2    97%   134, 150
src/sentient/core/event_bus.py                      53      0   100%
src/sentient/core/inference_gateway.py             138      7    95%   105-106, 121, 221-222, 247-248
src/sentient/core/lifecycle.py                     122     57    53%   50, 59, 63, 83-90, 118-127, 141-149, 160-170, 174-184, 190-208, 223-224, 236
src/sentient/core/module_interface.py               70      0   100%
src/sentient/health/__init__.py                      4      0   100%
src/sentient/health/innate_response.py             119     89    25%   36-41, 44-52, 55-58, 62-68, 80-102, 105, 108, 111, 115-138, 146-160, 173-175, 187-189, 197, 204-222, 231-244, 250
src/sentient/health/pulse_network.py                69     51    26%   31-49, 55-61, 64-65, 68-69, 75-126, 130-134, 148, 151, 154
src/sentient/health/registry.py                     42     27    36%   20-24, 28-29, 33, 37-38, 42-43, 51-61, 65-68, 72, 83
src/sentient/main.py                               113     77    32%   63-68, 73-186, 191-214, 219-222, 226
src/sentient/memory/__init__.py                      3      0   100%
src/sentient/memory/architecture.py                216    184    15%   109-129, 135-170, 173-174, 177-178, 184-204, 213-294, 305-357, 361-363, 381-382, 391-393, 416-524, 528-539, 542-556
src/sentient/memory/gatekeeper.py                   52     14    73%   65, 86-89, 99-102, 128-133
src/sentient/persona/__init__.py                     2      0   100%
src/sentient/persona/identity_manager.py           126     91    28%   49-65, 68-70, 77-82, 87, 93-111, 119, 149-150, 158-164, 173-223, 233-246, 250-251, 260-265, 270, 273, 277, 280
src/sentient/prajna/__init__.py                      4      0   100%
src/sentient/prajna/checkpost.py                    44      7    84%   61-63, 73-76, 109-113
src/sentient/prajna/frontal/__init__.py              4      0   100%
src/sentient/prajna/frontal/cognitive_core.py      199     51    74%   190-192, 216, 229-232, 237, 272, 278-281, 285, 304-305, 311, 319, 321-323, 336, 346-349, 351, 355-357, 371-374, 377-378, 382-392, 402-403, 419-425, 431-432, 437-445
src/sentient/prajna/frontal/harness_adapter.py      85     49    42%   59-70, 74, 78-79, 83, 87-98, 111-166, 176-191, 194
src/sentient/prajna/frontal/world_model.py          92     16    83%   128-129, 174-176, 190-191, 229-232, 234, 237-239, 246
src/sentient/prajna/queue_zone.py                  110     40    64%   34-40, 104-105, 113-125, 144-152, 161-163, 166-167, 171-190, 210, 227-231
src/sentient/prajna/temporal_limbic.py              87      8    91%   40, 94-96, 132, 134, 162, 208
src/sentient/scripts/__init__.py                     0      0   100%
src/sentient/scripts/init_db.py                     31     31     0%   5-55
src/sentient/sleep/__init__.py                       2      0   100%
src/sentient/sleep/scheduler.py                    158    121    23%   43-64, 67-69, 72-73, 76-79, 85-94, 98-104, 108-123, 129-154, 158-164, 171, 175-188, 204-220, 230-236, 240-256, 260-275, 285-288, 294-299, 303-314, 324-335, 340-341
src/sentient/thalamus/__init__.py                    4      0   100%
src/sentient/thalamus/gateway.py                   127     40    69%   88-89, 94-95, 102, 110, 113, 124-126, 149-156, 163, 178-179, 186-189, 193-205, 218-227, 234
src/sentient/thalamus/heuristic_engine.py           32      9    72%   39-41, 47, 60, 73-81
src/sentient/thalamus/plugins/__init__.py            3      0   100%
src/sentient/thalamus/plugins/base.py               36      7    81%   61, 71, 75-79
src/sentient/thalamus/plugins/chat_input.py         54      9    83%   58-59, 82-84, 105-108, 113
------------------------------------------------------------------------------
TOTAL                                             2602   1135    56%
```

## Phase 4 test targets (5 lowest-coverage MVS modules)

| Module | Coverage | MVS Scope |
|--------|----------|-----------|
| memory/architecture.py | 15% | All four types, dual storage, gatekeeper, multi-path retrieval |
| api/server.py | 16% | System GUI: chat interface + basic dashboard |
| sleep/scheduler.py | 23% | Four stages, memory consolidation, wake-up handoff |
| health/innate_response.py | 25% | Layer 2 innate response |
| health/pulse_network.py | 26% | Layer 1 pulse monitoring |

## Model usage
- **GLM-4.6**: Integration test design (deep reading of 12+ pipeline modules, mock strategy design, event flow analysis, fixture architecture). Report synthesis.
- **MiniMax-M2**: Lint fixes (routine import removal), pyproject.toml edit, CI YAML edit, conftest.py creation.

## Approval gates hit
No YELLOW or RED gates were hit during Phase 3. All deliverables were GREEN:
- Lint fixes: removing unused imports (GREEN per architect approval)
- pyproject.toml dependency split: explicitly GREEN-approved by architect
- CI YAML update: new file / config change (GREEN)
- Integration test files: new test files (GREEN)
- conftest.py: new test file (GREEN)

## Unexpected findings
None. The pipeline modules were well-designed for testability with constructor dependency injection and event-based communication.

## Questions for the architect
1. **Should the API server tests require a running HTTP server?** The 16% coverage on server.py is because most of its code runs inside WebSocket handlers and HTTP routes. Testing these properly requires starting a TestClient, which is doable but heavier than unit tests.

2. **Should MemoryArchitecture tests use a real SQLite database or mock it?** The 15% coverage is because MemoryArchitecture requires real SQLite + ChromaDB. With chromadb now in the [memory] extra, tests would need `pip install -e ".[memory]"` to run full memory tests. We could test the SQLite path separately with an in-memory database.

3. **Should integration tests use shorter timeouts for the QueueZone delivery loop?** Currently the delivery loop checks every 2 seconds. For test speed, a configurable check interval would help. This would be a production code change (GREEN — single module refactor).