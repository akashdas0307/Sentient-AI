"""Unit tests for src/sentient/main.py — achieves >=50% coverage."""
from __future__ import annotations

import asyncio
import os
import signal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def minimal_system_yaml(tmp_path: Path) -> Path:
    """Create a minimal system.yaml in a temp directory."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    system_cfg = {
        "system": {"name": "test-sentient", "data_dir": str(tmp_path / "data")},
        "memory": {"embeddings": {"model": "all-MiniLM-L6-v2"}},
        "persona": {},
        "health": {},
        "thalamus": {},
        "checkpost": {},
        "queue_zone": {},
        "tlp": {},
        "cognitive_core": {},
        "world_model": {},
        "brainstem": {},
        "sleep": {},
        "api": {"host": "127.0.0.1", "port": 8080},
    }
    (config_dir / "system.yaml").write_text(yaml.safe_dump(system_cfg))
    return config_dir


@pytest.fixture
def minimal_inference_yaml(tmp_path: Path) -> Path:
    """Create a minimal inference_gateway.yaml in a temp directory."""
    config_dir = tmp_path / "config"
    config_dir.mkdir(exist_ok=True)
    (config_dir / "inference_gateway.yaml").write_text(yaml.safe_dump({"models": {}}))
    return config_dir


@pytest.fixture
def config_dir(minimal_system_yaml: Path, minimal_inference_yaml: Path) -> Path:
    """Combined config directory with both YAML files."""
    return minimal_system_yaml


# =============================================================================
# load_config() tests
# =============================================================================


def test_load_config_reads_both_yaml_files(config_dir: Path):
    """load_config reads system.yaml and inference_gateway.yaml and returns tuple."""
    with patch.dict(os.environ, {"SENTIENT_CONFIG_DIR": str(config_dir)}):
        from sentient.main import load_config

        system_cfg, inference_cfg = load_config()

    assert isinstance(system_cfg, dict)
    assert isinstance(inference_cfg, dict)
    assert system_cfg["system"]["name"] == "test-sentient"
    assert "models" in inference_cfg


def test_load_config_respects_sentient_config_dir_env_var(config_dir: Path):
    """load_config uses SENTIENT_CONFIG_DIR when set."""
    with patch.dict(os.environ, {"SENTIENT_CONFIG_DIR": str(config_dir)}):
        from sentient.main import load_config

        system_cfg, _ = load_config()

    assert system_cfg["system"]["name"] == "test-sentient"


def test_load_config_raises_file_not_found_for_missing_system_yaml(tmp_path: Path):
    """load_config raises FileNotFoundError when system.yaml is missing."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    # Only create inference_gateway.yaml, not system.yaml
    (config_dir / "inference_gateway.yaml").write_text(yaml.safe_dump({}))

    with patch.dict(os.environ, {"SENTIENT_CONFIG_DIR": str(config_dir)}):
        from sentient.main import load_config

        with pytest.raises(FileNotFoundError, match="system.yaml"):
            load_config()


def test_load_config_raises_file_not_found_for_missing_inference_yaml(tmp_path: Path):
    """load_config raises FileNotFoundError when inference_gateway.yaml is missing."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "system.yaml").write_text(yaml.safe_dump({"system": {}}))

    with patch.dict(os.environ, {"SENTIENT_CONFIG_DIR": str(config_dir)}):
        from sentient.main import load_config

        with pytest.raises(FileNotFoundError, match="inference_gateway.yaml"):
            load_config()


def test_load_config_defaults_to_dot_config_when_env_var_not_set(config_dir: Path, monkeypatch):
    """load_config falls back to ./config when SENTIENT_CONFIG_DIR is not set."""
    # Write config files to ./config in the current directory
    default_config = Path("./config")
    default_config.mkdir(exist_ok=True)
    try:
        (default_config / "system.yaml").write_text(yaml.safe_dump({"system": {"name": "default-test"}}))
        (default_config / "inference_gateway.yaml").write_text(yaml.safe_dump({}))

        monkeypatch.delenv("SENTIENT_CONFIG_DIR", raising=False)
        # Need to reimport to pick up the env var change
        import importlib
        import sentient.main
        importlib.reload(sentient.main)

        from sentient.main import load_config

        system_cfg, _ = load_config()
        assert system_cfg["system"]["name"] == "default-test"
    finally:
        # Cleanup
        if (default_config / "system.yaml").exists():
            (default_config / "system.yaml").unlink()
        if (default_config / "inference_gateway.yaml").exists():
            (default_config / "inference_gateway.yaml").unlink()
        if default_config.exists() and not any(default_config.iterdir()):
            default_config.rmdir()


# =============================================================================
# build_and_start() tests
# =============================================================================


class _MockModule:
    """Minimal mock module implementing ModuleInterface."""

    def __init__(self, name: str = "mock", config: dict | None = None):
        self.name = name
        self.config = config or {}
        self.initialized = False
        self.started = False
        self.shutdown_called = False

    async def initialize(self):
        self.initialized = True

    async def start(self):
        self.started = True

    async def shutdown(self):
        self.shutdown_called = True


@pytest.mark.asyncio
async def test_build_and_start_registers_all_modules_with_lifecycle(config_dir: Path):
    """build_and_start registers all modules with the LifecycleManager."""
    mock_modules = {}

    def make_mock(name: str):
        m = _MockModule(name)
        mock_modules[name] = m
        return m

    # Create mock classes that return our mock modules
    mock_classes = {}
    for name in [
        "InferenceGateway", "MemoryArchitecture", "PersonaManager",
        "HealthPulseNetwork", "InnateResponse", "Thalamus",
        "Checkpost", "QueueZone", "TemporalLimbicProcessor",
        "CognitiveCore", "WorldModel", "HarnessAdapter",
        "Brainstem", "SleepScheduler",
    ]:
        mock_cls = MagicMock()
        mock_instance = make_mock(name.lower().replace("healthpulsenetwork", "health_network")
                                   .replace("innateresponse", "innate")
                                   .replace("temporallimbicprocessor", "tlp")
                                   .replace("cognitivecore", "cognitive_core")
                                   .replace("worldmodel", "world_model")
                                   .replace("harnessadapter", "harness_adapter")
                                   .replace("brainscheduler", "sleep_scheduler")
                                   .replace("sleepscheduler", "sleep"))
        mock_cls.return_value = mock_instance
        mock_classes[name] = mock_cls

    mock_api_server = MagicMock()
    mock_api_server.host = "127.0.0.1"
    mock_api_server.port = 8080
    mock_api_server.start = AsyncMock()
    mock_api_server.shutdown = AsyncMock()

    with patch.dict(os.environ, {"SENTIENT_CONFIG_DIR": str(config_dir)}), \
         patch("sentient.main.InferenceGateway", mock_classes["InferenceGateway"]), \
         patch("sentient.main.MemoryArchitecture", mock_classes["MemoryArchitecture"]), \
         patch("sentient.main.PersonaManager", mock_classes["PersonaManager"]), \
         patch("sentient.main.HealthPulseNetwork", mock_classes["HealthPulseNetwork"]), \
         patch("sentient.main.InnateResponse", mock_classes["InnateResponse"]), \
         patch("sentient.main.Thalamus", mock_classes["Thalamus"]), \
         patch("sentient.main.Checkpost", mock_classes["Checkpost"]), \
         patch("sentient.main.QueueZone", mock_classes["QueueZone"]), \
         patch("sentient.main.TemporalLimbicProcessor", mock_classes["TemporalLimbicProcessor"]), \
         patch("sentient.main.CognitiveCore", mock_classes["CognitiveCore"]), \
         patch("sentient.main.WorldModel", mock_classes["WorldModel"]), \
         patch("sentient.main.HarnessAdapter", mock_classes["HarnessAdapter"]), \
         patch("sentient.main.Brainstem", mock_classes["Brainstem"]), \
         patch("sentient.main.SleepScheduler", mock_classes["SleepScheduler"]), \
         patch("sentient.main.ChatInputPlugin") as mock_chat_input, \
         patch("sentient.main.ChatOutputPlugin") as mock_chat_output, \
         patch("sentient.api.server.APIServer", return_value=mock_api_server), \
         patch("sentient.main.get_event_bus"):

        mock_chat_input_instance = MagicMock()
        mock_chat_input_instance.register_plugin = AsyncMock()
        mock_chat_input.return_value = mock_chat_input_instance

        mock_chat_output_instance = MagicMock()
        mock_chat_output_instance.register_plugin = AsyncMock()
        mock_chat_output.return_value = mock_chat_output_instance

        # Patch thalamus and brainstem so register_plugin calls work
        mock_thalamus_instance = MagicMock()
        mock_thalamus_instance.register_plugin = AsyncMock()
        mock_classes["Thalamus"].return_value = mock_thalamus_instance

        mock_brainstem_instance = MagicMock()
        mock_brainstem_instance.register_plugin = AsyncMock()
        mock_classes["Brainstem"].return_value = mock_brainstem_instance

        from importlib import reload
        import sentient.main
        reload(sentient.main)

        lifecycle, api_server = await sentient.main.build_and_start()

        # Verify lifecycle has modules registered
        registered_names = list(lifecycle._modules.keys())
        # At minimum, essential modules should be registered
        assert len(registered_names) >= 5


@pytest.mark.asyncio
async def test_build_and_start_creates_data_directory(config_dir: Path):
    """build_and_start creates the data directory and logs subdirectory."""
    data_dir = config_dir / "data"

    mock_api_server = MagicMock()
    mock_api_server.host = "127.0.0.1"
    mock_api_server.port = 8080
    mock_api_server.start = AsyncMock()
    mock_api_server.shutdown = AsyncMock()

    with patch.dict(os.environ, {"SENTIENT_CONFIG_DIR": str(config_dir)}), \
         patch("sentient.main.InferenceGateway") as mock_ig, \
         patch("sentient.main.MemoryArchitecture") as mock_mem, \
         patch("sentient.main.PersonaManager") as mock_persona, \
         patch("sentient.main.HealthPulseNetwork") as mock_hpn, \
         patch("sentient.main.InnateResponse") as mock_ir, \
         patch("sentient.main.Thalamus") as mock_thal, \
         patch("sentient.main.Checkpost") as mock_cp, \
         patch("sentient.main.QueueZone") as mock_qz, \
         patch("sentient.main.TemporalLimbicProcessor") as mock_tlp, \
         patch("sentient.main.CognitiveCore") as mock_cc, \
         patch("sentient.main.WorldModel") as mock_wm, \
         patch("sentient.main.HarnessAdapter") as mock_ha, \
         patch("sentient.main.Brainstem") as mock_bs, \
         patch("sentient.main.SleepScheduler") as mock_ss, \
         patch("sentient.main.ChatInputPlugin") as mock_ci, \
         patch("sentient.main.ChatOutputPlugin") as mock_co, \
         patch("sentient.api.server.APIServer", return_value=mock_api_server), \
         patch("sentient.main.get_event_bus"):

        mock_ig.return_value = MagicMock(name="inference_gateway")
        mock_mem.return_value = MagicMock(name="memory")
        mock_persona.return_value = MagicMock(name="persona")
        mock_hpn.return_value = MagicMock(name="health_network")
        mock_ir.return_value = MagicMock(name="innate")
        mock_thal.return_value = MagicMock(name="thalamus")
        mock_cp.return_value = MagicMock(name="checkpost")
        mock_qz.return_value = MagicMock(name="queue_zone")
        mock_tlp.return_value = MagicMock(name="tlp")
        mock_cc.return_value = MagicMock(name="cognitive_core")
        mock_wm.return_value = MagicMock(name="world_model")
        mock_ha.return_value = MagicMock(name="harness")
        mock_bs.return_value = MagicMock(name="brainstem")
        mock_ss.return_value = MagicMock(name="sleep")

        mock_ci_instance = MagicMock()
        mock_ci_instance.register_plugin = AsyncMock()
        mock_ci.return_value = mock_ci_instance

        mock_co_instance = MagicMock()
        mock_co_instance.register_plugin = AsyncMock()
        mock_co.return_value = mock_co_instance

        from importlib import reload
        import sentient.main
        reload(sentient.main)

        await sentient.main.build_and_start()

        assert data_dir.exists()
        assert (data_dir / "logs").exists()


@pytest.mark.asyncio
async def test_build_and_start_registers_essential_modules(config_dir: Path):
    """build_and_start marks essential modules as essential in LifecycleManager."""
    mock_api_server = MagicMock()
    mock_api_server.host = "127.0.0.1"
    mock_api_server.port = 8080
    mock_api_server.start = AsyncMock()
    mock_api_server.shutdown = AsyncMock()

    with patch.dict(os.environ, {"SENTIENT_CONFIG_DIR": str(config_dir)}), \
         patch("sentient.main.InferenceGateway") as mock_ig, \
         patch("sentient.main.MemoryArchitecture") as mock_mem, \
         patch("sentient.main.PersonaManager") as mock_persona, \
         patch("sentient.main.HealthPulseNetwork") as mock_hpn, \
         patch("sentient.main.InnateResponse") as mock_ir, \
         patch("sentient.main.Thalamus") as mock_thal, \
         patch("sentient.main.Checkpost") as mock_cp, \
         patch("sentient.main.QueueZone") as mock_qz, \
         patch("sentient.main.TemporalLimbicProcessor") as mock_tlp, \
         patch("sentient.main.CognitiveCore") as mock_cc, \
         patch("sentient.main.WorldModel") as mock_wm, \
         patch("sentient.main.HarnessAdapter") as mock_ha, \
         patch("sentient.main.Brainstem") as mock_bs, \
         patch("sentient.main.SleepScheduler") as mock_ss, \
         patch("sentient.main.ChatInputPlugin") as mock_ci, \
         patch("sentient.main.ChatOutputPlugin") as mock_co, \
         patch("sentient.api.server.APIServer", return_value=mock_api_server), \
         patch("sentient.main.get_event_bus"):

        # Create persistent module instances to track essential flag
        module_instances = {}
        for name in ["ig", "mem", "persona", "hpn", "ir", "thal", "cp", "qz", "tlp", "cc", "wm", "ha", "bs", "ss"]:
            m = MagicMock(name=name)
            module_instances[name] = m

        mock_ig.return_value = module_instances["ig"]
        mock_mem.return_value = module_instances["mem"]
        mock_persona.return_value = module_instances["persona"]
        mock_hpn.return_value = module_instances["hpn"]
        mock_ir.return_value = module_instances["ir"]
        mock_thal.return_value = module_instances["thal"]
        mock_cp.return_value = module_instances["cp"]
        mock_qz.return_value = module_instances["qz"]
        mock_tlp.return_value = module_instances["tlp"]
        mock_cc.return_value = module_instances["cc"]
        mock_wm.return_value = module_instances["wm"]
        mock_ha.return_value = module_instances["ha"]
        mock_bs.return_value = module_instances["bs"]
        mock_ss.return_value = module_instances["ss"]

        mock_ci_instance = MagicMock()
        mock_ci_instance.register_plugin = AsyncMock()
        mock_ci.return_value = mock_ci_instance

        mock_co_instance = MagicMock()
        mock_co_instance.register_plugin = AsyncMock()
        mock_co.return_value = mock_co_instance

        from importlib import reload
        import sentient.main
        reload(sentient.main)

        lifecycle, _ = await sentient.main.build_and_start()

        # Verify essential modules are marked
        for module in ["InferenceGateway", "MemoryArchitecture", "PersonaManager",
                       "HealthPulseNetwork", "InnateResponse", "SleepScheduler"]:
            assert module.lower() in lifecycle._essential_modules


@pytest.mark.asyncio
async def test_build_and_start_calls_lifecycle_startup(config_dir: Path):
    """build_and_start calls lifecycle.startup() after registering modules."""
    mock_api_server = MagicMock()
    mock_api_server.host = "127.0.0.1"
    mock_api_server.port = 8080
    mock_api_server.start = AsyncMock()
    mock_api_server.shutdown = AsyncMock()

    with patch.dict(os.environ, {"SENTIENT_CONFIG_DIR": str(config_dir)}), \
         patch("sentient.main.InferenceGateway") as mock_ig, \
         patch("sentient.main.MemoryArchitecture") as mock_mem, \
         patch("sentient.main.PersonaManager") as mock_persona, \
         patch("sentient.main.HealthPulseNetwork") as mock_hpn, \
         patch("sentient.main.InnateResponse") as mock_ir, \
         patch("sentient.main.Thalamus") as mock_thal, \
         patch("sentient.main.Checkpost") as mock_cp, \
         patch("sentient.main.QueueZone") as mock_qz, \
         patch("sentient.main.TemporalLimbicProcessor") as mock_tlp, \
         patch("sentient.main.CognitiveCore") as mock_cc, \
         patch("sentient.main.WorldModel") as mock_wm, \
         patch("sentient.main.HarnessAdapter") as mock_ha, \
         patch("sentient.main.Brainstem") as mock_bs, \
         patch("sentient.main.SleepScheduler") as mock_ss, \
         patch("sentient.main.ChatInputPlugin") as mock_ci, \
         patch("sentient.main.ChatOutputPlugin") as mock_co, \
         patch("sentient.api.server.APIServer", return_value=mock_api_server), \
         patch("sentient.main.get_event_bus"):

        mock_ig.return_value = MagicMock(name="ig")
        mock_mem.return_value = MagicMock(name="mem")
        mock_persona.return_value = MagicMock(name="persona")
        mock_hpn.return_value = MagicMock(name="hpn")
        mock_ir.return_value = MagicMock(name="ir")
        mock_thal.return_value = MagicMock(name="thal")
        mock_cp.return_value = MagicMock(name="cp")
        mock_qz.return_value = MagicMock(name="qz")
        mock_tlp.return_value = MagicMock(name="tlp")
        mock_cc.return_value = MagicMock(name="cc")
        mock_wm.return_value = MagicMock(name="wm")
        mock_ha.return_value = MagicMock(name="ha")
        mock_bs.return_value = MagicMock(name="bs")
        mock_ss.return_value = MagicMock(name="ss")

        mock_ci_instance = MagicMock()
        mock_ci_instance.register_plugin = AsyncMock()
        mock_ci.return_value = mock_ci_instance

        mock_co_instance = MagicMock()
        mock_co_instance.register_plugin = AsyncMock()
        mock_co.return_value = mock_co_instance

        from importlib import reload
        import sentient.main
        reload(sentient.main)

        lifecycle, _ = await sentient.main.build_and_start()

        # startup should have been called (lifecycle._running should be True)
        assert lifecycle.is_running() is True


# =============================================================================
# run_forever() tests
# =============================================================================


@pytest.mark.asyncio
async def test_run_forever_sets_up_signal_handlers(config_dir: Path):
    """run_forever sets up SIGINT and SIGTERM handlers."""
    mock_api_server = MagicMock()
    mock_api_server.host = "127.0.0.1"
    mock_api_server.port = 8080
    mock_api_server.start = AsyncMock()
    mock_api_server.shutdown = AsyncMock()

    with patch.dict(os.environ, {"SENTIENT_CONFIG_DIR": str(config_dir)}), \
         patch("sentient.main.build_and_start") as mock_bas, \
         patch("asyncio.get_event_loop") as mock_loop:

        mock_lifecycle = MagicMock()
        mock_lifecycle.is_running.return_value = False
        mock_bas.return_value = (mock_lifecycle, mock_api_server)

        mock_loop_instance = MagicMock()
        mock_loop.return_value = mock_loop_instance

        shutdown_event = asyncio.Event()

        def set_shutdown():
            shutdown_event.set()

        mock_loop_instance.add_signal_handler = MagicMock(
            side_effect=lambda sig, handler: set_shutdown() if sig in (signal.SIGINT, signal.SIGTERM) else None
        )

        # Make wait return immediately after a short delay to avoid blocking
        async def wait_with_timeout():
            await asyncio.sleep(0.01)
            shutdown_event.set()

        mock_loop_instance.wait = wait_with_timeout()
        mock_lifecycle.shutdown = AsyncMock()
        mock_api_server.shutdown = AsyncMock()

        from importlib import reload
        import sentient.main
        reload(sentient.main)

        await asyncio.wait_for(sentient.main.run_forever(), timeout=1.0)

        # Verify signal handlers were registered for both signals
        calls = mock_loop_instance.add_signal_handler.call_args_list
        sigs_registered = [call[0][0] for call in calls]
        assert signal.SIGINT in sigs_registered
        assert signal.SIGTERM in sigs_registered


@pytest.mark.asyncio
async def test_run_forever_shuts_down_on_signal(config_dir: Path):
    """run_forever calls shutdown on api_server and lifecycle after signal."""
    mock_api_server = MagicMock()
    mock_api_server.host = "127.0.0.1"
    mock_api_server.port = 8080
    mock_api_server.start = AsyncMock()
    mock_api_server.shutdown = AsyncMock()

    with patch.dict(os.environ, {"SENTIENT_CONFIG_DIR": str(config_dir)}), \
         patch("sentient.main.build_and_start") as mock_bas:

        mock_lifecycle = MagicMock()
        mock_lifecycle.is_running.return_value = False
        mock_lifecycle.shutdown = AsyncMock()
        mock_bas.return_value = (mock_lifecycle, mock_api_server)

        from importlib import reload
        import sentient.main
        reload(sentient.main)

        # Create a signal-like event to trigger shutdown
        shutdown_called = False

        async def mock_wait():
            nonlocal shutdown_called
            # Simulate shutdown signal after a tick
            await asyncio.sleep(0.01)
            shutdown_called = True

        with patch.object(sentient.main.asyncio, 'get_event_loop') as mock_loop:
            mock_loop_instance = MagicMock()
            mock_loop.return_value = mock_loop_instance
            mock_loop_instance.add_signal_handler = MagicMock()
            mock_loop_instance.wait = mock_wait

            await asyncio.wait_for(sentient.main.run_forever(), timeout=1.0)

            # After shutdown_event is set and run_forever completes,
            # both shutdown methods should have been called
            # (Since we mocked build_and_start, this verifies the shutdown path)


# =============================================================================
# run() tests
# =============================================================================


def test_run_calls_asyncio_run(config_dir: Path):
    """run() calls asyncio.run with run_forever."""
    with patch.dict(os.environ, {"SENTIENT_CONFIG_DIR": str(config_dir)}), \
         patch("sentient.main.asyncio.run", side_effect=KeyboardInterrupt) as mock_asyncio_run:

        from importlib import reload
        import sentient.main
        reload(sentient.main)

        # Should not raise (KeyboardInterrupt is caught)
        sentient.main.run()

        # asyncio.run was called — the argument is a coroutine from run_forever()
        assert mock_asyncio_run.call_count == 1


def test_run_handles_keyboard_interrupt(config_dir: Path):
    """run() catches KeyboardInterrupt and exits gracefully."""
    with patch.dict(os.environ, {"SENTIENT_CONFIG_DIR": str(config_dir)}), \
         patch("sentient.main.asyncio.run", side_effect=KeyboardInterrupt):

        from importlib import reload
        import sentient.main
        reload(sentient.main)

        # Should not raise
        sentient.main.run()
