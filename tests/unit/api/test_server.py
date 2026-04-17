"""Unit tests for sentient.api.server."""
from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from sentient.api.server import APIServer


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_lifecycle():
    """Lifecycle manager with status_summary and get_module."""
    lifecycle = MagicMock()
    lifecycle.status_summary.return_value = {
        "phase": "running",
        "modules": ["memory", "cognitive_core"],
    }
    lifecycle.get_module.return_value = None
    return lifecycle


@pytest.fixture
def mock_chat_input():
    """Chat input plugin with async inject method."""
    chat_input = AsyncMock()
    return chat_input


@pytest.fixture
def mock_chat_output():
    """Chat output plugin with outgoing_queue."""
    chat_output = MagicMock()
    chat_output.outgoing_queue = asyncio.Queue()
    return chat_output


@pytest.fixture
def mock_health_network():
    """Health pulse network with snapshot and all_statuses."""
    health_network = MagicMock()
    health_network.snapshot.return_value = {
        "status": "healthy",
        "modules": {"memory": "healthy", "cognitive_core": "healthy"},
    }
    health_network.all_statuses.return_value = {
        "memory": "healthy",
        "cognitive_core": "healthy",
    }
    return health_network


@pytest.fixture
def mock_event_bus():
    """Mock event bus with async subscribe."""
    bus = AsyncMock()
    return bus


@pytest.fixture
def server(mock_lifecycle, mock_chat_input, mock_chat_output, mock_health_network, mock_event_bus):
    """Construct APIServer with all mocks."""
    config = {"host": "127.0.0.1", "port": 8765}
    return APIServer(
        config,
        mock_lifecycle,
        mock_chat_input,
        mock_chat_output,
        mock_health_network,
        event_bus=mock_event_bus,
    )


@pytest.fixture
def client(server):
    """TestClient attached to the server app."""
    return TestClient(server.app)


# ---------------------------------------------------------------------------
# REST endpoint tests
# ---------------------------------------------------------------------------


def test_get_root_returns_html(client):
    """GET / returns HTML placeholder with status 200."""
    response = client.get("/")
    assert response.status_code == 200
    assert "<!DOCTYPE html>" in response.text
    assert "Sentient" in response.text


def test_get_health_returns_snapshot(client, mock_health_network):
    """GET /api/health returns health_network.snapshot()."""
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == mock_health_network.snapshot.return_value
    mock_health_network.snapshot.assert_called_once()


def test_get_status_returns_lifecycle_summary(client, mock_lifecycle):
    """GET /api/status returns lifecycle.status_summary()."""
    response = client.get("/api/status")
    assert response.status_code == 200
    assert response.json() == mock_lifecycle.status_summary.return_value
    mock_lifecycle.status_summary.assert_called_once()


def test_get_memory_count_with_module(client, mock_lifecycle):
    """GET /api/memory/count returns metrics when memory module is present."""
    mock_memory = MagicMock()
    mock_memory.health_pulse.return_value = MagicMock(metrics={"entries": 42})
    mock_lifecycle.get_module.return_value = mock_memory

    response = client.get("/api/memory/count")
    assert response.status_code == 200
    assert response.json() == {"entries": 42}
    mock_lifecycle.get_module.assert_called_once_with("memory")


def test_get_memory_count_without_module(client, mock_lifecycle):
    """GET /api/memory/count returns error dict when memory module is absent."""
    mock_lifecycle.get_module.return_value = None

    response = client.get("/api/memory/count")
    assert response.status_code == 200
    assert response.json() == {"error": "memory module not available"}


def test_get_cognitive_recent_with_module(client, mock_lifecycle):
    """GET /api/cognitive/recent returns metrics when cognitive_core is present."""
    mock_cognitive = MagicMock()
    mock_cognitive.health_pulse.return_value = MagicMock(
        metrics={"cycles": 10, "last_reasoning": "2026-04-17T12:00:00Z"}
    )
    mock_lifecycle.get_module.return_value = mock_cognitive

    response = client.get("/api/cognitive/recent")
    assert response.status_code == 200
    assert response.json() == {"cycles": 10, "last_reasoning": "2026-04-17T12:00:00Z"}
    mock_lifecycle.get_module.assert_called_once_with("cognitive_core")


def test_get_cognitive_recent_without_module(client, mock_lifecycle):
    """GET /api/cognitive/recent returns error dict when cognitive_core is absent."""
    mock_lifecycle.get_module.return_value = None

    response = client.get("/api/cognitive/recent")
    assert response.status_code == 200
    assert response.json() == {"error": "cognitive core not available"}


# ---------------------------------------------------------------------------
# WebSocket endpoint tests
# ---------------------------------------------------------------------------


def test_ws_chat_connect_sends_welcome_message(client):
    """Connecting to /ws/chat receives a welcome JSON message."""
    with client.websocket_connect("/ws/chat") as websocket:
        data = websocket.receive_json()
        assert data["type"] == "system"
        assert "Connected to sentient framework" in data["text"]
        assert "timestamp" in data


def test_ws_chat_send_text_calls_inject(client, mock_chat_input):
    """Sending text over /ws/chat triggers chat_input.inject()."""
    with client.websocket_connect("/ws/chat") as websocket:
        # Clear the welcome message
        websocket.receive_json()

        websocket.send_json({"text": "hello world", "session_id": "test-session"})
        # Allow event loop to process
        time.sleep(0.05)

    mock_chat_input.inject.assert_called_once()
    call_args = mock_chat_input.inject.call_args[0][0]
    assert call_args["text"] == "hello world"
    assert call_args["session_id"] == "test-session"
    assert "timestamp" in call_args


def test_ws_chat_non_json_text_treated_as_text(client, mock_chat_input):
    """Non-JSON text sent to /ws/chat is treated as {"text": <raw>}."""
    mock_lifecycle = MagicMock()
    mock_lifecycle.status_summary.return_value = {}
    mock_lifecycle.get_module.return_value = None

    mock_health_network = MagicMock()
    mock_health_network.snapshot.return_value = {}
    mock_health_network.all_statuses.return_value = {}

    with client.websocket_connect("/ws/chat") as websocket:
        websocket.receive_json()  # welcome
        websocket.send_text("plain text message")

    # Should still call inject with {"text": "plain text message"}
    mock_chat_input.inject.assert_called_once()
    assert mock_chat_input.inject.call_args[0][0]["text"] == "plain text message"


def test_ws_chat_empty_text_not_forwarded(client, mock_chat_input):
    """Whitespace-only text is not forwarded to chat_input.inject()."""
    with client.websocket_connect("/ws/chat") as websocket:
        websocket.receive_json()  # welcome
        websocket.send_json({"text": "   ", "session_id": "s"})
        time.sleep(0.05)

    mock_chat_input.inject.assert_not_called()


def test_ws_chat_disconnect_removes_socket(client, server, mock_chat_input):
    """WebSocket disconnect removes the socket from tracking set."""
    ws = client.websocket_connect("/ws/chat")
    ws.__enter__()
    ws.receive_json()  # welcome
    ws.close()
    # Allow event loop to process the WebSocketDisconnect exception in the handler
    time.sleep(0.05)
    # Socket should be removed from _chat_sockets
    assert len(server._chat_sockets) == 0


def test_ws_dashboard_connect_accepts_and_tracks(client, server):
    """Connecting to /ws/dashboard adds socket to tracking set."""
    ws = client.websocket_connect("/ws/dashboard")
    ws.__enter__()
    assert len(server._dashboard_sockets) == 1
    ws.close()


# ---------------------------------------------------------------------------
# Lifecycle method tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_creates_server_and_drain_tasks(
    mock_lifecycle, mock_chat_input, mock_chat_output, mock_health_network, mock_event_bus
):
    """start() creates _server_task and _outgoing_drain_task."""
    config = {"host": "127.0.0.1", "port": 8765}
    srv = APIServer(
        config,
        mock_lifecycle,
        mock_chat_input,
        mock_chat_output,
        mock_health_network,
        event_bus=mock_event_bus,
    )

    # Use an unuasigned port so uvicorn doesn't actually bind
    srv.port = 0

    await srv.start()

    try:
        assert srv._server_task is not None
        assert srv._outgoing_drain_task is not None
    finally:
        await srv.shutdown()


@pytest.mark.asyncio
async def test_start_subscribes_to_cognitive_events(
    mock_lifecycle, mock_chat_input, mock_chat_output, mock_health_network, mock_event_bus
):
    """start() subscribes to cognitive event topics on the event bus."""
    config = {"host": "127.0.0.1", "port": 8765}
    srv = APIServer(
        config,
        mock_lifecycle,
        mock_chat_input,
        mock_chat_output,
        mock_health_network,
        event_bus=mock_event_bus,
    )
    srv.port = 0  # use unassigned port

    await srv.start()
    await srv.shutdown()

    # Three topics subscribed
    assert mock_event_bus.subscribe.call_count == 3
    subscribed_topics = [
        call_args[0][0] for call_args in mock_event_bus.subscribe.call_args_list
    ]
    assert "cognitive.cycle.complete" in subscribed_topics
    assert "cognitive.daydream.start" in subscribed_topics
    assert "cognitive.daydream.end" in subscribed_topics


@pytest.mark.asyncio
async def test_shutdown_cancels_tasks(
    mock_lifecycle, mock_chat_input, mock_chat_output, mock_health_network, mock_event_bus
):
    """shutdown() cancels _server_task and _outgoing_drain_task."""
    config = {"host": "127.0.0.1", "port": 8765}
    srv = APIServer(
        config,
        mock_lifecycle,
        mock_chat_input,
        mock_chat_output,
        mock_health_network,
        event_bus=mock_event_bus,
    )
    srv.port = 0  # use unassigned port

    await srv.start()
    server_task = srv._server_task
    drain_task = srv._outgoing_drain_task

    await srv.shutdown()

    # Tasks should be cancelled
    assert server_task.cancelled() or server_task.done()
    assert drain_task.cancelled() or drain_task.done()

# ---------------------------------------------------------------------------
# Internal method tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_drain_outgoing_broadcasts_to_chat_sockets(
    mock_lifecycle, mock_chat_input, mock_chat_output, mock_health_network, mock_event_bus
):
    """_drain_outgoing reads queue and sends to all chat sockets."""
    config = {"host": "127.0.0.1", "port": 8765}
    srv = APIServer(
        config,
        mock_lifecycle,
        mock_chat_input,
        mock_chat_output,
        mock_health_network,
        event_bus=mock_event_bus,
    )

    # Use TestClient to get a real websocket connected
    test_client = TestClient(srv.app)
    ws = test_client.websocket_connect("/ws/chat")
    ws.__enter__()
    ws.receive_json()  # welcome

    # Queue a message
    test_message = {"type": "sentient", "text": "hello", "timestamp": time.time()}
    await mock_chat_output.outgoing_queue.put(test_message)

    # Run drain for a short moment
    drain_task = asyncio.create_task(srv._drain_outgoing())
    await asyncio.sleep(0.1)
    drain_task.cancel()
    try:
        await drain_task
    except asyncio.CancelledError:
        pass

    # Client should have received the message
    received = ws.receive_json()
    assert received == test_message

    ws.close()


@pytest.mark.asyncio
async def test_broadcast_cognitive_event_sends_to_dashboard_sockets(
    mock_lifecycle, mock_chat_input, mock_chat_output, mock_health_network, mock_event_bus
):
    """_broadcast_cognitive_event sends event to all dashboard sockets."""
    config = {"host": "127.0.0.1", "port": 8765}
    srv = APIServer(
        config,
        mock_lifecycle,
        mock_chat_input,
        mock_chat_output,
        mock_health_network,
        event_bus=mock_event_bus,
    )

    test_client = TestClient(srv.app)
    ws = test_client.websocket_connect("/ws/dashboard")
    ws.__enter__()

    payload = {"event_type": "cognitive.cycle.complete", "data": {"cycles": 1}}
    await srv._broadcast_cognitive_event(payload)

    # Client should receive the formatted event
    received = ws.receive_json()
    assert received["type"] == "cognitive_event"
    assert received["event_type"] == "cognitive.cycle.complete"
    assert "timestamp" in received

    ws.close()


# ---------------------------------------------------------------------------
# Constructor / init tests
# ---------------------------------------------------------------------------


def test_constructor_sets_host_and_port_from_config():
    """Constructor reads host and port from config dict."""
    mock_lifecycle = MagicMock()
    mock_lifecycle.status_summary.return_value = {}
    mock_lifecycle.get_module.return_value = None
    mock_health = MagicMock()
    mock_health.snapshot.return_value = {}
    mock_health.all_statuses.return_value = {}
    mock_chat_in = AsyncMock()
    mock_chat_out = MagicMock()
    mock_chat_out.outgoing_queue = asyncio.Queue()

    config = {"host": "0.0.0.0", "port": 9999}
    srv = APIServer(
        config,
        mock_lifecycle,
        mock_chat_in,
        mock_chat_out,
        mock_health,
    )

    assert srv.host == "0.0.0.0"
    assert srv.port == 9999


def test_constructor_adds_cors_middleware():
    """Constructor adds CORSMiddleware to the FastAPI app."""
    mock_lifecycle = MagicMock()
    mock_lifecycle.status_summary.return_value = {}
    mock_lifecycle.get_module.return_value = None
    mock_health = MagicMock()
    mock_health.snapshot.return_value = {}
    mock_health.all_statuses.return_value = {}
    mock_chat_in = AsyncMock()
    mock_chat_out = MagicMock()
    mock_chat_out.outgoing_queue = asyncio.Queue()

    srv = APIServer(
        {"host": "127.0.0.1", "port": 8765},
        mock_lifecycle,
        mock_chat_in,
        mock_chat_out,
        mock_health,
    )

    # Verify CORSMiddleware is in the app's middleware stack
    # starlette stores each middleware as Middleware(cls=..., kwargs={...})
    middleware_classes = [m.cls.__name__ for m in srv.app.user_middleware]
    assert "CORSMiddleware" in middleware_classes


def test_placeholder_gui_html_returns_html_string():
    """_placeholder_gui_html returns a string containing HTML."""
    mock_lifecycle = MagicMock()
    mock_lifecycle.status_summary.return_value = {}
    mock_lifecycle.get_module.return_value = None
    mock_health = MagicMock()
    mock_health.snapshot.return_value = {}
    mock_health.all_statuses.return_value = {}
    mock_chat_in = AsyncMock()
    mock_chat_out = MagicMock()
    mock_chat_out.outgoing_queue = asyncio.Queue()

    srv = APIServer(
        {"host": "127.0.0.1", "port": 8765},
        mock_lifecycle,
        mock_chat_in,
        mock_chat_out,
        mock_health,
    )

    html = srv._placeholder_gui_html()
    assert isinstance(html, str)
    assert "<!DOCTYPE html>" in html
    assert "Sentient" in html
