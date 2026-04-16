# Phase 1 Inventory — Sentient AI Framework

> Generated: 2026-04-16
> Branch: auto/phase-1-foundation

## Directory Structure

```
Sentient-AI/
├── README.md
├── SETUP.md
├── pyproject.toml
├── .gitignore
├── doc/
│   ├── PRD.md
│   ├── DESIGN_DECISIONS.md
│   ├── ARCHITECTURE.md
│   └── CONVERSATION_SUMMARY.md
├── config/
│   ├── system.yaml
│   ├── inference_gateway.yaml
│   └── identity/
│       ├── constitutional_core.yaml
│       └── developmental.yaml
├── src/sentient/
│   ├── __init__.py
│   ├── main.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── envelope.py
│   │   ├── event_bus.py
│   │   ├── module_interface.py
│   │   ├── lifecycle.py
│   │   └── inference_gateway.py
│   ├── thalamus/
│   │   ├── __init__.py
│   │   ├── heuristic_engine.py
│   │   ├── gateway.py
│   │   └── plugins/
│   │       ├── __init__.py
│   │       ├── base.py
│   │       └── chat_input.py
│   ├── prajna/
│   │   ├── __init__.py
│   │   ├── checkpost.py
│   │   ├── queue_zone.py
│   │   ├── temporal_limbic.py
│   │   └── frontal/
│   │       ├── __init__.py
│   │       ├── cognitive_core.py
│   │       ├── world_model.py
│   │       └── harness_adapter.py
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── gatekeeper.py
│   │   └── architecture.py
│   ├── persona/
│   │   ├── __init__.py
│   │   └── identity_manager.py
│   ├── brainstem/
│   │   ├── __init__.py
│   │   ├── gateway.py
│   │   └── plugins/
│   │       ├── __init__.py
│   │       ├── base.py
│   │       └── chat_output.py
│   ├── sleep/
│   │   ├── __init__.py
│   │   └── scheduler.py
│   ├── health/
│   │   ├── __init__.py
│   │   ├── registry.py
│   │   ├── pulse_network.py
│   │   └── innate_response.py
│   ├── api/
│   │   ├── __init__.py
│   │   └── server.py
│   └── scripts/
│       ├── __init__.py
│       └── init_db.py
├── tests/
│   ├── __init__.py
│   └── test_smoke.py
└── (no docs/, scripts/ top-level dirs yet)
```

## Python Module Inventory

### src/sentient/core/ (5 modules)

| File | Lines | Classes/Functions | Status | Notes |
|------|-------|-------------------|--------|-------|
| `envelope.py` | 173 | `Envelope`, `Priority`, `SourceType`, `TrustLevel` | Working | Full envelope dataclass with tags, pipeline state, confidence |
| `event_bus.py` | 161 | `EventBus`, `get_event_bus()`, `reset_event_bus()` | Working | Async pub/sub with wildcard support. Singleton pattern |
| `module_interface.py` | 182 | `ModuleInterface`, `ModuleStatus`, `LifecycleState`, `HealthPulse` | Working | Abstract base with lifecycle contract + health pulse |
| `lifecycle.py` | 246 | `LifecycleManager` | Working | Startup/shutdown orchestration, sleep transitions, restart |
| `inference_gateway.py` | 302 | `InferenceGateway`, `InferenceRequest`, `InferenceResponse`, `_EndpointMetrics` | Working | Cloud→local→heuristic fallback. litellm integration. Cost tracking |

### src/sentient/thalamus/ (3 modules + 2 plugins)

| File | Lines | Classes/Functions | Status | Notes |
|------|-------|-------------------|--------|-------|
| `heuristic_engine.py` | 83 | `HeuristicEngine` | Working | Layer 1: keyword + health flag detection. Dedup logic |
| `gateway.py` | 246 | `Thalamus` | Working | Adaptive batching, plugin registry, attention summary subscriber |
| `plugins/base.py` | 95 | `InputPlugin` | Working | Abstract base for input plugins with emit callback |
| `plugins/chat_input.py` | 119 | `ChatInputPlugin` | Working | WebSocket chat → envelope conversion. Intent detection |

### src/sentient/prajna/ (3 pipeline modules + 3 frontal)

| File | Lines | Classes/Functions | Status | Notes |
|------|-------|-------------------|--------|-------|
| `checkpost.py` | 121 | `Checkpost` | Scaffold | LLM enhance stubbed. Entity/intent tagging minimal |
| `queue_zone.py` | 242 | `QueueZone`, `_QueueItem` | Working | Priority aging, active/idle modes, batch summarization stub |
| `temporal_limbic.py` | 216 | `TemporalLimbicProcessor`, `EnrichedContext` | Working | Memory retrieval, context assembly, significance weighting |
| `frontal/cognitive_core.py` | 457 | `CognitiveCore`, `CognitiveState`, `ReasoningCycle` | Working | 7-step loop, daydream, attention summary. JSON parsing |
| `frontal/world_model.py` | 261 | `WorldModel`, `ReviewVerdict` | Working | 5-dimension review, veto loop, journal |
| `frontal/harness_adapter.py` | 204 | `HarnessAdapter`, `TaskDelegation`, `TaskResult` | Working | Subprocess spawning of Claude Code / Claw Code |

### src/sentient/memory/ (2 modules)

| File | Lines | Classes/Functions | Status | Notes |
|------|-------|-------------------|--------|-------|
| `gatekeeper.py` | 134 | `MemoryGatekeeper`, `GatekeeperDecision` | Working | Logic-based filtering. Hash dedup, semantic dedup, contradiction detection |
| `architecture.py` | 570 | `MemoryArchitecture`, `MemoryType` | Working | SQLite+FTS5 + ChromaDB dual storage. Multi-path retrieval. Full write pipeline |

### src/sentient/persona/ (1 module)

| File | Lines | Classes/Functions | Status | Notes |
|------|-------|-------------------|--------|-------|
| `identity_manager.py` | 291 | `PersonaManager`, `DynamicState` | Working | 3-layer identity. Constitutional immutable. Identity block assembly |

### src/sentient/brainstem/ (1 module + 2 plugins)

| File | Lines | Classes/Functions | Status | Notes |
|------|-------|-------------------|--------|-------|
| `gateway.py` | 231 | `Brainstem` | Working | Action translator, retry with backoff, safety gate, rate limiter |
| `plugins/base.py` | 76 | `OutputPlugin`, `OutputCommand`, `OutputResult` | Working | Abstract base for output plugins |
| `plugins/chat_output.py` | 79 | `ChatOutputPlugin` | Working | Queue-based output for WebSocket delivery |

### src/sentient/sleep/ (1 module)

| File | Lines | Classes/Functions | Status | Notes |
|------|-------|-------------------|--------|-------|
| `scheduler.py` | 352 | `SleepScheduler`, `SleepStage` | Working | 4-stage sleep, circadian scheduling, emergency wake, sleepwalking |

### src/sentient/health/ (3 modules)

| File | Lines | Classes/Functions | Status | Notes |
|------|-------|-------------------|--------|-------|
| `registry.py` | 87 | `HealthRegistry` | Working | In-memory pulse storage, unresponsive detection |
| `pulse_network.py` | 170 | `HealthPulseNetwork` | Working | Continuous polling, anomaly detection/publishing |
| `innate_response.py` | 262 | `InnateResponse`, `_CircuitBreaker` | Working | Rule-based recovery, circuit breakers, restart with backoff, escalation |

### src/sentient/api/ (1 module)

| File | Lines | Classes/Functions | Status | Notes |
|------|-------|-------------------|--------|-------|
| `server.py` | 338 | `APIServer` | Working | FastAPI + WebSocket (chat + dashboard). Placeholder HTML GUI |

### src/sentient/main.py (1 module)

| File | Lines | Classes/Functions | Status | Notes |
|------|-------|-------------------|--------|-------|
| `main.py` | 228 | `build_and_start()`, `run_forever()`, `run()` | Working | Full system wiring. Signal handling. Startup sequence |

### src/sentient/scripts/ (1 module)

| File | Lines | Classes/Functions | Status | Notes |
|------|-------|-------------------|--------|-------|
| `init_db.py` | 56 | `main()` | Working | SQLite schema init + ChromaDB dir setup |

### tests/ (1 file)

| File | Lines | Tests | Notes |
|------|-------|-------|-------|
| `test_smoke.py` | 245 | 8 tests | Envelope, EventBus, Lifecycle, imports, Gatekeeper, HeuristicEngine |

## Configuration Files

| File | Purpose |
|------|---------|
| `config/system.yaml` | Global system config: thalamus, cognitive core, memory, persona, brainstem, sleep, health, API, logging |
| `config/inference_gateway.yaml` | LLM endpoints per module, fallback chains, routing behavior, cost tracking |
| `config/identity/constitutional_core.yaml` | Immutable identity layer: core values, relationship, ontological honesty, operational constraints |
| `config/identity/developmental.yaml` | Evolving identity: personality traits, communication style, maturity tracking (starts blank) |
| `pyproject.toml` | Python 3.12+, dependencies (litellm, fastapi, chromadb, etc.), ruff config, pytest config |

## Documentation Files

| File | Purpose |
|------|---------|
| `doc/PRD.md` | Product Requirements Document — vision, principles, functional/non-functional requirements, scope |
| `doc/DESIGN_DECISIONS.md` | DD-001 through DD-028 — every architectural decision with rationale and biological analogies |
| `doc/ARCHITECTURE.md` | Full system architecture — module specs, data flows, tech stack, deployment, security |
| `doc/CONVERSATION_SUMMARY.md` | Development history |
| `README.md` | Project overview, structure, Phase 1 checklist |
| `SETUP.md` | Installation, configuration, first-run guide |

## Key Observations

1. **The codebase is surprisingly complete for a "scaffold"** — most modules have real working logic, not just stubs. The README's Phase 1 checklist is partially outdated (several items marked `[ ]` are actually implemented).

2. **inference_gateway.py** (302 lines) is the most critical module for testing. It has:
   - `InferenceRequest` / `InferenceResponse` dataclasses
   - `_EndpointMetrics` with success/failure tracking and health_score
   - `InferenceGateway` class with `infer()`, `_try_endpoint()`, `health_pulse()`
   - Provider-specific model string construction (ollama/anthropic/openai)
   - Timeout handling via `asyncio.wait_for`
   - Cost tracking via `litellm.completion_cost()`
   - Heuristic minimum return when litellm is unavailable

3. **No `docs/` directory exists yet** — the project uses `doc/` for existing documentation. Phase 1 deliverables specify `docs/` (with s), which is a new directory.

4. **No `scripts/` top-level directory** — scripts live in `src/sentient/scripts/`.

5. **.gitignore already has `.env` and `data/`** — but missing `HANDOFF.md`, `SESSION.md`, `.claude-session/`, `*.db`.

6. **Test infrastructure** uses pytest + pytest-asyncio with `asyncio_mode = "auto"`. No existing tests for inference_gateway.

7. **Dependencies** — litellm, pyyaml, fastapi, chromadb, sentence-transformers, apscheduler, pydantic, python-dotenv are all declared. Dev deps include pytest, pytest-asyncio, pytest-cov, ruff, mypy.

8. **The Constitutional Core** (`config/identity/constitutional_core.yaml`) has `modification_lock: true` and explicit "never modify" documentation — per DD-025, this is RED territory.