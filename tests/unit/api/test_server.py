"""Unit tests for sentient.api.server — lifecycle, constructor, and module endpoints.

Note: WebSocket and route tests are in test_server_routes.py. Integration tests
are in tests/integration/test_api_integration.py and test_api_smoke.py.
"""
from __future__ import annotations

import asyncio
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
    """Health pulse network with snapshot."""
    health_network = MagicMock()
    health_network.snapshot.return_value = {
        "status": "healthy",
        "modules": {"memory": "healthy", "cognitive_core": "healthy"},
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
# REST endpoint tests (module-specific)
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

    srv.port = 0  # use unassigned port

    await srv.start()

    try:
        assert srv._server_task is not None
        assert srv._outgoing_drain_task is not None
    finally:
        await srv.shutdown()


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
    srv.port = 0

    await srv.start()
    server_task = srv._server_task
    drain_task = srv._outgoing_drain_task

    await srv.shutdown()

    assert server_task.cancelled() or server_task.done()
    assert drain_task.cancelled() or drain_task.done()


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

    middleware_classes = [m.cls.__name__ for m in srv.app.user_middleware]
    assert "CORSMiddleware" in middleware_classes


def test_placeholder_gui_html_returns_html_string():
    """_placeholder_gui_html returns a string containing HTML."""
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

    html = srv._placeholder_gui_html()
    assert isinstance(html, str)
    assert "<!DOCTYPE html>" in html
    assert "Sentient" in html