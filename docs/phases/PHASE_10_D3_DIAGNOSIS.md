# Phase 10 — D3 Diagnosis: Sleep Subsystem Forensics

**Date:** 2026-04-20
**Branch:** `auto/phase-10-aliveness-audit`
**Investigator:** Main session (GLM-5.1)

---

## Executive Summary

Sleep cycles never fire during testing for three compounding reasons: (1) the scheduler is circadian-gated only — no idle-time trigger exists; (2) there is no debug endpoint to force a sleep cycle programmatically; (3) the sleep config tree is disconnected — `system.yaml` has `sleep.consolidation.max_duration_seconds: 300` but the scheduler reads `sleep.duration.min_hours` (which doesn't exist), causing 6-12 hour defaults to apply even when `max_duration_seconds: 300` suggests shorter durations were intended.

---

## Root Cause 1: Circadian-Only Trigger

**File:** `src/sentient/sleep/scheduler.py:103-124`

The `_schedule_loop()` checks every 60 seconds whether `_is_sleep_time()` returns True. This method only checks the hour of day:

```python
def _is_sleep_time(self) -> bool:
    now = datetime.now()
    hour = now.hour
    if self.sleep_hour < self.wake_hour:
        return self.sleep_hour <= hour < self.wake_hour
    else:
        return hour >= self.sleep_hour or hour < self.wake_hour
```

Default window: `sleep_hour=23`, `wake_hour=7` (from `scheduler.py:74-75` defaults since `system.yaml` has no `default_circadian` key under `sleep`).

**Consequence:** If the system is started at 2pm and stopped at 6pm, sleep never fires. The scheduler loop is running but the condition is never met.

**Missing:** No idle-time trigger. A sentient system should be able to enter sleep after prolonged inactivity, not just at night. The Gemini advisor review from D1 recommended this as a Phase 11 improvement, but for Phase 10 verification we need at minimum a manual trigger.

---

## Root Cause 2: No Debug Endpoint

**File:** `src/sentient/api/server.py`

The API server has two sleep-related endpoints:
- `GET /api/sleep/status` (line 312) — read-only status query
- `GET /api/sleep/consolidations` (line 320) — read-only consolidation history

There is **no** `POST /api/debug/sleep_cycle` endpoint. Phase 9 D10 was supposed to add this but it was skipped. Without a debug endpoint, the only way to trigger sleep is to either:
1. Wait for the circadian window (23:00-07:00)
2. Set system clock to nighttime (not practical in CI)
3. Call `scheduler.enter_sleep()` directly in test code (possible but doesn't verify the API path)

---

## Root Cause 3: Config Tree Disconnect

**File:** `config/system.yaml:82-86` vs `scheduler.py:67-68`

The config file has:
```yaml
sleep:
  consolidation:
    enabled: true
    schedule: daily
    max_duration_seconds: 300    # <-- This is for ConsolidationEngine
```

But the scheduler reads:
```python
self.min_hours = config.get("duration", {}).get("min_hours", 6)
self.max_hours = config.get("duration", {}).get("max_hours", 12)
```

The scheduler looks for `sleep.duration.min_hours` and `sleep.duration.max_hours` — these keys **do not exist** in `system.yaml`. The `max_duration_seconds: 300` key is under `sleep.consolidation`, which is read by `ConsolidationEngine`, not the scheduler.

**Result:** Sleep always defaults to 6-12 hours regardless of the 300-second consolidation config. Even if sleep fires, a full cycle takes:
- Settling: 45 minutes (default `settling_minutes`)
- Maintenance: 60-120 minutes
- Deep Consolidation: remainder
- Pre-Wake: 45 minutes (default `pre_wake_minutes`)
- **Total: 6-12 hours**

The integration tests (`test_sleep_consolidation.py`) work around this by using `patch("asyncio.sleep", new=fake_sleep)` to skip all the time waits, but this doesn't test the actual sleep trigger path.

---

## Root Cause 4: Missing `default_circadian` Config

**File:** `config/system.yaml` — no `sleep.default_circadian` key

The scheduler reads:
```python
circadian = config.get("default_circadian", {})
self.sleep_hour = circadian.get("sleep_hour", 23)
self.wake_hour = circadian.get("wake_hour", 7)
```

Since `system.yaml` has no `default_circadian` under `sleep`, the defaults of 23:00/07:00 always apply. This is intentional for production but means there's no way to configure different circadian windows for testing.

---

## Evidence Summary

| # | Observation | Source | Confidence |
|---|---|---|---|
| E1 | `_is_sleep_time()` only checks hour of day | `scheduler.py:116-124` | **Certain** |
| E2 | No idle-time trigger exists | `scheduler.py:103-114` | **Certain** |
| E3 | No `POST /api/debug/sleep_cycle` endpoint | `server.py` search | **Certain** |
| E4 | `sleep.duration` config key missing from system.yaml | `system.yaml` vs `scheduler.py:67-68` | **Certain** |
| E5 | `max_duration_seconds: 300` is for ConsolidationEngine, not scheduler | `consolidation.py` vs `scheduler.py` | **Certain** |
| E6 | `default_circadian` config key missing from system.yaml | `system.yaml` vs `scheduler.py:73-75` | **Certain** |
| E7 | Integration tests bypass sleep timing via `patch("asyncio.sleep")` | `test_sleep_consolidation.py:258-261` | **Certain** |
| E8 | Stage defaults (45+45 min settling/pre-wake) make short sleeps impossible | `scheduler.py:69-70` | **Certain** |

---

## Fix Proposals for D4 (ranked)

### Fix 1: Add `POST /api/debug/sleep_cycle` endpoint (Required for verification)

**Location:** `src/sentient/api/server.py`

Add a dev-only endpoint that calls `scheduler.enter_sleep(requested_hours=0.1)` (6 minutes). This bypasses the circadian gate entirely.

**Implementation:**
- New route `POST /api/debug/sleep_cycle`
- Body: `{"requested_hours": 0.1}` (optional, defaults to 0.1)
- Guard: only register if `config.get("dev_mode")` or environment variable `SENTIENT_ENV=development`
- Returns: `{"status": "sleep_entered", "requested_hours": 0.1}`

**Risk:** Low. This is a debug-only endpoint, not registered in production.

### Fix 2: Add `sleep.duration` and `sleep.default_circadian` to system.yaml

**Location:** `config/system.yaml`

Add the missing config keys that the scheduler actually reads:
```yaml
sleep:
  duration:
    min_hours: 6
    max_hours: 12
  default_circadian:
    sleep_hour: 23
    wake_hour: 7
  stages:
    settling_minutes: 45
    pre_wake_minutes: 45
  # ... existing consolidation/contradiction/etc. keys stay
```

**Risk:** Low. Makes existing implicit defaults explicit. No behavior change.

### Fix 3: Add dev-mode stage overrides for short sleep cycles

**Location:** `config/system.yaml` + `scheduler.py`

For dev/testing, allow much shorter stage durations:
```yaml
sleep:
  stages:
    settling_minutes: 1      # dev override (default 45)
    pre_wake_minutes: 1      # dev override (default 45)
```

And add a `dev_overrides` section or environment-based override logic in the scheduler.

**Risk:** Low. The scheduler already reads `settling_minutes` and `pre_wake_minutes` from config, so adding them to the YAML is sufficient. No code changes needed in `scheduler.py`.

### Fix 4: Add idle-time trigger (Phase 11 — defer)

After N hours of idle (configurable), allow sleep to start regardless of time-of-day. This is a design change that needs more thought and is properly Phase 11 scope. For D4, the debug endpoint (Fix 1) is sufficient for verification.

---

## Recommended D4 Action Path

1. Add `POST /api/debug/sleep_cycle` endpoint (Fix 1)
2. Add missing `sleep.duration`, `sleep.default_circadian`, `sleep.stages` config keys (Fix 2)
3. Set stage overrides for short test cycles (Fix 3 — via config only)
4. Write unit test for debug endpoint
5. Verify sleep can be triggered manually via the endpoint

---

## Files Investigated

- `src/sentient/sleep/scheduler.py` — Primary: circadian gate, config gaps, stage durations
- `src/sentient/sleep/consolidation.py` — ConsolidationEngine (reads `max_duration_seconds`)
- `src/sentient/api/server.py` — Existing sleep endpoints (status, consolidations)
- `src/sentient/main.py` — Scheduler initialization with config
- `config/system.yaml` — Sleep config tree (missing scheduler-level keys)
- `tests/integration/test_sleep_consolidation.py` — Existing integration tests