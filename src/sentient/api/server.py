"""FastAPI server — chat WebSocket + dashboard REST/WebSocket.

Per ARCHITECTURE.md §9.3, this layer bridges the System GUI (React
frontend) to the backend framework. Two WebSocket streams:
  - /ws/chat         — bidirectional chat messages
  - /ws/dashboard    — live system state (health, cognitive state, memory)

REST endpoints:
  - GET /api/health          — full health snapshot
  - GET /api/status          — system status summary
  - GET /api/memory/count    — memory statistics
  - GET /api/cognitive/recent — recent reasoning cycles
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from sentient.core.event_bus import EventBus, get_event_bus
from sentient.core.module_interface import ModuleStatus

logger = logging.getLogger(__name__)


class APIServer:
    """FastAPI server managing WebSocket + REST endpoints."""

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
        self._chat_sockets: set[WebSocket] = set()
        self._dashboard_sockets: set[WebSocket] = set()
        self._server_task: asyncio.Task | None = None
        self._outgoing_drain_task: asyncio.Task | None = None

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

        # === REST endpoints ===
        @self.app.get("/api/health")
        async def get_health():
            return self.health_network.snapshot()

        @self.app.get("/api/status")
        async def get_status():
            return self.lifecycle.status_summary()

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

        # === Chat WebSocket ===
        @self.app.websocket("/ws/chat")
        async def chat_ws(websocket: WebSocket):
            await websocket.accept()
            self._chat_sockets.add(websocket)
            try:
                # Send welcome frame
                await websocket.send_json({
                    "type": "system",
                    "text": "Connected to sentient framework.",
                    "timestamp": time.time(),
                })
                while True:
                    raw = await websocket.receive_text()
                    try:
                        data = json.loads(raw)
                    except json.JSONDecodeError:
                        data = {"text": raw}

                    text = data.get("text", "").strip()
                    if text:
                        # Forward to Thalamus via chat input plugin
                        await self.chat_input.inject({
                            "text": text,
                            "timestamp": time.time(),
                            "session_id": data.get("session_id"),
                        })
            except WebSocketDisconnect:
                pass
            finally:
                self._chat_sockets.discard(websocket)

        # === Dashboard WebSocket ===
        @self.app.websocket("/ws/dashboard")
        async def dashboard_ws(websocket: WebSocket):
            await websocket.accept()
            self._dashboard_sockets.add(websocket)
            try:
                while True:
                    # Send periodic updates
                    await asyncio.sleep(2)
                    snapshot = {
                        "type": "dashboard_update",
                        "timestamp": time.time(),
                        "health": self.health_network.all_statuses(),
                        "lifecycle": self.lifecycle.status_summary(),
                    }
                    await websocket.send_json(snapshot)
            except WebSocketDisconnect:
                pass
            finally:
                self._dashboard_sockets.discard(websocket)

    # === Lifecycle ===

    async def start(self) -> None:
        """Start the FastAPI server and the chat-output drain task."""
        import uvicorn

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

        # Subscribe to cognitive events for dashboard streaming
        await self.event_bus.subscribe(
            "cognitive.cycle.complete", self._broadcast_cognitive_event,
        )
        await self.event_bus.subscribe(
            "cognitive.daydream.start", self._broadcast_cognitive_event,
        )
        await self.event_bus.subscribe(
            "cognitive.daydream.end", self._broadcast_cognitive_event,
        )

        logger.info("API server started on http://%s:%d", self.host, self.port)

    async def shutdown(self) -> None:
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
                # Broadcast to all connected chat sockets
                dead_sockets = set()
                for socket in self._chat_sockets:
                    try:
                        await socket.send_json(message)
                    except Exception:
                        dead_sockets.add(socket)
                self._chat_sockets -= dead_sockets
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.exception("Chat output drain error: %s", exc)

    async def _broadcast_cognitive_event(self, payload: dict[str, Any]) -> None:
        """Send cognitive events to dashboard sockets."""
        event = {
            "type": "cognitive_event",
            "event_type": payload.get("event_type"),
            "data": payload,
            "timestamp": time.time(),
        }
        dead = set()
        for socket in self._dashboard_sockets:
            try:
                await socket.send_json(event)
            except Exception:
                dead.add(socket)
        self._dashboard_sockets -= dead

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

const chatWs = new WebSocket(`ws://${location.host}/ws/chat`);
const dashWs = new WebSocket(`ws://${location.host}/ws/dashboard`);

chatWs.onmessage = (e) => {
  const msg = JSON.parse(e.data);
  addMsg(msg.sender || msg.type, msg.text, msg.timestamp);
};

dashWs.onmessage = (e) => {
  const msg = JSON.parse(e.data);
  if (msg.type === 'dashboard_update') {
    renderHealth(msg.health);
  } else if (msg.type === 'cognitive_event') {
    const line = `[${new Date().toLocaleTimeString()}] ${msg.event_type}: ` +
                 `${JSON.stringify(msg.data).slice(0, 200)}\\n`;
    eventsBox.textContent = line + eventsBox.textContent.slice(0, 5000);
  }
};

function renderHealth(statuses) {
  healthList.innerHTML = Object.entries(statuses).map(([name, status]) =>
    `<div class="module-row"><span class="dot ${status}"></span>${name} (${status})</div>`
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
  if (!text) return;
  addMsg('user', text, Date.now() / 1000);
  chatWs.send(JSON.stringify({ text, session_id: 'main' }));
  input.value = '';
}

input.addEventListener('keypress', (e) => {
  if (e.key === 'Enter') send();
});
</script>

</body>
</html>"""
