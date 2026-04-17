"""Coverage tests for src/sentient/main.py.

Uses in-process mocking to test main.py functions without loading heavy
dependencies (chromadb, sentence_transformers, litellm). All module
dependencies are mocked so we can exercise load_config, build_and_start,
run_forever, and run in isolation.
"""
from __future__ import annotations

import asyncio
import os
import signal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config_files(tmp_path: Path) -> Path:
    """Write minimal config files and return the config dir path."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    system_cfg = {
        "system": {"name": "test-sentient", "data_dir": str(tmp_path / "data")},
        "memory": {"embeddings": {"model": "all-MiniLM-L6-v2"}},
        "persona": {},
        "health": {},
        "thalamus": {"batching": {}},
        "checkpost": {},
        "queue_zone": {},
        "tlp": {},
        "cognitive_core": {},
        "world_model": {},
        "brainstem": {},
        "sleep": {},
        "api": {"host": "127.0.0.1", "port": 0},
    }
    (config_dir / "system.yaml").write_text(yaml.safe_dump(system_cfg))
    (config_dir / "inference_gateway.yaml").write_text(
        yaml.safe_dump({"models": {}, "routing": {}, "cost_tracking": {"enabled": False}}),
    )
    return config_dir


def _make_mock_module(name: str) -> MagicMock:
    """Create a mock module with async lifecycle methods."""
    m = MagicMock(name=name)
    m.initialize = AsyncMock()
    m.start = AsyncMock()
    m.shutdown = AsyncMock()
    m.register_plugin = AsyncMock()
    m.state = MagicMock()
    m.state.value = "running"
    m.set_status = MagicMock()
    return m


# ---------------------------------------------------------------------------
# load_config tests
# ---------------------------------------------------------------------------

class TestLoadConfig:
    def test_load_config_success(self, tmp_path: Path):
        config_dir = _make_config_files(tmp_path)
        with patch.dict(os.environ, {"SENTIENT_CONFIG_DIR": str(config_dir)}):
            from sentient.main import load_config
            sys_cfg, inf_cfg = load_config()
            assert sys_cfg["system"]["name"] == "test-sentient"
            assert "models" in inf_cfg

    def test_load_config_missing_dir(self, tmp_path: Path):
        from sentient.main import load_config
        with patch.dict(os.environ, {"SENTIENT_CONFIG_DIR": str(tmp_path / "nonexistent")}):
            with pytest.raises(FileNotFoundError):
                load_config()


# ---------------------------------------------------------------------------
# build_and_start tests (with full module mocking)
# ---------------------------------------------------------------------------

class TestBuildAndStart:
    @pytest.mark.asyncio
    async def test_build_and_start_creates_data_dir(self, tmp_path: Path):
        config_dir = _make_config_files(tmp_path)
        data_dir = tmp_path / "data"

        mocks = {
            "InferenceGateway": _make_mock_module("ig"),
            "MemoryArchitecture": _make_mock_module("mem"),
            "PersonaManager": _make_mock_module("pm"),
            "HealthPulseNetwork": _make_mock_module("hpn"),
            "InnateResponse": _make_mock_module("ir"),
            "Thalamus": _make_mock_module("thal"),
            "Checkpost": _make_mock_module("cp"),
            "QueueZone": _make_mock_module("qz"),
            "TemporalLimbicProcessor": _make_mock_module("tlp"),
            "CognitiveCore": _make_mock_module("cc"),
            "WorldModel": _make_mock_module("wm"),
            "HarnessAdapter": _make_mock_module("ha"),
            "Brainstem": _make_mock_module("bs"),
            "SleepScheduler": _make_mock_module("ss"),
        }

        mock_lifecycle = MagicMock()
        mock_lifecycle.startup = AsyncMock()
        mock_lifecycle.register = MagicMock()
        mock_lifecycle.shutdown = AsyncMock()

        mock_api = MagicMock()
        mock_api.start = AsyncMock()
        mock_api.shutdown = AsyncMock()
        mock_api.host = "127.0.0.1"
        mock_api.port = 0

        mock_bus = MagicMock()

        with patch.dict(os.environ, {"SENTIENT_CONFIG_DIR": str(config_dir)}), \
             patch("sentient.main.InferenceGateway", return_value=mocks["InferenceGateway"]), \
             patch("sentient.main.MemoryArchitecture", return_value=mocks["MemoryArchitecture"]), \
             patch("sentient.main.PersonaManager", return_value=mocks["PersonaManager"]), \
             patch("sentient.main.HealthPulseNetwork", return_value=mocks["HealthPulseNetwork"]), \
             patch("sentient.main.InnateResponse", return_value=mocks["InnateResponse"]), \
             patch("sentient.main.Thalamus", return_value=mocks["Thalamus"]), \
             patch("sentient.main.Checkpost", return_value=mocks["Checkpost"]), \
             patch("sentient.main.QueueZone", return_value=mocks["QueueZone"]), \
             patch("sentient.main.TemporalLimbicProcessor", return_value=mocks["TemporalLimbicProcessor"]), \
             patch("sentient.main.CognitiveCore", return_value=mocks["CognitiveCore"]), \
             patch("sentient.main.WorldModel", return_value=mocks["WorldModel"]), \
             patch("sentient.main.HarnessAdapter", return_value=mocks["HarnessAdapter"]), \
             patch("sentient.main.Brainstem", return_value=mocks["Brainstem"]), \
             patch("sentient.main.SleepScheduler", return_value=mocks["SleepScheduler"]), \
             patch("sentient.main.LifecycleManager", return_value=mock_lifecycle), \
             patch("sentient.main.get_event_bus", return_value=mock_bus), \
             patch("sentient.main.ChatInputPlugin"), \
             patch("sentient.main.ChatOutputPlugin"), \
             patch("sentient.api.server.APIServer", return_value=mock_api):

            from sentient.main import build_and_start
            lifecycle, api_server = await build_and_start()

            # Data dir should be created
            assert data_dir.exists()
            assert (data_dir / "logs").exists()

            # Lifecycle startup should be called
            mock_lifecycle.startup.assert_called_once()

            # API server should be started
            mock_api.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_build_and_start_registers_modules(self, tmp_path: Path):
        config_dir = _make_config_files(tmp_path)

        mock_lifecycle = MagicMock()
        mock_lifecycle.startup = AsyncMock()
        mock_lifecycle.register = MagicMock()
        mock_lifecycle.shutdown = AsyncMock()
        register_calls = []
        mock_lifecycle.register.side_effect = lambda m, **kw: register_calls.append((m, kw))

        mock_api = MagicMock()
        mock_api.start = AsyncMock()
        mock_api.shutdown = AsyncMock()
        mock_api.host = "127.0.0.1"
        mock_api.port = 0

        mock_bus = MagicMock()

        with patch.dict(os.environ, {"SENTIENT_CONFIG_DIR": str(config_dir)}), \
             patch("sentient.main.InferenceGateway", return_value=_make_mock_module("ig")), \
             patch("sentient.main.MemoryArchitecture", return_value=_make_mock_module("mem")), \
             patch("sentient.main.PersonaManager", return_value=_make_mock_module("pm")), \
             patch("sentient.main.HealthPulseNetwork", return_value=_make_mock_module("hpn")), \
             patch("sentient.main.InnateResponse", return_value=_make_mock_module("ir")), \
             patch("sentient.main.Thalamus", return_value=_make_mock_module("thal")), \
             patch("sentient.main.Checkpost", return_value=_make_mock_module("cp")), \
             patch("sentient.main.QueueZone", return_value=_make_mock_module("qz")), \
             patch("sentient.main.TemporalLimbicProcessor", return_value=_make_mock_module("tlp")), \
             patch("sentient.main.CognitiveCore", return_value=_make_mock_module("cc")), \
             patch("sentient.main.WorldModel", return_value=_make_mock_module("wm")), \
             patch("sentient.main.HarnessAdapter", return_value=_make_mock_module("ha")), \
             patch("sentient.main.Brainstem", return_value=_make_mock_module("bs")), \
             patch("sentient.main.SleepScheduler", return_value=_make_mock_module("ss")), \
             patch("sentient.main.LifecycleManager", return_value=mock_lifecycle), \
             patch("sentient.main.get_event_bus", return_value=mock_bus), \
             patch("sentient.main.ChatInputPlugin"), \
             patch("sentient.main.ChatOutputPlugin"), \
             patch("sentient.api.server.APIServer", return_value=mock_api):

            from sentient.main import build_and_start
            await build_and_start()

            # Should register at least 10 modules (essential + non-essential)
            assert mock_lifecycle.register.call_count >= 10


# ---------------------------------------------------------------------------
# run_forever / run tests
# ---------------------------------------------------------------------------

class TestRunForever:
    @pytest.mark.asyncio
    async def test_run_forever_shutdown_on_signal(self, tmp_path: Path):
        """run_forever should exit cleanly when shutdown_event is set."""
        # Mock build_and_start to return a lifecycle/api that shut down quickly
        mock_lifecycle = MagicMock()
        mock_lifecycle.shutdown = AsyncMock()
        mock_api = MagicMock()
        mock_api.shutdown = AsyncMock()

        async def fake_build_and_start():
            return mock_lifecycle, mock_api

        # Make asyncio.Event().wait() return immediately (simulates signal)
        mock_event = MagicMock()
        mock_event.wait = AsyncMock()
        mock_event.set = MagicMock()

        with patch("sentient.main.build_and_start", side_effect=fake_build_and_start), \
             patch("asyncio.Event", return_value=mock_event), \
             patch("asyncio.get_event_loop") as mock_loop:
            mock_loop_obj = MagicMock()
            mock_loop_obj.add_signal_handler = MagicMock(side_effect=NotImplementedError)
            mock_loop.return_value = mock_loop_obj

            from sentient.main import run_forever
            await run_forever()

            mock_lifecycle.shutdown.assert_called()
            mock_api.shutdown.assert_called()


class TestRun:
    def test_run_keyboard_interrupt(self, tmp_path: Path):
        """run() should handle KeyboardInterrupt gracefully."""
        with patch("sentient.main.asyncio.run", side_effect=KeyboardInterrupt):
            from sentient.main import run
            # Should not raise
            run()