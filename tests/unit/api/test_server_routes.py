"""Unit tests for the rebuilt APIServer routes.

Tests POST /api/chat, GET /api/events/recent, GET /api/turns/{turn_id},
unified /ws WebSocket, event broadcasting, turn records, and cleanup.
"""
from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from sentient.api.server import APIServer, TurnRecord


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
    """Health pulse network with snapshot."""
    health_network = MagicMock()
    health_network.snapshot.return_value = {
        "thalamus": {"latest": {"status": "healthy"}, "pulse_count": 1, "status": "healthy"},
    }
    return health_network


@pytest.fixture
def mock_event_bus():
    """Mock event bus with async subscribe/publish."""
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
# POST /api/chat
# ---------------------------------------------------------------------------


def test_post_chat_valid_message_returns_202_and_turn_id(client, mock_chat_input, mock_event_bus):
    """POST /api/chat with a valid message returns 202 with turn_id."""
    response = client.post("/api/chat", json={"message": "hello world"})
    assert response.status_code == 202
    data = response.json()
    assert "turn_id" in data
    assert data["status"] == "accepted"
    # UUID format check
    assert len(data["turn_id"]) == 36


def test_post_chat_empty_message_returns_400(client):
    """POST /api/chat with empty/whitespace-only message returns 400."""
    response = client.post("/api/chat", json={"message": ""})
    assert response.status_code == 400
    assert "error" in response.json()

    response = client.post("/api/chat", json={"message": "   "})
    assert response.status_code == 400


def test_post_chat_no_message_returns_400(client):
    """POST /api/chat without a message field returns 400."""
    response = client.post("/api/chat", json={})
    assert response.status_code == 400


def test_post_chat_injects_into_chat_input(client, mock_chat_input):
    """POST /api/chat calls chat_input.inject() with correct payload."""
    response = client.post("/api/chat", json={"message": "test message", "session_id": "main"})
    assert response.status_code == 202
    mock_chat_input.inject.assert_called_once()
    call_args = mock_chat_input.inject.call_args[0][0]
    assert call_args["text"] == "test message"
    assert call_args["session_id"] == "main"
    assert "timestamp" in call_args
    assert "turn_id" in call_args


def test_post_chat_publishes_event(client, mock_event_bus):
    """POST /api/chat publishes chat.input.received event."""
    response = client.post("/api/chat", json={"message": "hello"})
    assert response.status_code == 202
    mock_event_bus.publish.assert_called_once()
    event_name, payload = mock_event_bus.publish.call_args[0]
    assert event_name == "chat.input.received"
    assert payload["text"] == "hello"
    assert "turn_id" in payload


def test_post_chat_creates_turn_record(client, server):
    """POST /api/chat creates a TurnRecord in _turn_records."""
    response = client.post("/api/chat", json={"message": "hello"})
    assert response.status_code == 202
    turn_id = response.json()["turn_id"]
    assert turn_id in server._turn_records
    record = server._turn_records[turn_id]
    assert record.user_message == "hello"
    assert record.is_complete is False


# ---------------------------------------------------------------------------
# GET /api/events/recent
# ---------------------------------------------------------------------------


def test_get_recent_events_empty_returns_empty_list(client):
    """GET /api/events/recent with empty buffer returns empty list."""
    response = client.get("/api/events/recent")
    assert response.status_code == 200
    assert response.json() == []


# ---------------------------------------------------------------------------
# GET /api/turns/{turn_id}
# ---------------------------------------------------------------------------


def test_get_turn_valid_turn_id(client, server):
    """GET /api/turns/{turn_id} returns the turn record when found."""
    # Create a turn record directly
    turn_id = "test-turn-123"
    server._turn_records[turn_id] = TurnRecord(turn_id, "hello", time.time())

    response = client.get(f"/api/turns/{turn_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["turn_id"] == turn_id
    assert data["user_message"] == "hello"
    assert data["is_complete"] is False


def test_get_turn_invalid_turn_id_returns_404(client):
    """GET /api/turns/{turn_id} returns 404 when turn_id not found."""
    response = client.get("/api/turns/nonexistent-turn")
    assert response.status_code == 404
    assert "error" in response.json()


# ---------------------------------------------------------------------------
# GET /api/health and /api/status (existing routes)
# ---------------------------------------------------------------------------


def test_get_health_returns_snapshot(client, mock_health_network):
    """GET /api/health delegates to health_network.snapshot()."""
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == mock_health_network.snapshot.return_value


def test_get_status_returns_lifecycle_summary(client, mock_lifecycle):
    """GET /api/status delegates to lifecycle.status_summary()."""
    response = client.get("/api/status")
    assert response.status_code == 200
    assert response.json() == mock_lifecycle.status_summary.return_value


# ---------------------------------------------------------------------------
# WebSocket /ws (Step-wise tests)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_ws_message_ping_returns_pong(server):
    """_handle_ws_message returns pong for ping."""
    ts = time.time()
    result = await server._handle_ws_message({"type": "ping"}, ts)
    assert result == {"type": "pong", "timestamp": ts}


@pytest.mark.asyncio
async def test_handle_ws_message_chat_forwards_to_input(server, mock_chat_input):
    """_handle_ws_message for chat forwards to chat_input.inject()."""
    ts = time.time()
    await server._handle_ws_message(
        {"type": "chat", "text": "hello", "session_id": "ws-session"}, ts
    )
    mock_chat_input.inject.assert_called_once()
    payload = mock_chat_input.inject.call_args[0][0]
    assert payload["text"] == "hello"
    assert payload["session_id"] == "ws-session"
    assert payload["timestamp"] == ts


def test_ws_connect_sends_health_snapshot_and_welcome(client, mock_health_network):
    """Connecting to /ws receives health snapshot and welcome message."""
    # We still use TestClient for simple connection/receive tests if they don't hang.
    # If they hang, we'd mock the WebSocket object and call unified_ws directly.
    with client.websocket_connect("/ws") as websocket:
        # First message should be health
        data = websocket.receive_json()
        assert data["type"] == "health"
        assert data["data"] == mock_health_network.snapshot.return_value

        # Second message should be welcome
        data = websocket.receive_json()
        assert data["type"] == "welcome"
        assert "Connected to Sentient" in data["text"]


def test_ws_recent_events_sent_on_connect(client, server):
    """Recent events from buffer are sent on WebSocket connect."""
    # Pre-populate the event buffer
    event = {
        "type": "event",
        "stage": "thalamus",
        "event_name": "input.received",
        "data": {},
        "timestamp": time.time(),
    }
    server._event_buffer.append(event)

    with client.websocket_connect("/ws") as websocket:
        websocket.receive_json()  # health
        websocket.receive_json()  # welcome

        # Next should be the backfilled event
        data = websocket.receive_json()
        assert data == event


# ---------------------------------------------------------------------------
# Event broadcasting
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_broadcast_event_stores_in_ring_buffer(
    mock_lifecycle, mock_chat_input, mock_chat_output, mock_health_network, mock_event_bus
):
    """_broadcast_event appends event to _event_buffer."""
    config = {"host": "127.0.0.1", "port": 8765}
    srv = APIServer(
        config,
        mock_lifecycle,
        mock_chat_input,
        mock_chat_output,
        mock_health_network,
        event_bus=mock_event_bus,
    )

    await srv._broadcast_event({
        "event_type": "cognitive.cycle.complete",
        "sequence": 1,
        "timestamp": time.time(),
    })

    assert len(srv._event_buffer) == 1
    event = srv._event_buffer[0]
    assert event["type"] == "event"
    assert event["event_name"] == "cognitive.cycle.complete"
    assert event["stage"] == "cognitive_core"


@pytest.mark.asyncio
async def test_broadcast_event_tracks_in_turn_record(
    mock_lifecycle, mock_chat_input, mock_chat_output, mock_health_network, mock_event_bus
):
    """_broadcast_event appends event to the matching TurnRecord."""
    config = {"host": "127.0.0.1", "port": 8765}
    srv = APIServer(
        config,
        mock_lifecycle,
        mock_chat_input,
        mock_chat_output,
        mock_health_network,
        event_bus=mock_event_bus,
    )

    turn_id = "track-test-turn"
    srv._turn_records[turn_id] = TurnRecord(turn_id, "hello", time.time())

    await srv._broadcast_event({
        "event_type": "cognitive.cycle.complete",
        "turn_id": turn_id,
        "timestamp": time.time(),
    })

    record = srv._turn_records[turn_id]
    assert len(record.events) == 1
    assert record.events[0]["event_name"] == "cognitive.cycle.complete"


# ---------------------------------------------------------------------------
# _map_event_to_stage
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "event_name,expected_stage",
    [
        ("input.received", "thalamus"),
        ("thalamus.classified", "thalamus"),
        ("checkpost.tagged", "checkpost"),
        ("queue.delivered", "queue_zone"),
        ("tlp.enriched", "tlp"),
        ("cognitive.cycle.complete", "cognitive_core"),
        ("decision.approved", "world_model"),
        ("action.executed", "brainstem"),
        ("memory.candidate", "memory"),
        ("sleep.wake", "sleep"),
        ("health.pulse", "health"),
        ("attention.summary.update", "frontal"),
        ("chat.input.received", "chat"),
        ("lifecycle.module.started", "lifecycle"),
        ("harness.cycle.end", "harness"),
        ("unknown.event", "system"),
    ],
)
def test_map_event_to_stage(event_name, expected_stage):
    """Event name prefixes map to correct stages."""
    mock_lifecycle = MagicMock()
    mock_lifecycle.status_summary.return_value = {}
    mock_lifecycle.get_module.return_value = None
    mock_health = MagicMock()
    mock_health.snapshot.return_value = {}
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
    assert srv._map_event_to_stage(event_name) == expected_stage


# ---------------------------------------------------------------------------
# Turn record cleanup
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cleanup_removes_expired_turn_records(
    mock_lifecycle, mock_chat_input, mock_chat_output, mock_health_network, mock_event_bus
):
    """_cleanup_turn_records removes records older than TTL."""
    config = {"host": "127.0.0.1", "port": 8765}
    srv = APIServer(
        config,
        mock_lifecycle,
        mock_chat_input,
        mock_chat_output,
        mock_health_network,
        event_bus=mock_event_bus,
    )
    srv._turn_ttl_seconds = 1  # 1 second TTL for testing

    # Add an old record (started 2 seconds ago)
    old_turn_id = "old-turn"
    srv._turn_records[old_turn_id] = TurnRecord(old_turn_id, "old", time.time() - 2)

    # Add a fresh record
    fresh_turn_id = "fresh-turn"
    srv._turn_records[fresh_turn_id] = TurnRecord(fresh_turn_id, "fresh", time.time())

    # Run cleanup
    srv._do_cleanup_iteration()

    # Old record should be removed, fresh one should remain
    assert old_turn_id not in srv._turn_records
    assert fresh_turn_id in srv._turn_records


# ---------------------------------------------------------------------------
# _drain_outgoing updates turn record
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_drain_outgoing_updates_turn_record(
    server, mock_chat_output
):
    """_drain_outgoing marks turn record complete and sends to ws clients."""
    turn_id = "drain-test-turn"
    server._turn_records[turn_id] = TurnRecord(turn_id, "hello", time.time())

    # Queue a message with turn_id
    test_message = {
        "type": "chat_message",
        "text": "assistant reply",
        "turn_id": turn_id,
        "timestamp": time.time(),
    }
    await mock_chat_output.outgoing_queue.put(test_message)

    # Mock a WebSocket client
    mock_ws = AsyncMock()
    server._ws_clients.add(mock_ws)

    # Run drain briefly
    drain_task = asyncio.create_task(server._drain_outgoing())
    await asyncio.sleep(0.05)
    drain_task.cancel()
    try:
        await drain_task
    except asyncio.CancelledError:
        pass

    # Turn record should be marked complete
    record = server._turn_records[turn_id]
    assert record.is_complete is True
    assert record.assistant_reply == "assistant reply"

    # Mock WS should have received the message
    mock_ws.send_json.assert_called_once()
    reply = mock_ws.send_json.call_args[0][0]
    assert reply["type"] == "reply"
    assert reply["text"] == "assistant reply"
    assert reply["turn_id"] == turn_id


# ---------------------------------------------------------------------------
# Constructor / init
# ---------------------------------------------------------------------------


def test_turn_record_initial_state():
    """TurnRecord initializes with correct default values."""
    record = TurnRecord("tid-1", "hello", 1234.0)
    assert record.turn_id == "tid-1"
    assert record.user_message == "hello"
    assert record.started_at == 1234.0
    assert record.assistant_reply == ""
    assert record.events == []
    assert record.completed_at is None
    assert record.is_complete is False


def test_constructor_initializes_data_structures(
    mock_lifecycle, mock_chat_input, mock_chat_output, mock_health_network, mock_event_bus
):
    """Constructor initializes _turn_records, _event_buffer, _ws_clients."""
    config = {"host": "127.0.0.1", "port": 8765}
    srv = APIServer(
        config,
        mock_lifecycle,
        mock_chat_input,
        mock_chat_output,
        mock_health_network,
        event_bus=mock_event_bus,
    )

    assert srv._turn_records == {}
    assert len(srv._event_buffer) == 0
    assert len(srv._ws_clients) == 0
    assert srv._turn_ttl_seconds == 300
    assert srv._cleanup_task is None


def test_placeholder_gui_html_contains_ws_script(server):
    """Placeholder HTML contains WebSocket connection to /ws."""
    html = server._placeholder_gui_html()
    assert 'ws://${location.host}/ws' in html
    assert "Sentient" in html


# ---------------------------------------------------------------------------
# Frontend serving and SPA fallback
# ---------------------------------------------------------------------------


def test_frontend_dist_property_returns_none_when_no_dist(server, tmp_path):
    """_frontend_dist returns None when frontend dist directory doesn't exist."""
    # Point to a non-existent dist
    server.config["frontend_dir"] = str(tmp_path / "nonexistent")
    try:
        assert server._frontend_dist is None
    finally:
        server.config.pop("frontend_dir", None)


def test_frontend_dist_property_returns_path_when_dist_exists(server, tmp_path):
    """_frontend_dist returns Path when dist directory with index.html exists."""
    dist = tmp_path / "frontend" / "dist"
    dist.mkdir(parents=True)
    (dist / "index.html").write_text("<html>react app</html>")
    server.config["frontend_dir"] = str(dist)
    result = server._frontend_dist
    assert result is not None
    assert result == dist
    # Cleanup config
    del server.config["frontend_dir"]


def test_root_serves_placeholder_when_no_frontend_dist(client):
    """GET / returns placeholder HTML when no frontend dist exists."""
    response = client.get("/")
    assert response.status_code == 200
    assert "Sentient" in response.text


def test_root_serves_react_app_when_frontend_dist_exists(server, client, tmp_path):
    """GET / returns React index.html when frontend dist directory exists."""
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>React App</html>")
    server.config["frontend_dir"] = str(dist)
    try:
        response = client.get("/")
        assert response.status_code == 200
        assert "React App" in response.text
    finally:
        del server.config["frontend_dir"]


def test_assets_route_returns_404_when_no_frontend_dist(client):
    """GET /assets/... returns 404 when no frontend dist exists."""
    response = client.get("/assets/index-abc123.js")
    assert response.status_code == 404


def test_assets_route_serves_file_when_frontend_dist_exists(server, client, tmp_path):
    """GET /assets/... serves file from frontend dist when it exists."""
    dist = tmp_path / "dist"
    assets = dist / "assets"
    assets.mkdir(parents=True)
    (assets / "index-abc123.js").write_text("console.log('app');")
    (dist / "index.html").write_text("<html>React App</html>")
    server.config["frontend_dir"] = str(dist)
    try:
        response = client.get("/assets/index-abc123.js")
        assert response.status_code == 200
        assert "console.log" in response.text
    finally:
        del server.config["frontend_dir"]


def test_spa_fallback_returns_404_when_no_frontend_dist(server, client, tmp_path):
    """SPA fallback returns 404 when no frontend dist exists."""
    # Point to a non-existent dist so fallback has nothing to serve
    server.config["frontend_dir"] = str(tmp_path / "nonexistent")
    try:
        response = client.get("/dashboard")
        assert response.status_code == 404
    finally:
        server.config.pop("frontend_dir", None)


def test_spa_fallback_serves_index_html_when_frontend_dist_exists(server, client, tmp_path):
    """SPA fallback serves React index.html for unknown routes."""
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>React App</html>")
    server.config["frontend_dir"] = str(dist)
    try:
        response = client.get("/dashboard/settings")
        assert response.status_code == 200
        assert "React App" in response.text
    finally:
        server.config.pop("frontend_dir", None)


def test_api_routes_not_intercepted_by_spa_fallback(client):
    """SPA fallback does not intercept /api/ routes."""
    response = client.get("/api/health")
    # Should return 200 from the real endpoint, not 404 from SPA fallback
    assert response.status_code == 200