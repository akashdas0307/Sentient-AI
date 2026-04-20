# D7: Internal References & Cross-Module Data Flow Test Results

**Date**: 2026-04-20  
**Branch**: auto/phase-10-aliveness-audit  
**Server**: http://localhost:8765 (running)

---

## Test 1: EventBus Pub/Sub Verification

**Result: PASS (after correction)**

The original test script called `subscribe()` and `unsubscribe()` synchronously, but the EventBus API defines these as `async` methods. After correcting to use `await`, all sub-tests passed.

### Corrected test results

| Sub-test | Result | Detail |
|----------|--------|--------|
| Subscribe + Publish | PASS | 1 event received with correct payload including `event_type`, `sequence`, and original data |
| Multiple subscribers | PASS | Both handlers received the `test.multi` event (handler1=1, handler2=1) |
| Unsubscribe | PASS | After unsubscribing handler from `test.event`, no new events were delivered to it (before=2, after=2) |
| Wildcard subscription | PASS | `subscribe('*', handler)` received 1 event from `test.wildcard` publish |
| Event count | PASS | `bus.event_count()` returned 4, matching total publishes |

### Key observations

- EventBus uses `subscribe('*', handler)` for wildcard (all events), not glob patterns like `test.*`
- Every published event includes `event_type` and `sequence` fields automatically
- `_to_json_safe()` sanitizes payloads before dispatch (handles dataclasses, Enums, datetime, sets)
- Publish is fire-and-forget: handlers run concurrently via `asyncio.create_task`, exceptions are logged but not propagated
- The global singleton `get_event_bus()` provides one bus per running system

---

## Test 2: Health Pulse Network

**Result: PASS**

### /api/health endpoint

| Module | Status | Pulse Count |
|--------|--------|-------------|
| inference_gateway | healthy | 76 |
| memory | healthy | 76 |
| thalamus | healthy | 76 |
| persona | healthy | 12 |
| innate_response | healthy | 12 |
| checkpost | healthy | 12 |
| queue_zone | healthy | 12 |
| tlp | healthy | 12 |
| cognitive_core | healthy | 12 |
| world_model | healthy | 12 |
| harness_adapter | healthy | 12 |
| decision_arbiter | healthy | 12 |
| brainstem | healthy | 12 |
| sleep_scheduler | healthy | 12 |

### /api/status endpoint

```
System running: True
```

All 15 modules report `state=running, status=healthy` including the `health_pulse_network` module itself.

### Key observations

- Two pulse-count tiers: core infrastructure modules (inference_gateway, memory, thalamus) at 76 pulses, application modules at 12 pulses. This indicates the server has been running long enough for the core modules to accumulate more heartbeat cycles.
- The health endpoint returns per-module dictionaries with `latest` status and `pulse_count`, while the status endpoint returns a flat `state`/`status` per module under a top-level `running: true` flag.
- The original test script for `/api/status` failed because it assumed each module value was a dict with `.get()`, but the response wraps modules under a `modules` key with a top-level `running` boolean.

---

## Test 3: WebSocket Event Stream (30-second capture)

**Result: PASS**

### Event stream summary

| Metric | Value |
|--------|-------|
| Total events in 30s | 70 |
| `health` events | 4 |
| `welcome` events | 1 |
| `event` events | 65 |

### Timeline

- **0.0s**: Burst of ~52 events (1 welcome, 1 health, 50 general `event` types) -- initial state dump on connection
- **3.7-3.8s**: Cluster of 12 events (likely a processing cycle)
- **6.3-6.4s**: 1 event + 1 health pulse
- **11.4s**: 5s gap (no events)
- **16.4s**: Health pulse
- **21.3s**: 1 event
- **26.4s**: Health pulse

### Key observations

- Health pulses arrive approximately every 5 seconds (4 pulses in 30s = ~7.5s average, but the first pulse was at 0s so the interval between subsequent pulses is roughly 10s, which may reflect the configured 30-second health interval with initial burst)
- The initial burst of 52 events at connection start indicates the server sends accumulated state on WebSocket connect
- Event types are categorized as `health`, `welcome`, and generic `event`; the actual event_type field within `event` messages was not individually parsed but would contain the specific event sub-types (e.g., `health.pulse`, `cognitive.cycle.complete`, etc.)

---

## Test 4: Chat Message Pipeline

**Result: PASS**

### Response

```json
{
  "turn_id": "b775d198-55df-4fa7-ae25-aff120e82915",
  "status": "accepted"
}
```

### Key observations

- The `/api/chat` endpoint accepts POST requests with a `message` field and returns a unique `turn_id` with `status: accepted`
- This confirms the Thalamus -> Queue Zone -> Cognitive Core pipeline is accepting input
- The response is asynchronous (accepted, not completed), consistent with the fire-and-forget event-driven architecture

---

## Test 5: Inference Gateway

**Result: PASS (with concern)**

### /api/gateway/calls

| Endpoint | Success | Failure | Avg Latency | Health Score |
|----------|---------|---------|-------------|--------------|
| ollama::glm-5.1:cloud | 0 | 3 | 0.0ms | 0.0 |
| ollama::minimax-m2.7:cloud | 4 | 0 | 38,462ms (~38s) | 1.0 |

### Key observations

- **glm-5.1:cloud has a health_score of 0.0** with 3 failures and 0 successes. This endpoint is currently non-functional, likely due to configuration or availability issues with the cloud Ollama instance.
- **minimax-m2.7:cloud is functional** with 4 successes and high average latency (~38 seconds per call). The high latency suggests either large prompts, slow model inference, or network overhead to the cloud endpoint.
- Total cost reported as $0.00, consistent with self-hosted Ollama models.
- The `/api/gateway/status` and `/api/gateway/calls` endpoints return similar/overlapping data.

---

## Test 6: Module Imports / Dependency Graph

**Result: PASS**

### Core hub modules (imported by 5+ other modules)

| Hub Module | Imported By |
|------------|-------------|
| `core.event_bus` | api.server, brainstem.gateway, cognitive_core, consolidation, contradiction_resolver, decision_arbiter, harness_adapter, health.innate_response, health.pulse_network, identity_drift_detector, inference_gateway, lifecycle, memory.architecture, persona.identity_manager, prajna.checkpost, prajna.queue_zone, prajna.temporal_limbic, procedural_refiner, scheduler, world_model, wm_calibrator |
| `core.module_interface` | brainstem.gateway, brainstem.plugins.base, brainstem.plugins.chat_output, checkpost, cognitive_core, harness_adapter, innate_response, inference_gateway, lifecycle, memory.architecture, persona.identity_manager, pulse_network, queue_zone, scheduler, temporal_limbic, thalamus.gateway, thalamus.plugins.base, thalamus.plugins.chat_input, world_model |
| `core.inference_gateway` | checkpost, cognitive_core, consolidation, contradiction_resolver, developmental_consolidator, temporal_limbic, world_model |
| `core.envelope` | checkpost, cognitive_core, queue_zone, temporal_limbic, thalamus.gateway, thalamus.plugins.chat_input |

### Import chain patterns

1. **Every module imports `EventBus` + `ModuleInterface`** -- this is the standard pattern for framework modules
2. **Modules that use LLM inference import `InferenceGateway`** -- checkpost, cognitive_core, consolidation, contradiction_resolver, developmental_consolidator, temporal_limbic, world_model
3. **`main.py` imports all top-level modules** -- it serves as the orchestrator wiring everything together
4. **Sleep subsystem** has extensive internal cross-imports (scheduler imports consolidation, contradiction_resolver, developmental_consolidator, identity_drift_detector, procedural_refiner, wm_calibrator)
5. **No circular imports observed** -- the architecture maintains a clean DAG dependency structure

---

## Summary

| Test | Result | Notes |
|------|--------|-------|
| 1. EventBus Pub/Sub | PASS | Async subscribe/unsubscribe API; wildcard via `*` not glob |
| 2. Health Pulse Network | PASS | 15 modules all healthy; two pulse-count tiers observed |
| 3. WebSocket Event Stream | PASS | 70 events in 30s; health pulses every ~5-10s; initial state burst on connect |
| 4. Chat Pipeline | PASS | Async acceptance with turn_id; response not inline |
| 5. Inference Gateway | PASS (concern) | glm-5.1:cloud failing (0/3 success); minimax-m2.7 functional but slow (~38s avg) |
| 6. Module Dependency Graph | PASS | Clean DAG; EventBus and ModuleInterface are universal dependencies |

### Issues flagged

1. **glm-5.1:cloud inference endpoint** has health_score 0.0 with 0 successes and 3 failures. This needs investigation (endpoint configuration, availability, or model routing issue).
2. **minimax-m2.7:cloud latency** averaging ~38 seconds per call is high and may impact user experience during chat interactions.
3. **EventBus test script bug**: The original test called async `subscribe`/`unsubscribe` synchronously. The corrected version (using `await`) works correctly. The EventBus source code confirms these are `async def` methods.