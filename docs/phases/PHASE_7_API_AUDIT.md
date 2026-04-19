# Phase 7 Deliverable D8: Backend API Audit & Canonical Route Table

**Phase:** 7 — Consolidation and Rebirth (Part B: UI Rebirth)
**Date:** 2026-04-18
**Author:** Architect (GLM-5.1)
**Status:** Architect-approved

---

## Section 1: Current Routes

Every route currently registered in `src/sentient/api/server.py` (lines 70-151):

| Method | Path | Handler | Purpose | Status |
|--------|------|---------|---------|--------|
| GET | `/` | `_placeholder_gui_html()` (line 72) | Serves inline HTML/JS/CSS for the MVS console | Works — renders a 2-column layout with chat + health/events |
| GET | `/api/health` | `get_health()` (line 78) | Full health snapshot via `HealthPulseNetwork.snapshot()` | Works — returns `{module: {latest: pulse_dict, pulse_count, status}}` |
| GET | `/api/status` | `get_status()` (line 82) | System status via `LifecycleManager.status_summary()` | Works — returns `{running: bool, modules: {name: {state, status}}}` |
| GET | `/api/memory/count` | `get_memory_count()` (line 86) | Memory module metrics via `health_pulse().metrics` | **Partially broken** — returns `{"error": "memory module not available"}` with HTTP 200 when module absent |
| GET | `/api/cognitive/recent` | `get_cognitive_recent()` (line 94) | Cognitive core metrics via `health_pulse().metrics` | **Partially broken** — same 200-on-error pattern as memory/count |
| WS | `/ws/chat` | `chat_ws()` (line 101) | Bidirectional chat messages between frontend and Thalamus | Works — accepts JSON `{text, session_id}`, sends welcome frame, forwards to `ChatInputPlugin.inject()` |
| WS | `/ws/dashboard` | `dashboard_ws()` (line 133) | Server-push health/cognitive state every 2 seconds | Works — sends `{type: "dashboard_update", health, lifecycle}` periodically + cognitive events via `_broadcast_cognitive_event()` |

### Detailed Route Analysis

#### GET / (line 72-74)

Returns `HTMLResponse` from `_placeholder_gui_html()` (lines 227-335). The inline HTML is a complete single-page console with:
- Two-column CSS grid layout (chat left, health/events right)
- WebSocket connections to `/ws/chat` and `/ws/dashboard`
- A `send()` function bound to the Send button and Enter key
- A `renderHealth()` function that renders module status dots
- A `addMsg()` function that appends messages to the chat log

#### GET /api/health (line 78-79)

Delegates to `self.health_network.snapshot()` which calls `HealthRegistry.snapshot()` (registry.py:70-79). Returns:

```json
{
  "thalamus": {
    "latest": {"module_name": "thalamus", "status": "healthy", "timestamp": 1745000000, "metrics": {...}, "notes": ""},
    "pulse_count": 42,
    "status": "healthy"
  }
}
```

No error handling if `health_network` is not initialized. No pagination.

#### GET /api/status (line 82-83)

Delegates to `self.lifecycle.status_summary()` (lifecycle.py:234-245). Returns:

```json
{
  "running": true,
  "modules": {
    "thalamus": {"state": "running", "status": "healthy"}
  }
}
```

#### GET /api/memory/count (line 86-91)

Retrieves the `memory` module via `self.lifecycle.get_module("memory")`. If the module is not registered, returns `{"error": "memory module not available"}` with HTTP 200 status. This is incorrect — it should return 503 Service Unavailable.

If the module exists, calls `memory.health_pulse().metrics`. The metrics depend on the MemoryArchitecture implementation but typically include `total_memories`, `episodic_count`, `semantic_count`, etc.

#### GET /api/cognitive/recent (line 94-98)

Same pattern as `/api/memory/count` but for `cognitive_core`. Same 200-on-error bug.

#### WS /ws/chat (line 101-130)

Flow:
1. Accepts WebSocket connection, adds to `self._chat_sockets`
2. Sends welcome frame: `{type: "system", text: "Connected to sentient framework.", timestamp: float}`
3. Loops on `websocket.receive_text()`, parsing as JSON (fallback: `{"text": raw}`)
4. Extracts `text` field, calls `self.chat_input.inject({text, timestamp, session_id})`
5. On disconnect, removes from `_chat_sockets`

No message validation, no rate limiting, no authentication, no reconnection protocol.

#### WS /ws/dashboard (line 133-151)

Flow:
1. Accepts WebSocket connection, adds to `self._dashboard_sockets`
2. Every 2 seconds, sends: `{type: "dashboard_update", timestamp: float, health: all_statuses(), lifecycle: status_summary()}`
3. Also receives cognitive events via `_broadcast_cognitive_event()` (line 211-225): `{type: "cognitive_event", event_type: str, data: dict, timestamp: float}`

No client-to-server messages are handled. The 2-second interval is hardcoded.

---

## Section 2: Frontend Expectations

### What the Inline JS Does (server.py:281-330)

**WebSocket connections (lines 287-288):**
```javascript
const chatWs = new WebSocket(`ws://${location.host}/ws/chat`);
const dashWs = new WebSocket(`ws://${location.host}/ws/dashboard`);
```

No `onclose`, `onerror`, or `onopen` handlers. No reconnection logic.

**chatWs.onmessage (lines 290-293):**
```javascript
chatWs.onmessage = (e) => {
  const msg = JSON.parse(e.data);
  addMsg(msg.sender || msg.type, msg.text, msg.timestamp);
};
```

Expects messages with `sender` and `text` fields. The `ChatOutputPlugin` sends `{type: "chat_message", sender: "sentient", text: str, timestamp: float, metadata: dict}`, so `msg.sender` resolves to `"sentient"` and `msg.text` resolves correctly.

**dashWs.onmessage (lines 295-303):**
```javascript
dashWs.onmessage = (e) => {
  const msg = JSON.parse(e.data);
  if (msg.type === 'dashboard_update') {
    renderHealth(msg.health);
  } else if (msg.type === 'cognitive_event') {
    const line = `[${new Date().toLocaleTimeString()}] ${msg.event_type}: ` +
                 `${JSON.stringify(msg.data).slice(0, 200)}\n`;
    eventsBox.textContent = line + eventsBox.textContent.slice(0, 5000);
  }
};
```

Expects two message types:
- `dashboard_update` with `msg.health` (object of `{moduleName: statusString}`)
- `cognitive_event` with `msg.event_type` (string) and `msg.data` (object)

**renderHealth() (lines 306-310):**
```javascript
function renderHealth(statuses) {
  healthList.innerHTML = Object.entries(statuses).map(([name, status]) =>
    `<div class="module-row"><span class="dot ${status}"></span>${name} (${status})</div>`
  ).join('');
}
```

Expects `statuses` as `{name: statusString}`. The `all_statuses()` method returns exactly this format. Status strings (`healthy`, `degraded`, `error`, `critical`, `unresponsive`) map to CSS classes (`.dot.healthy`, `.dot.degraded`, `.dot.error`, `.dot.unresponsive`).

**addMsg() (lines 312-318):**
```javascript
function addMsg(sender, text, ts) {
  const div = document.createElement('div');
  div.className = `msg ${sender === 'sentient' ? 'sentient' : sender === 'user' ? 'user' : 'system'}`;
  div.innerHTML = `<div class="sender">${sender}</div>${text}`;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
}
```

Renders messages with sender-based styling. Uses `innerHTML` (XSS risk with unescaped `text`, but acceptable for MVS).

**send() (lines 320-326):**
```javascript
function send() {
  const text = input.value.trim();
  if (!text) return;
  addMsg('user', text, Date.now() / 1000);
  chatWs.send(JSON.stringify({ text, session_id: 'main' }));
  input.value = '';
}
```

Sends `{text: str, session_id: 'main'}` via the chat WebSocket. No error handling if `chatWs` is not in `OPEN` state.

### Identified Broken Behaviors

| Behavior | Root Cause | Impact |
|----------|-----------|--------|
| **No POST /api/chat route** | Only WebSocket input path exists. No REST fallback. | If WS drops, user cannot send messages. No way to test chat via curl. |
| **No turn correlation** | `ChatOutputPlugin.execute()` (chat_output.py:54-60) sends `{type, sender, text, timestamp, metadata}` with no `turn_id`. `ChatInputPlugin.inject()` (chat_input.py:61-71) accepts `{text, timestamp, session_id}` with no return value. | Frontend cannot match responses to inputs. In a rapid conversation, responses may arrive out of order with no way to correlate. |
| **Recent Events panel starts empty** | `_broadcast_cognitive_event()` (line 211-225) only fires for 3 event types subscribed in `start()` (lines 171-179). The dashboard WS sends no historical events on connect. | User sees an empty events panel until a cognitive cycle completes. No way to see past events. |
| **System Health panel works** | `all_statuses()` returns `{name: statusString}`, and `renderHealth()` correctly maps this. | Functional. |
| **Chat send works over WS** | `send()` correctly formats `{text, session_id}` and `chat_ws()` (line 118-126) correctly forwards to `ChatInputPlugin.inject()`. | Functional, but no error handling for WS not in OPEN state. |
| **No reconnection logic** | No `onclose`/`onerror` handlers on either WebSocket. | Any network disruption requires a full page refresh. |
| **No XSS protection** | `addMsg()` uses `innerHTML` with unescaped `text`. | MVS-acceptable, but must be fixed in the rebuilt frontend. |
| **Memory/Cognitive endpoints return 200 on error** | Lines 88-91 and 96-98 return `{"error": "..."}` with HTTP 200. | Client cannot distinguish success from failure via status code. |
| **Dashboard push is fire-and-forget** | The 2-second interval sends regardless of client readiness. No acknowledgment protocol. | Acceptable for MVS, but not production-quality. |
| **No CORS origin restriction** | CORS middleware (lines 62-68) allows `origins=["*"]`. | Acceptable for local development, security risk in production. |

---

## Section 3: Canonical Route Table

### REST Endpoints

| Method | Path | Purpose | Request Body | Response | Notes |
|--------|------|---------|-------------|----------|-------|
| GET | `/` | Serve SPA shell (index.html) | — | HTML | Replaces `_placeholder_gui_html()` |
| GET | `/static/*` | Static assets (JS, CSS, images) | — | Files | Served via `StaticFiles` mount |
| POST | `/api/chat` | Submit a chat message | `{"message": string, "session_id?": string}` | `202 {"turn_id": string}` | Fire-and-forget; injects into Thalamus; returns immediately with turn_id |
| GET | `/api/health` | Full module health snapshot | — | `200 JSON` | Delegates to `HealthPulseNetwork.snapshot()` |
| GET | `/api/status` | System status summary | — | `200 JSON` | Delegates to `LifecycleManager.status_summary()` |
| GET | `/api/events/recent` | Last N events from ring buffer | — | `200 [{"type": string, "stage": string, "event_name": string, "data": object, "turn_id?": string, "timestamp": float}]` | Ring buffer of last 50 events; filled by event bus wildcard subscription |
| GET | `/api/turns/{turn_id}` | Get completed turn status | — | `200 {"turn_id": string, "status": "pending"|"complete"|"error", "input": string, "reply?": string, "created_at": float, "completed_at?": float}` | Polls the turn tracking map |

### WebSocket Endpoint

| Method | Path | Purpose | Direction | Notes |
|--------|------|---------|-----------|-------|
| WS | `/ws` | Unified event stream | Bidirectional | Replaces separate `/ws/chat` and `/ws/dashboard` |

#### WS /ws Message Formats

**Client -> Server:**

```json
{
  "type": "chat",
  "text": "Hello",
  "turn_id": "optional-client-side-id",
  "session_id": "main"
}
```

**Server -> Client — Event (system events):**

```json
{
  "type": "event",
  "stage": "thalamus",
  "event_name": "input.received",
  "data": {"envelope_id": "...", "source_type": "chat", "priority": 2},
  "turn_id": "optional-correlation-id",
  "timestamp": 1745000000.123
}
```

**Server -> Client — Reply (complete response):**

```json
{
  "type": "reply",
  "turn_id": "abc-123",
  "text": "I understand your message...",
  "done": true,
  "timestamp": 1745000001.456
}
```

**Server -> Client — Reply Chunk (streaming):**

```json
{
  "type": "reply_chunk",
  "turn_id": "abc-123",
  "text": "I understand",
  "done": false,
  "timestamp": 1745000001.100
}
```

**Server -> Client — Health Snapshot (sent on connect and periodically):**

```json
{
  "type": "health",
  "data": {"thalamus": {"latest": {...}, "pulse_count": 42, "status": "healthy"}, ...},
  "timestamp": 1745000000.0
}
```

**Server -> Client — Welcome (sent immediately on connect):**

```json
{
  "type": "welcome",
  "text": "Connected to Sentient Framework.",
  "timestamp": 1745000000.0
}
```

### Data Structures

#### Turn Tracking Map (in-memory)

```python
_turns: dict[str, TurnRecord] = {}
# TurnRecord:
#   turn_id: str          # UUID
#   status: str           # "pending" | "complete" | "error"
#   input_text: str       # Original user message
#   reply_text: str       # Accumulated reply text (if any)
#   created_at: float     # Unix timestamp
#   completed_at: float   # Unix timestamp (when reply arrived)
#   events: list[dict]    # Events associated with this turn
```

- Turn records are created when POST `/api/chat` is called.
- Turn records are updated when `ChatOutputPlugin` delivers a response via the event bus or outgoing queue.
- Turn records expire after 300 seconds (5 minutes) to prevent unbounded memory growth.
- The `turn_id` is propagated through the `Envelope.metadata` field so that the Brainstem can attach it to the response.

#### Event Ring Buffer (in-memory)

```python
_event_buffer: deque[dict] = deque(maxlen=50)
```

- Filled by an event bus wildcard subscription (`"*"`).
- Each event is stored as `{type: "event", stage: str, event_name: str, data: dict, turn_id?: str, timestamp: float}`.
- Served via GET `/api/events/recent` and pushed to connected WS clients.
- The `stage` field is derived from the event_name prefix (e.g., `input.received` -> `thalamus`, `cognitive.cycle.complete` -> `cognitive_core`, `action.executed` -> `brainstem`).

#### Stage Mapping (event_name prefix -> stage)

| Event Prefix | Stage |
|-------------|-------|
| `input.*` | `thalamus` |
| `checkpost.*` | `checkpost` |
| `tlp.*` | `tlp` |
| `cognitive.*` | `cognitive_core` |
| `decision.*` | `world_model` |
| `action.*` | `brainstem` |
| `memory.*` | `memory` |
| `health.*` | `health` |
| `sleep.*` | `sleep` |
| `attention.*` | `frontal` |
| `lifecycle.*` | `lifecycle` |
| `harness.*` | `harness` |

---

## Section 4: Architect Sign-off

**Approved by:** Architect (GLM-5.1)
**Date:** 2026-04-18

### Design Decisions

1. **Unified WS `/ws` replaces separate `/ws/chat` and `/ws/dashboard`.** The dual-connection model forces the frontend to manage two WebSocket lifecycles independently, with no shared reconnection state. A single connection simplifies the client, reduces server resource usage (one FD per client instead of two), and enables turn correlation across event and reply messages. The trade-off is that a single overloaded connection cannot be prioritized separately, but for an MVS console this is acceptable.

2. **POST /api/chat is fire-and-forget (returns 202 immediately).** The endpoint creates a turn record, injects the message into Thalamus via `ChatInputPlugin.inject()`, and returns the `turn_id` without waiting for a response. This decouples the HTTP layer from the cognitive pipeline latency (which can be 5-30 seconds for a full cycle). The client receives the response via the WebSocket `/ws` stream. The 202 status code explicitly signals "accepted but not yet processed."

3. **Event ring buffer for `/api/events/recent` (last 50 events).** A `deque(maxlen=50)` provides bounded memory usage and immediate historical context for the frontend on page load or reconnection. 50 events covers approximately 2-5 minutes of system activity at typical event rates. The buffer is populated by a wildcard event bus subscription, so it captures all system events without requiring individual subscriptions. The trade-off is no persistence across server restarts, but this is acceptable for a development console.

4. **Turn tracking map for `/api/turns/{turn_id}`.** A simple `dict[str, TurnRecord]` with a 300-second TTL allows the frontend to poll for turn completion status. This is essential for cases where the WebSocket connection drops mid-conversation: the client can reconnect, request `/api/events/recent` to catch up, and then poll `/api/turns/{turn_id}` for any in-flight turns. The trade-off is in-memory storage (no persistence across restarts), but turn records are ephemeral by nature.

5. **Connection state management (exponential backoff, max 5 retries).** The frontend JS must implement:
   - `onclose`: Attempt reconnection with exponential backoff (1s, 2s, 4s, 8s, 16s).
   - `onerror`: Log and attempt reconnection.
   - Max 5 retry attempts before showing a "Connection lost" banner.
   - On successful reconnection, immediately request `/api/events/recent` to catch up.
   - This applies only to the single `/ws` connection.

### Out of Scope for This Phase

- Authentication/authorization (all endpoints are open in MVS).
- Rate limiting on POST `/api/chat` (the Brainstem already has rate limiting at `_check_rate_limit()`).
- Persistent event storage (ring buffer is in-memory only).
- Streaming reply chunks via POST (streaming only available via WS).
- HTTPS/TLS (local development only).

### References

- `src/sentient/api/server.py:70-151` — Current route registrations
- `src/sentient/api/server.py:227-335` — Inline HTML/JS frontend
- `src/sentient/api/server.py:193-209` — `_drain_outgoing()` output loop
- `src/sentient/brainstem/plugins/chat_output.py:39-78` — ChatOutputPlugin queue message format
- `src/sentient/thalamus/plugins/chat_input.py:61-71` — ChatInputPlugin.inject() entry point
- `src/sentient/core/event_bus.py:22-51` — Complete event type list
- `src/sentient/core/event_bus.py:111-124` — Wildcard subscription support
- `src/sentient/health/registry.py:70-86` — snapshot() and all_statuses()
- `src/sentient/core/lifecycle.py:234-245` — status_summary()
- `src/sentient/core/envelope.py:62-173` — Envelope dataclass with metadata field for turn_id propagation
- `src/sentient/main.py:179-188` — APIServer instantiation
