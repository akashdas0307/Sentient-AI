# Phase 10 — D1 Diagnosis: Why Are Cognitive Cycles Hollow?

**Date:** 2026-04-20
**Branch:** `auto/phase-10-aliveness-audit`
**Investigator:** Main session (GLM-5.1)

---

## Executive Summary

Daydream cycles are hollow because the `_daydream()` method passes `context=None` to `_run_reasoning_cycle()`, which hits an early-return guard that short-circuits before the LLM is ever called. Sleep cycles never fire during testing because the scheduler is circadian-gated (23:00–07:00 only) with no idle-time trigger and no debug endpoint.

Both are architectural stubs — acknowledged "TODO" items from earlier phases that were never connected. They are not bugs in the sense of incorrect logic; the logic does exactly what it says. The problem is that the code paths that would produce real thinking were never implemented.

---

## Root Cause 1: Daydream Cycles Produce No Thought

### Primary: Early-return guard kills the reasoning cycle

**File:** `src/sentient/prajna/frontal/cognitive_core.py:286-299`

```python
# Guard: if no envelope (daydream with context=None or no envelope),
# publish cycle events with null IDs and return early
if context is None or envelope is None:
    logger.debug("Reasoning cycle skipped: no envelope (daydream)")
    cycle.completed_at = time.time()
    await self.event_bus.publish(
        "cognitive.cycle.complete",
        {
            "cycle_id": cycle.cycle_id,
            "is_daydream": is_daydream,
            "monologue": "",
            "decision_count": 0,
            "duration_ms": 0,
        },
    )
    return cycle
```

This guard fires on **every** daydream because `_daydream()` at line 680 explicitly passes `context=None`:

```python
# Run daydream as a reasoning cycle without an envelope
# In full implementation, build EnrichedContext from random seed
await self._run_reasoning_cycle(context=None, is_daydream=True)
```

The comment "In full implementation, build EnrichedContext from random seed" confirms this was a known stub. The result: `cognitive.cycle.complete` events with `monologue: ""`, `decision_count: 0`, `duration_ms: ~0.017` (just the guard check, no LLM call).

### Secondary: Seed selector exists but output never reaches the prompt

The `DaydreamSeedSelector` infrastructure is fully implemented (`daydream_seeds.py`):
- `RandomMemorySeed` — queries episodic memory with random-ish queries
- `EmotionalResidueSeed` — pulls emotionally tagged recent memories
- `CuriositySeed` — FIFO queue of follow-up questions from reasoning cycles

Config confirms it's enabled (`system.yaml:41: seed_sources_enabled: true`).

The seed selector IS instantiated in `CognitiveCore.__init__` (lines 188-203) and `_build_daydream_seed_async()` (line 596) can produce seed text. But `_assemble_prompt()` (which calls `_build_daydream_seed_async()`) is **never reached** because the early-return at line 286 fires first.

### Evidence

| Observation | Source | Status |
|---|---|---|
| `cognitive.cycle.complete` with empty monologue | Event log (overnight run) | Confirmed |
| `decision_count: 0` on all daydream cycles | Event log | Confirmed |
| `duration_ms: 0.017` (guard check only, no LLM) | Event log | Confirmed |
| `seed_sources_enabled: true` in config | `config/system.yaml:41` | Confirmed |
| `_seed_selector` instantiated when memory available | `cognitive_core.py:188-203` | Confirmed |
| Early-return guard requires context or envelope | `cognitive_core.py:286` | Root cause |
| `_daydream()` passes `context=None` | `cognitive_core.py:680` | Root cause |

### Fix Proposals for D2 (ranked)

1. **Build a synthetic Envelope from the daydream seed** (Recommended)
   - In `_daydream()`, call `_build_daydream_seed_async()` to get seed text
   - Create a synthetic `Envelope` with `source_type=SourceType.INTERNAL_DAYDREAM`, `processed_content=seed_text`
   - Wrap it in a minimal dict context `{"envelope": envelope, "related_memories": [], "sidebar": []}`
   - Pass this context to `_run_reasoning_cycle()` instead of `None`
   - This satisfies the guard and the seed text flows through the full prompt assembly path
   - **Impact:** Minimal change to `_daydream()` method, no restructuring of `_run_reasoning_cycle`
   - **Risk:** Low — the guard still protects real reasoning, daydreams just get their own synthetic envelope

2. **Restructure the guard to skip envelope requirement for daydreams**
   - Change the guard at line 286 to only short-circuit for non-daydream cycles without envelopes
   - For daydream cycles with `context=None`, fall through to `_assemble_prompt()` which already handles the is_daydream path
   - **Impact:** Changes the guard semantics, need to ensure prompt assembly works without context dict (it accesses `context.get()` which would fail on None)
   - **Risk:** Medium — need to handle None context in `_assemble_prompt()` sidebar block and memory retrieval blocks

3. **Add a dedicated daydream reasoning path** (Over-engineering risk)
   - Create a separate `_run_daydream_cycle()` that doesn't go through the full reasoning path
   - **Impact:** Code duplication, divergence between daydream and active reasoning
   - **Risk:** High — two paths to maintain, test divergence

**Recommendation:** Fix proposal #1 is the cleanest path. It uses existing infrastructure (seed selector, envelope system) and requires minimal changes to a single method.

---

## Root Cause 2: Sleep Cycles Never Fire During Testing

### Primary: Circadian-only trigger

**File:** `src/sentient/sleep/scheduler.py:103-124`

The scheduler loop checks every 60 seconds whether `_is_sleep_time()` returns True. This method only checks the hour of day:

```python
def _is_sleep_time(self) -> bool:
    now = datetime.now()
    hour = now.hour
    if self.sleep_hour < self.wake_hour:
        return self.sleep_hour <= hour < self.wake_hour
    else:
        return hour >= self.sleep_hour or hour < self.wake_hour
```

Default window: `sleep_hour=23`, `wake_hour=7` (from `config/system.yaml` which has no explicit `default_circadian` key, so defaults kick in from `scheduler.py:74-75`).

**Consequence:** If the system is started at 2pm and stopped at 6pm, sleep never fires. The scheduler is running but the condition is never met.

### Secondary: No debug endpoint to force a sleep cycle

Phase 9 D10 was supposed to add `POST /api/debug/sleep_cycle` but this was skipped. There is no way to trigger a sleep cycle programmatically except by waiting for the circadian window.

### Tertiary: Default sleep duration is 6-12 hours

**File:** `scheduler.py:67-68`

```python
self.min_hours = config.get("duration", {}).get("min_hours", 6)
self.max_hours = config.get("duration", {}).get("max_hours", 12)
```

The `system.yaml` sleep config has no `duration` key, so defaults of 6/12 hours apply. Even if sleep fires, a full cycle takes:
- Settling: 45 minutes
- Maintenance: 60-120 minutes
- Deep Consolidation: remainder
- Pre-Wake: 45 minutes
- **Total: 6-12 hours**

The `max_duration_seconds: 300` in `system.yaml:86` is NOT read by the scheduler — it appears to be a config key for the consolidation subsystem, not the scheduler itself.

### Evidence

| Observation | Source | Status |
|---|---|---|
| No `sleep.consolidation.*` events in overnight log | Event log | Confirmed |
| Scheduler running (health_pulse shows stage=awake) | Health pulse | Confirmed |
| No debug sleep endpoint | `api/server.py` search | Confirmed |
| Default sleep window 23:00-07:00 | `scheduler.py:74-75` + missing config | Confirmed |
| No idle-time trigger for sleep | `scheduler.py:103-114` | Root cause |
| `max_duration_seconds: 300` not used by scheduler | `scheduler.py:67-68` | Config gap |

### Fix Proposals for D3/D4 (ranked)

1. **Add `POST /api/debug/sleep_cycle` debug endpoint** (Required for D4 verification)
   - Dev-only endpoint that calls `sleep.enter_sleep(requested_hours=0.1)` (6 minutes)
   - Auth: check `config.dev_mode` or similar flag
   - This bypasses the circadian gate and allows testing at any time

2. **Add idle-time trigger as alternative to circadian gate**
   - After N hours of idle (configurable), allow sleep to start regardless of time-of-day
   - This makes the system genuinely autonomous rather than time-dependent

3. **Add `duration` section to sleep config**
   - Map the existing `max_duration_seconds` to the scheduler or add `duration.min_hours` / `duration.max_hours` with test-appropriate values
   - For testing: `min_hours: 0.1` (6 min), `max_hours: 0.25` (15 min)

4. **Add stage duration overrides for testing**
   - `stages.settling_minutes: 1`, `stages.pre_wake_minutes: 1` for dev mode
   - Avoids 45+45 minutes of waiting during verification

**Recommendation:** Fix proposals #1 + #3 + #4 together. The debug endpoint is mandatory for D4 verification. The duration and stage overrides make testing practical. The idle-time trigger (#2) is a Phase 11 improvement — it's a design change that needs more thought.

---

## Summary of Ranked Hypotheses

| # | Hypothesis | Confidence | Evidence |
|---|---|---|---|
| H1 | Daydream passes `context=None` → early-return guard fires → no LLM call | **Certain** | Code trace, event log, comment "In full implementation" |
| H2 | Seed selector output never reaches prompt assembly | **Certain** | Guard fires before `_assemble_prompt()` is reached |
| H3 | Sleep is circadian-gated only, no idle trigger | **Certain** | `_is_sleep_time()` only checks hour, no idle counter |
| H4 | Sleep duration defaults (6-12h) prevent practical testing | **Certain** | Config has no `duration` section, defaults apply |
| H5 | Memory stores have no daydream-origin rows | **Probable** | If no daydream produces content, nothing is stored |
| H6 | CuriositySeed queue is empty (no prior reasoning cycles with candidates) | **Probable** | Cold start, no prior conversation to populate it |

---

## Files Investigated

- `src/sentient/prajna/frontal/cognitive_core.py` — Primary root cause
- `src/sentient/prajna/frontal/daydream_seeds.py` — Seed selector (functional, not connected)
- `src/sentient/sleep/scheduler.py` — Sleep trigger logic
- `src/sentient/main.py` — Startup wiring (correct)
- `config/system.yaml` — Daydream and sleep config
- `config/inference_gateway.yaml` — Model routing (cognitive-core → glm-5.1:cloud)