"""FastAPI server — unified WebSocket + REST endpoints.

Per ARCHITECTURE.md §9.3, this layer bridges the System GUI (React
frontend) to the backend framework. A single WebSocket endpoint `/ws`
handles bidirectional event streaming. REST endpoints provide health,
status, and turn tracking.

REST endpoints:
  - GET  /                      — serves SPA shell (placeholder HTML for now)
  - GET  /static/{path}          — static assets
  - POST /api/chat               — fire-and-forget message submission
  - GET  /api/health             — full health snapshot
  - GET  /api/status             — system status summary
  - GET  /api/events/recent      — last 50 events from ring buffer
  - GET  /api/turns/{turn_id}    — completed turn record
  - GET  /api/memory/count       — memory statistics
  - GET  /api/cognitive/recent   — recent reasoning cycles

WebSocket /ws streams events, replies, and health snapshots.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections import deque
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from sentient.core.event_bus import EventBus, get_event_bus

logger = logging.getLogger(__name__)


class TurnRecord:
    """Tracks a single user turn from input to output."""

    def __init__(self, turn_id: str, user_message: str, timestamp: float):
        self.turn_id = turn_id
        self.user_message = user_message
        self.assistant_reply: str = ""
        self.events: list[dict] = []
        self.started_at = timestamp
        self.completed_at: float | None = None
        self.is_complete = False


class APIServer:
    """FastAPI server managing unified WebSocket + REST endpoints."""

    def __init__(
        self,
        config: dict[str, Any],
        lifecycle_manager: Any,
        chat_input_plugin: Any,
        chat_output_plugin: Any,
        health_pulse_network: Any,
        event_bus: EventBus | None = None,
    ) -> None:
        self.config = config
        self.event_bus = event_bus or get_event_bus()
        self.lifecycle = lifecycle_manager
        self.chat_input = chat_input_plugin
        self.chat_output = chat_output_plugin
        self.health_network = health_pulse_network

        self.host = config.get("host", "127.0.0.1")
        self.port = config.get("port", 8765)

        self.app = FastAPI(title="Sentient AI Framework", version="0.1.0-mvs")
        self._ws_clients: set[WebSocket] = set()
        self._server_task: asyncio.Task | None = None
        self._outgoing_drain_task: asyncio.Task | None = None

        # Turn tracking
        self._turn_records: dict[str, TurnRecord] = {}
        self._turn_ttl_seconds = 300  # 5-minute TTL for turn records

        # Event ring buffer
        self._event_buffer: deque[dict] = deque(maxlen=50)

        # Cleanup task
        self._cleanup_task: asyncio.Task | None = None

        self._configure_middleware()
        self._register_routes()

    def _configure_middleware(self) -> None:
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def _register_routes(self) -> None:
        # === Root — serves a minimal GUI placeholder ===
        @self.app.get("/", response_class=HTMLResponse)
        async def root():
            return self._placeholder_gui_html()

        # === Static files ===
        @self.app.get("/static/{path:path}")
        async def serve_static(path: str):
            # Delegate to static files mount (added in start() if static_dir exists)
            from fastapi.responses import FileResponse
            static_dir = self.config.get("static_dir", "static")
            file_path = Path(static_dir) / path
            if file_path.is_file():
                return FileResponse(str(file_path))
            return JSONResponse({"error": "not found"}, status_code=404)

        # === REST endpoints ===
        @self.app.get("/api/health")
        async def get_health():
            return self.health_network.snapshot()

        @self.app.get("/api/status")
        async def get_status():
            return self.lifecycle.status_summary()

        @self.app.post("/api/chat")
        async def post_chat(request: dict) -> dict:
            message = request.get("message", "").strip()
            if not message:
                return JSONResponse({"error": "message is required"}, status_code=400)

            turn_id = str(uuid.uuid4())
            timestamp = time.time()

            # Create turn record
            self._turn_records[turn_id] = TurnRecord(turn_id, message, timestamp)

            # Inject into Thalamus
            await self.chat_input.inject({
                "text": message,
                "timestamp": timestamp,
                "session_id": request.get("session_id", f"turn_{turn_id}"),
                "turn_id": turn_id,
            })

            # Publish event
            await self.event_bus.publish("chat.input.received", {
                "turn_id": turn_id,
                "text": message,
                "timestamp": timestamp,
            })

            return JSONResponse({"turn_id": turn_id, "status": "accepted"}, status_code=202)

        @self.app.get("/api/events/recent")
        async def get_recent_events():
            return list(self._event_buffer)

        @self.app.get("/api/turns/{turn_id}")
        async def get_turn(turn_id: str):
            record = self._turn_records.get(turn_id)
            if record is None:
                return JSONResponse({"error": "turn not found"}, status_code=404)
            return {
                "turn_id": record.turn_id,
                "user_message": record.user_message,
                "assistant_reply": record.assistant_reply,
                "events": record.events,
                "started_at": record.started_at,
                "completed_at": record.completed_at,
                "is_complete": record.is_complete,
            }

        @self.app.get("/api/memory/count")
        async def get_memory_count():
            memory = self.lifecycle.get_module("memory")
            if memory is None:
                return {"error": "memory module not available"}
            pulse = memory.health_pulse()
            return pulse.metrics

        @self.app.get("/api/cognitive/recent")
        async def get_cognitive_recent():
            cognitive = self.lifecycle.get_module("cognitive_core")
            if cognitive is None:
                return {"error": "cognitive core not available"}
            return cognitive.health_pulse().metrics

        # === Unified WebSocket /ws ===
        @self.app.websocket("/ws")
        async def unified_ws(websocket: WebSocket):
            await websocket.accept()
            self._ws_clients.add(websocket)
            try:
                # Send health snapshot on connect
                health = self.health_network.snapshot()
                await websocket.send_json({
                    "type": "health",
                    "data": health,
                    "timestamp": time.time(),
                })

                # Send welcome message
                await websocket.send_json({
                    "type": "welcome",
                    "text": "Connected to Sentient Framework.",
                    "timestamp": time.time(),
                })

                # Send recent events for backfill
                for event in list(self._event_buffer):
                    await websocket.send_json(event)

                # Keep connection alive
                while True:
                    try:
                        data = await websocket.receive_text()
                        try:
                            parsed = json.loads(data)
                            result = await self._handle_ws_message(parsed, time.time())
                            if result:
                                await websocket.send_json(result)
                        except json.JSONDecodeError:
                            pass
                    except WebSocketDisconnect:
                        break
            finally:
                self._ws_clients.discard(websocket)

    async def _handle_ws_message(self, parsed: dict, timestamp: float) -> dict | None:
        """Handle a single WebSocket message. Returns response message or None."""
        msg_type = parsed.get("type")

        if msg_type == "ping":
            return {
                "type": "pong",
                "timestamp": timestamp,
            }

        if msg_type == "chat":
            # Forward chat message to Thalamus
            text = parsed.get("text", "").strip()
            if text:
                turn_id = parsed.get("turn_id") or str(uuid.uuid4())
                # Create turn record if not exists
                if turn_id not in self._turn_records:
                    self._turn_records[turn_id] = TurnRecord(turn_id, text, timestamp)
                await self.chat_input.inject(
                    {
                        "text": text,
                        "timestamp": timestamp,
                        "session_id": parsed.get("session_id", "main"),
                        "turn_id": turn_id,
                    }
                )
                await self.event_bus.publish(
                    "chat.input.received",
                    {"turn_id": turn_id, "text": text, "timestamp": timestamp},
                )
        return None

    # === Lifecycle ===

    async def start(self) -> None:
        """Start the FastAPI server and the chat-output drain task."""
        import uvicorn

        # Subscribe to all events for WS broadcasting
        await self.event_bus.subscribe("*", self._broadcast_event)

        # Start cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_turn_records())

        config = uvicorn.Config(
            app=self.app,
            host=self.host,
            port=self.port,
            log_level="info",
            access_log=False,
        )
        server = uvicorn.Server(config)
        self._server_task = asyncio.create_task(server.serve())
        self._outgoing_drain_task = asyncio.create_task(self._drain_outgoing())

        logger.info("API server started on http://%s:%d", self.host, self.port)

    async def shutdown(self) -> None:
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        if self._outgoing_drain_task:
            self._outgoing_drain_task.cancel()
        if self._server_task:
            self._server_task.cancel()
            try:
                await self._server_task
            except asyncio.CancelledError:
                pass

    async def _drain_outgoing(self) -> None:
        """Drain chat_output's queue, forwarding messages to connected sockets."""
        while True:
            try:
                message = await self.chat_output.outgoing_queue.get()

                # Extract turn_id from message if present
                turn_id = (
                    message.get("turn_id")
                    or message.get("session_id", "").replace("turn_", "")
                )

                # Forward to WS clients as reply
                reply_msg = {
                    "type": "reply",
                    "turn_id": turn_id,
                    "text": message.get("text", ""),
                    "done": True,
                    "timestamp": time.time(),
                }

                dead = set()
                for ws in self._ws_clients:
                    try:
                        await ws.send_json(reply_msg)
                    except Exception:
                        dead.add(ws)
                self._ws_clients -= dead

                # Update turn record
                if turn_id and turn_id in self._turn_records:
                    record = self._turn_records[turn_id]
                    record.assistant_reply = message.get("text", "")
                    record.completed_at = time.time()
                    record.is_complete = True

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.exception("Chat output drain error: %s", exc)

    async def _broadcast_event(self, payload: dict[str, Any]) -> None:
        """Broadcast any event to all WS clients and store in ring buffer."""
        event_name = payload.get("event_type", "unknown")
        turn_id = payload.get("turn_id")
        timestamp = payload.get("timestamp", time.time())

        # Determine stage from event prefix
        stage = self._map_event_to_stage(event_name)

        event_msg = {
            "type": "event",
            "stage": stage,
            "event_name": event_name,
            "data": payload,
            "turn_id": turn_id,
            "timestamp": timestamp,
        }

        # Store in ring buffer
        self._event_buffer.append(event_msg)

        # Broadcast to all WS clients
        dead = set()
        for ws in self._ws_clients:
            try:
                await ws.send_json(event_msg)
            except Exception:
                dead.add(ws)
        self._ws_clients -= dead

        # Track in turn record if applicable
        if turn_id and turn_id in self._turn_records:
            self._turn_records[turn_id].events.append(event_msg)

    def _map_event_to_stage(self, event_name: str) -> str:
        """Map event name prefix to human-readable stage."""
        prefix_map = {
            "input": "thalamus",
            "thalamus": "thalamus",
            "checkpost": "checkpost",
            "queue": "queue_zone",
            "tlp": "tlp",
            "cognitive": "cognitive_core",
            "decision": "world_model",
            "action": "brainstem",
            "memory": "memory",
            "sleep": "sleep",
            "health": "health",
            "attention": "frontal",
            "chat": "chat",
            "lifecycle": "lifecycle",
            "harness": "harness",
        }
        for prefix, stage in prefix_map.items():
            if event_name.startswith(prefix):
                return stage
        return "system"

    async def _cleanup_turn_records(self) -> None:
        """Periodically remove expired turn records."""
        while True:
            try:
                await asyncio.sleep(60)
                self._do_cleanup_iteration()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.exception("Cleanup task error: %s", exc)

    def _do_cleanup_iteration(self) -> None:
        """Perform one iteration of turn record cleanup."""
        now = time.time()
        expired = [
            tid
            for tid, rec in self._turn_records.items()
            if now - rec.started_at > self._turn_ttl_seconds
        ]
        for tid in expired:
            del self._turn_records[tid]

    def _placeholder_gui_html(self) -> str:
        """Minimal HTML GUI for MVS testing.

        Phase 2+ replaces this with a proper React application.
        """
        return """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Sentient — MVS Console</title>
<style>
  body { background: #111; color: #eee; font-family: ui-monospace, monospace;
         margin: 0; padding: 1rem; display: grid; grid-template-columns: 2fr 1fr; gap: 1rem; height: 100vh; box-sizing: border-box; }
  .panel { background: #1c1c1c; border: 1px solid #333; border-radius: 4px; padding: 1rem;
           display: flex; flex-direction: column; overflow: hidden; }
  h2 { margin: 0 0 1rem 0; font-size: 14px; color: #8af; text-transform: uppercase; letter-spacing: 0.1em; }
  #chat-log { flex: 1; overflow-y: auto; font-size: 14px; line-height: 1.5; }
  .msg { margin-bottom: 0.5rem; padding: 0.5rem; border-radius: 3px; }
  .msg.user { background: #1a2a3a; }
  .msg.sentient { background: #2a1a2a; }
  .msg.system { background: #222; color: #888; font-style: italic; }
  .msg .sender { font-weight: bold; color: #8af; font-size: 11px; text-transform: uppercase; }
  .msg.sentient .sender { color: #c8f; }
  #input-row { display: flex; margin-top: 0.5rem; gap: 0.5rem; }
  #input { flex: 1; background: #222; color: #eee; border: 1px solid #444; padding: 0.5rem; border-radius: 3px; font-family: inherit; }
  button { background: #2a4a7a; color: #fff; border: 0; padding: 0.5rem 1rem; border-radius: 3px; cursor: pointer; }
  button:hover { background: #3a5a8a; }
  pre { background: #0a0a0a; padding: 0.5rem; overflow: auto; font-size: 11px; margin: 0; flex: 1; }
  .dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 0.5rem; }
  .dot.healthy { background: #4a4; }
  .dot.degraded { background: #aa4; }
  .dot.error { background: #a44; }
  .dot.unresponsive { background: #666; }
  .module-row { font-size: 12px; margin-bottom: 0.2rem; }
</style>
</head>
<body>

<div class="panel">
<h2>Chat with Sentient</h2>
<div id="chat-log"></div>
<div id="input-row">
  <input id="input" placeholder="Type a message..." autofocus>
  <button onclick="send()">Send</button>
</div>
</div>

<div class="panel">
<h2>System Health</h2>
<div id="health-list" style="margin-bottom: 1rem;"></div>
<h2>Recent Events</h2>
<pre id="events"></pre>
</div>

<script>
const log = document.getElementById('chat-log');
const input = document.getElementById('input');
const healthList = document.getElementById('health-list');
const eventsBox = document.getElementById('events');

let ws;
let reconnectAttempts = 0;
const maxRetries = 5;

function connect() {
  ws = new WebSocket(`ws://${location.host}/ws`);

  ws.onopen = () => {
    reconnectAttempts = 0;
  };

  ws.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    if (msg.type === 'health') {
      renderHealth(msg.data);
    } else if (msg.type === 'reply') {
      addMsg('sentient', msg.text, msg.timestamp);
    } else if (msg.type === 'event') {
      const line = `[${new Date().toLocaleTimeString()}] ${msg.event_name}: ` +
                   `${JSON.stringify(msg.data).slice(0, 200)}\n`;
      eventsBox.textContent = line + eventsBox.textContent.slice(0, 5000);
    }
  };

  ws.onclose = () => {
    if (reconnectAttempts < maxRetries) {
      reconnectAttempts++;
      const delay = Math.pow(2, reconnectAttempts) * 1000;
      setTimeout(connect, delay);
    }
  };

  ws.onerror = (err) => {
    console.error('WS error', err);
  };
}

connect();

function renderHealth(statuses) {
  healthList.innerHTML = Object.entries(statuses).map(([name, data]) =>
    `<div class="module-row"><span class="dot ${data.status}"></span>${name} (${data.status})</div>`
  ).join('');
}

function addMsg(sender, text, ts) {
  const div = document.createElement('div');
  div.className = `msg ${sender === 'sentient' ? 'sentient' : sender === 'user' ? 'user' : 'system'}`;
  div.innerHTML = `<div class="sender">${sender}</div>${text}`;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
}

function send() {
  const text = input.value.trim();
  if (!text || !ws || ws.readyState !== WebSocket.OPEN) return;
  addMsg('user', text, Date.now() / 1000);
  ws.send(JSON.stringify({ type: 'chat', text, session_id: 'main' }));
  input.value = '';
}

input.addEventListener('keypress', (e) => {
  if (e.key === 'Enter') send();
});
</script>

</body>
</html>"""