"""Unit tests for src/sentient/main.py — achieves >=50% coverage."""
from __future__ import annotations

import asyncio
import os
import signal
from contextlib import ExitStack
from pathlib import Path
from typing import Any
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
# Helpers
# =============================================================================

# All module-class names that main.py imports at the top level and uses in
# build_and_start().  Keeping this list in one place avoids the Python
# static-nesting-limit error that long ``with`` chains produce.
_MODULE_PATCH_TARGETS = [
    "InferenceGateway",
    "MemoryArchitecture",
    "PersonaManager",
    "HealthPulseNetwork",
    "InnateResponse",
    "Thalamus",
    "Checkpost",
    "QueueZone",
    "TemporalLimbicProcessor",
    "CognitiveCore",
    "WorldModel",
    "HarnessAdapter",
    "Brainstem",
    "SleepScheduler",
    # Sleep sub-components instantiated by build_and_start
    "ConsolidationEngine",
    "ContradictionResolver",
    "WMCalibrator",
    "ProceduralRefiner",
    "IdentityDriftDetector",
    "DevelopmentalConsolidator",
    # Decision arbiter
    "DecisionArbiter",
    # I/O plugins
    "ChatInputPlugin",
    "ChatOutputPlugin",
]


def _apply_module_patches(stack: ExitStack) -> tuple[dict[str, MagicMock], MagicMock]:
    """Enter patch contexts for all module classes and return (name→mock, event_bus_mock)."""
    mocks: dict[str, MagicMock] = {}
    for name in _MODULE_PATCH_TARGETS:
        m = stack.enter_context(patch(f"sentient.main.{name}"))
        mocks[name] = m
    event_bus_mock = stack.enter_context(patch("sentient.main.get_event_bus"))
    return mocks, event_bus_mock


# Mapping from patch target names to the actual .name attribute that real
# modules use (snake_case).  Used so lifecycle._essential_modules matches
# production code.
_NAME_MAP = {
    "InferenceGateway": "inference_gateway",
    "MemoryArchitecture": "memory",
    "PersonaManager": "persona",
    "HealthPulseNetwork": "health_pulse_network",
    "InnateResponse": "innate_response",
    "Thalamus": "thalamus",
    "Checkpost": "checkpost",
    "QueueZone": "queue_zone",
    "TemporalLimbicProcessor": "tlp",
    "CognitiveCore": "cognitive_core",
    "WorldModel": "world_model",
    "HarnessAdapter": "harness_adapter",
    "Brainstem": "brainstem",
    "SleepScheduler": "sleep_scheduler",
    "ConsolidationEngine": "consolidation_engine",
    "ContradictionResolver": "contradiction_resolver",
    "WMCalibrator": "wm_calibrator",
    "ProceduralRefiner": "procedural_refiner",
    "IdentityDriftDetector": "identity_drift_detector",
    "DevelopmentalConsolidator": "developmental_consolidator",
    "DecisionArbiter": "decision_arbiter",
    "ChatInputPlugin": "chat_input",
    "ChatOutputPlugin": "chat_output",
}


def _configure_default_mocks(mocks: dict[str, MagicMock]) -> None:
    """Set .return_value on every mock and wire up async lifecycle methods."""
    for name, m in mocks.items():
        instance = MagicMock(name=name)
        # LifecycleManager awaits initialize(), start(), shutdown()
        instance.initialize = AsyncMock()
        instance.start = AsyncMock()
        instance.shutdown = AsyncMock()
        # LifecycleManager reads .name as the registry key — use real module names
        instance.name = _NAME_MAP.get(name, name)
        # LifecycleManager sets .state and calls .set_status() on failure
        instance.state = MagicMock()
        instance.set_status = MagicMock()
        m.return_value = instance

    # Thalamus and Brainstem need async register_plugin
    mocks["Thalamus"].return_value.register_plugin = AsyncMock()
    mocks["Brainstem"].return_value.register_plugin = AsyncMock()

    # Chat plugins need async register_plugin
    mocks["ChatInputPlugin"].return_value.register_plugin = AsyncMock()
    mocks["ChatOutputPlugin"].return_value.register_plugin = AsyncMock()


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
@pytest.mark.skipif(
    os.environ.get("CI") == "true",
    reason="Requires full module import (chromadb/sentence_transformers); too heavy for CI",
)
async def test_build_and_start_registers_all_modules_with_lifecycle(config_dir: Path):
    """build_and_start registers all modules with the LifecycleManager."""
    mock_modules = {}

    def make_mock(name: str):
        m = _MockModule(name)
        mock_modules[name] = m
        return m

    # Create mock classes that return our mock modules
    mock_classes = {}
    for name in _MODULE_PATCH_TARGETS:
        if name in ("ChatInputPlugin", "ChatOutputPlugin"):
            continue
        mock_cls = MagicMock()
        mock_instance = make_mock(name.lower())
        mock_cls.return_value = mock_instance
        mock_classes[name] = mock_cls

    mock_api_server = MagicMock()
    mock_api_server.host = "127.0.0.1"
    mock_api_server.port = 8080
    mock_api_server.start = AsyncMock()
    mock_api_server.shutdown = AsyncMock()

    # Reload BEFORE patching so reload doesn't overwrite our mocks
    from importlib import reload
    import sentient.main
    reload(sentient.main)

    with ExitStack() as stack:
        stack.enter_context(patch.dict(os.environ, {"SENTIENT_CONFIG_DIR": str(config_dir)}))
        for name, mock_cls in mock_classes.items():
            stack.enter_context(patch(f"sentient.main.{name}", mock_cls))
        mock_chat_input = stack.enter_context(patch("sentient.main.ChatInputPlugin"))
        mock_chat_output = stack.enter_context(patch("sentient.main.ChatOutputPlugin"))
        stack.enter_context(patch("sentient.api.server.APIServer", return_value=mock_api_server))
        mock_get_event_bus = stack.enter_context(patch("sentient.main.get_event_bus"))

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

        # Configure event bus mock with async publish
        mock_event_bus = MagicMock()
        mock_event_bus.publish = AsyncMock()
        mock_get_event_bus.return_value = mock_event_bus

        lifecycle, api_server = await sentient.main.build_and_start()

        # Verify lifecycle has modules registered
        registered_names = list(lifecycle._modules.keys())
        # At minimum, essential modules should be registered
        assert len(registered_names) >= 5


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.environ.get("CI") == "true",
    reason="Requires full module import; too heavy for CI",
)
async def test_build_and_start_creates_data_directory(config_dir: Path):
    """build_and_start creates the data directory and logs subdirectory."""
    # config_dir is tmp_path / "config"; the YAML sets data_dir to tmp_path / "data"
    data_dir = config_dir.parent / "data"

    mock_api_server = MagicMock()
    mock_api_server.host = "127.0.0.1"
    mock_api_server.port = 8080
    mock_api_server.start = AsyncMock()
    mock_api_server.shutdown = AsyncMock()

    # Reload BEFORE patching so reload doesn't overwrite our mocks
    from importlib import reload
    import sentient.main
    reload(sentient.main)

    with ExitStack() as stack:
        stack.enter_context(patch.dict(os.environ, {"SENTIENT_CONFIG_DIR": str(config_dir)}))
        mocks, mock_get_event_bus = _apply_module_patches(stack)
        _configure_default_mocks(mocks)
        stack.enter_context(patch("sentient.api.server.APIServer", return_value=mock_api_server))
        # Configure event bus mock with async publish
        mock_event_bus = MagicMock()
        mock_event_bus.publish = AsyncMock()
        mock_get_event_bus.return_value = mock_event_bus

        await sentient.main.build_and_start()

        assert data_dir.exists()
        assert (data_dir / "logs").exists()


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.environ.get("CI") == "true",
    reason="Requires full module import; too heavy for CI",
)
async def test_build_and_start_registers_essential_modules(config_dir: Path):
    """build_and_start marks essential modules as essential in LifecycleManager."""
    mock_api_server = MagicMock()
    mock_api_server.host = "127.0.0.1"
    mock_api_server.port = 8080
    mock_api_server.start = AsyncMock()
    mock_api_server.shutdown = AsyncMock()

    # Reload BEFORE patching so reload doesn't overwrite our mocks
    from importlib import reload
    import sentient.main
    reload(sentient.main)

    with ExitStack() as stack:
        stack.enter_context(patch.dict(os.environ, {"SENTIENT_CONFIG_DIR": str(config_dir)}))
        mocks, mock_get_event_bus = _apply_module_patches(stack)
        _configure_default_mocks(mocks)
        stack.enter_context(patch("sentient.api.server.APIServer", return_value=mock_api_server))
        # Configure event bus mock with async publish
        mock_event_bus = MagicMock()
        mock_event_bus.publish = AsyncMock()
        mock_get_event_bus.return_value = mock_event_bus

        lifecycle, _ = await sentient.main.build_and_start()

        # Verify essential modules are marked using actual module names
        for name in ["inference_gateway", "memory", "persona",
                      "health_pulse_network", "innate_response", "sleep_scheduler"]:
            assert name in lifecycle._essential_modules


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.environ.get("CI") == "true",
    reason="Requires full module import; too heavy for CI",
)
async def test_build_and_start_calls_lifecycle_startup(config_dir: Path):
    """build_and_start calls lifecycle.startup() after registering modules."""
    mock_api_server = MagicMock()
    mock_api_server.host = "127.0.0.1"
    mock_api_server.port = 8080
    mock_api_server.start = AsyncMock()
    mock_api_server.shutdown = AsyncMock()

    # Reload BEFORE patching so reload doesn't overwrite our mocks
    from importlib import reload
    import sentient.main
    reload(sentient.main)

    with ExitStack() as stack:
        stack.enter_context(patch.dict(os.environ, {"SENTIENT_CONFIG_DIR": str(config_dir)}))
        mocks, mock_get_event_bus = _apply_module_patches(stack)
        _configure_default_mocks(mocks)
        stack.enter_context(patch("sentient.api.server.APIServer", return_value=mock_api_server))
        # Configure event bus mock with async publish
        mock_event_bus = MagicMock()
        mock_event_bus.publish = AsyncMock()
        mock_get_event_bus.return_value = mock_event_bus

        lifecycle, _ = await sentient.main.build_and_start()

        # startup should have been called (lifecycle._running should be True)
        assert lifecycle.is_running() is True


# =============================================================================
# run_forever() tests
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.environ.get("CI") == "true",
    reason="Requires full module import; too heavy for CI",
)
async def test_run_forever_sets_up_signal_handlers(config_dir: Path):
    """run_forever sets up SIGINT and SIGTERM handlers."""
    mock_api_server = MagicMock()
    mock_api_server.host = "127.0.0.1"
    mock_api_server.port = 8080
    mock_api_server.start = AsyncMock()
    mock_api_server.shutdown = AsyncMock()

    # Reload BEFORE patching so reload doesn't overwrite our mocks
    from importlib import reload
    import sentient.main
    reload(sentient.main)

    with patch.dict(os.environ, {"SENTIENT_CONFIG_DIR": str(config_dir)}), \
         patch("sentient.main.build_and_start") as mock_bas, \
         patch("sentient.main.asyncio.get_event_loop") as mock_get_loop:

        mock_lifecycle = MagicMock()
        mock_lifecycle.is_running.return_value = False
        mock_lifecycle.shutdown = AsyncMock()
        mock_bas.return_value = (mock_lifecycle, mock_api_server)

        # Capture signal handlers registered by run_forever so we can trigger them
        registered_handlers: dict[int, Any] = {}
        mock_loop_instance = MagicMock()
        mock_get_loop.return_value = mock_loop_instance
        mock_loop_instance.add_signal_handler = MagicMock(
            side_effect=lambda sig, handler: registered_handlers.update({sig: handler})
        )

        async def trigger_shutdown_soon():
            """Fire the captured signal handler shortly after run_forever starts."""
            await asyncio.sleep(0.05)
            # Call the handler that run_forever registered (sets its internal shutdown_event)
            for handler in registered_handlers.values():
                handler()

        run_forever_task = asyncio.create_task(sentient.main.run_forever())
        trigger_task = asyncio.create_task(trigger_shutdown_soon())

        await asyncio.wait_for(asyncio.gather(run_forever_task, trigger_task), timeout=2.0)

        # Verify signal handlers were registered for both signals
        calls = mock_loop_instance.add_signal_handler.call_args_list
        sigs_registered = [call[0][0] for call in calls]
        assert signal.SIGINT in sigs_registered
        assert signal.SIGTERM in sigs_registered


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.environ.get("CI") == "true",
    reason="Requires full module import; too heavy for CI",
)
async def test_run_forever_shuts_down_on_signal(config_dir: Path):
    """run_forever calls shutdown on api_server and lifecycle after signal."""
    mock_api_server = MagicMock()
    mock_api_server.host = "127.0.0.1"
    mock_api_server.port = 8080
    mock_api_server.start = AsyncMock()
    mock_api_server.shutdown = AsyncMock()

    # Reload BEFORE patching so reload doesn't overwrite our mocks
    from importlib import reload
    import sentient.main
    reload(sentient.main)

    with patch.dict(os.environ, {"SENTIENT_CONFIG_DIR": str(config_dir)}), \
         patch("sentient.main.build_and_start") as mock_bas, \
         patch("sentient.main.asyncio.get_event_loop") as mock_get_loop:

        mock_lifecycle = MagicMock()
        mock_lifecycle.is_running.return_value = False
        mock_lifecycle.shutdown = AsyncMock()
        mock_bas.return_value = (mock_lifecycle, mock_api_server)

        # Capture signal handlers registered by run_forever so we can trigger them
        registered_handlers: dict[int, Any] = {}
        mock_loop_instance = MagicMock()
        mock_get_loop.return_value = mock_loop_instance
        mock_loop_instance.add_signal_handler = MagicMock(
            side_effect=lambda sig, handler: registered_handlers.update({sig: handler})
        )

        async def trigger_shutdown_soon():
            """Fire the captured signal handler shortly after run_forever starts."""
            await asyncio.sleep(0.05)
            for handler in registered_handlers.values():
                handler()

        run_forever_task = asyncio.create_task(sentient.main.run_forever())
        trigger_task = asyncio.create_task(trigger_shutdown_soon())

        await asyncio.wait_for(asyncio.gather(run_forever_task, trigger_task), timeout=2.0)

        # After shutdown signal fires, both shutdown methods should have been called
        mock_api_server.shutdown.assert_awaited_once()
        mock_lifecycle.shutdown.assert_awaited_once()


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