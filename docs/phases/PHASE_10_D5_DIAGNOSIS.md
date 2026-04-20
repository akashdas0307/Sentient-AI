# Phase 10 — D5 Diagnosis: Timestamp Format Inconsistency

**Date:** 2026-04-20
**Branch:** `auto/phase-10-aliveness-audit`
**Investigator:** Main session (GLM-5.1)

---

## Executive Summary

Timestamps are inconsistent across the system. The canonical format (per prior decision) is **int milliseconds since epoch**, but the backend emits **float seconds since epoch** via `time.time()` in most places. The frontend expects milliseconds (`new Date(ms)` interprets the argument as milliseconds; values < 1e12 display as 1970 dates). This causes display bugs and deduplication failures.

---

## Root Cause: Backend emits float seconds, frontend expects int milliseconds

### Backend (Python)

Every timestamp in `src/sentient/api/server.py` uses `time.time()`:
- Line 192: `timestamp = time.time()` (chat input)
- Line 200/209: `"timestamp": timestamp` (event payloads)
- Line 379/386: `"timestamp": time.time()` (WS events)
- Line 552: `timestamp = payload.get("timestamp", time.time())` (broadcast — the main path)
- Line 593: `"timestamp": time.time()` (health pulse WS)
- Line 644: `now = time.time()` (cleanup)
- Line 74/79: `TurnRecord.__init__(timestamp: float)` / `self.started_at = timestamp`

All produce float seconds (e.g., `1718457600.123456`).

### Frontend (TypeScript)

- `ChatPanel.tsx:34`: `timestamp: Date.now()` — **int ms** (e.g., `1718457600123`)
- `useWebSocket.ts:98,115,132`: `timestamp: payload.timestamp || Date.now() / 1000` — fallback is **float seconds**
- `EventsPanel.tsx:49`: `new Date(event.timestamp)` — expects **ms**, gets **seconds** from backend → shows 1970
- `MonologuePanel.tsx:29`: `new Date(timestamp)` — same issue
- `ChatPage.tsx:166`: `new Date(msg.timestamp)` — same issue
- `useSentientStore.ts:112`: `m.timestamp === message.timestamp` — **strict equality** fails across formats

### The conversion point

`server.py:552` is the critical conversion point — it's the single place where ALL events pass before reaching the WebSocket. If we normalize timestamps there, all downstream consumers receive the correct format.

---

## Fix Proposal

### Approach: Normalize at the broadcast boundary + add frontend safety net

1. **Add `now_ms()` helper in server.py**: Returns `int(time.time() * 1000)`
2. **Convert in `_broadcast_event()`**: `timestamp = int(payload.get("timestamp", time.time()) * 1000)` if the value looks like seconds (< 1e12)
3. **Convert in chat/WS input paths**: Replace `time.time()` with `now_ms()` in all API response timestamps
4. **Frontend safety net**: Add a `normalizeTimestamp(ts)` function that converts seconds to ms if `ts < 1e12`
5. **Fix deduplication**: Use `Math.abs(m.timestamp - message.timestamp) < 1000` instead of strict equality

### Scope

**server.py** — the main file. Most timestamp conversions happen here.
**frontend/src/hooks/useWebSocket.ts** — add normalization for incoming timestamps
**frontend/src/store/useSentientStore.ts** — fix deduplication to handle format differences
**cognitive_core.py** — `Envelope.created_at` stays as float seconds (internal format). Only the API boundary converts.

### Files NOT changed

- `envelope.py` — `created_at` is internal, stays as float seconds
- `cognitive_core.py` — internal timing uses float seconds (for `idle_seconds` calculations)
- `memory/architecture.py` — internal timestamps, stays as float seconds

---

## Evidence

| # | Observation | Source | Confidence |
|---|---|---|---|
| E1 | Backend uses `time.time()` (float seconds) everywhere | `server.py` grep | **Certain** |
| E2 | Frontend uses `Date.now()` (int ms) for new messages | `ChatPanel.tsx:34` | **Certain** |
| E3 | `new Date(seconds)` shows 1970 dates | JS Date constructor semantics | **Certain** |
| E4 | WebSocket fallback `Date.now() / 1000` converts ms back to seconds | `useWebSocket.ts:98` | **Certain** |
| E5 | Deduplication uses strict equality (`===`) on timestamps | `useSentientStore.ts:112` | **Certain** |
| E6 | `_broadcast_event` is the single path for all WS events | `server.py:548-576` | **Certain** |

---

## Files Investigated

- `src/sentient/api/server.py` — Primary: all timestamp emission points
- `frontend/src/components/ChatPanel.tsx` — Frontend timestamp creation
- `frontend/src/components/EventsPanel.tsx` — Frontend timestamp display
- `frontend/src/components/MonologuePanel.tsx` — Frontend timestamp display
- `frontend/src/pages/ChatPage.tsx` — Frontend timestamp display
- `frontend/src/hooks/useWebSocket.ts` — WS timestamp handling
- `frontend/src/store/useSentientStore.ts` — Deduplication logic
- `src/sentient/prajna/frontal/cognitive_core.py` — Internal timestamps (float seconds, OK)