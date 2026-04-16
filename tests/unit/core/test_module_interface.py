"""Unit tests for module_interface.py.

Uses pytest + pytest-asyncio. Creates a minimal concrete subclass
(ModuleDouble) to test the abstract ModuleInterface contract.
Covers: lifecycle state transitions, health pulse, restart,
error tracking, and repr.
"""
from __future__ import annotations

import time
from typing import Any

import pytest

from sentient.core.module_interface import (
    HealthPulse,
    LifecycleState,
    ModuleInterface,
    ModuleStatus,
)


# ---------------------------------------------------------------------------
# Concrete test-double for the abstract ModuleInterface
# ---------------------------------------------------------------------------


class ModuleDouble(ModuleInterface):
    """Minimal concrete module for testing the lifecycle contract."""

    def __init__(self, name: str = "test_module", config: dict[str, Any] | None = None) -> None:
        super().__init__(name, config)
        self.initialized = False
        self.started = False
        self.shut_down = False

    async def initialize(self) -> None:
        """Mark as initialized."""
        self.state = LifecycleState.READY
        self.initialized = True

    async def start(self) -> None:
        """Mark as started."""
        self.state = LifecycleState.RUNNING
        self.started = True

    async def shutdown(self) -> None:
        """Mark as shut down."""
        self.state = LifecycleState.SHUTDOWN
        self.shut_down = True


class FailingModule(ModuleInterface):
    """A module whose initialize() always fails."""

    def __init__(self, name: str = "failing_module", config: dict[str, Any] | None = None) -> None:
        super().__init__(name, config)

    async def initialize(self) -> None:
        """Raise an error to simulate init failure."""
        self.state = LifecycleState.FAILED
        raise RuntimeError("Initialization failed")

    async def start(self) -> None:
        self.state = LifecycleState.RUNNING

    async def shutdown(self) -> None:
        self.state = LifecycleState.SHUTDOWN


# ---------------------------------------------------------------------------
# 1. Construction — initial state
# ---------------------------------------------------------------------------


def test_initial_state_is_uninitialized() -> None:
    """Module starts in UNINITIALIZED state."""
    mod = ModuleDouble()
    assert mod.state == LifecycleState.UNINITIALIZED


def test_initial_error_count_is_zero() -> None:
    """Module starts with zero error count."""
    mod = ModuleDouble()
    assert mod._error_count == 0


def test_initial_last_error_is_none() -> None:
    """Module starts with no last error."""
    mod = ModuleDouble()
    assert mod._last_error is None


def test_initial_health_status_is_healthy() -> None:
    """Module starts with HEALTHY status."""
    mod = ModuleDouble()
    assert mod._last_health_status == ModuleStatus.HEALTHY


def test_name_and_config_stored() -> None:
    """Name and config are stored from constructor."""
    mod = ModuleDouble(name="custom", config={"key": "val"})
    assert mod.name == "custom"
    assert mod.config == {"key": "val"}


def test_default_config_is_empty_dict() -> None:
    """Default config is an empty dict."""
    mod = ModuleDouble()
    assert mod.config == {}


# ---------------------------------------------------------------------------
# 2. Lifecycle transitions — initialize → start → shutdown
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_initialize_sets_ready_state() -> None:
    """After initialize(), state should be READY."""
    mod = ModuleDouble()
    await mod.initialize()
    assert mod.state == LifecycleState.READY
    assert mod.initialized is True


@pytest.mark.asyncio
async def test_start_sets_running_state() -> None:
    """After start(), state should be RUNNING."""
    mod = ModuleDouble()
    await mod.initialize()
    await mod.start()
    assert mod.state == LifecycleState.RUNNING
    assert mod.started is True


@pytest.mark.asyncio
async def test_shutdown_sets_shutdown_state() -> None:
    """After shutdown(), state should be SHUTDOWN."""
    mod = ModuleDouble()
    await mod.initialize()
    await mod.start()
    await mod.shutdown()
    assert mod.state == LifecycleState.SHUTDOWN
    assert mod.shut_down is True


@pytest.mark.asyncio
async def test_full_lifecycle_initialize_start_shutdown() -> None:
    """Complete lifecycle: uninitialized → ready → running → shutdown."""
    mod = ModuleDouble()

    assert mod.state == LifecycleState.UNINITIALIZED

    await mod.initialize()
    assert mod.state == LifecycleState.READY

    await mod.start()
    assert mod.state == LifecycleState.RUNNING

    await mod.shutdown()
    assert mod.state == LifecycleState.SHUTDOWN


# ---------------------------------------------------------------------------
# 3. Double-initialize behavior
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_double_initialize_is_idempotent() -> None:
    """Calling initialize() twice doesn't crash and resets to READY."""
    mod = ModuleDouble()
    await mod.initialize()
    assert mod.state == LifecycleState.READY

    # Second initialize — our test double just sets READY again
    await mod.initialize()
    assert mod.state == LifecycleState.READY
    assert mod.initialized is True


# ---------------------------------------------------------------------------
# 4. Failed initialization
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_failed_initialize_sets_failed_state() -> None:
    """If initialize() raises, state should be FAILED."""
    mod = FailingModule()

    with pytest.raises(RuntimeError, match="Initialization failed"):
        await mod.initialize()

    assert mod.state == LifecycleState.FAILED


# ---------------------------------------------------------------------------
# 5. Pause and resume
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pause_sets_paused_state() -> None:
    """pause() sets state to PAUSED (default implementation)."""
    mod = ModuleDouble()
    await mod.initialize()
    await mod.start()

    await mod.pause()
    assert mod.state == LifecycleState.PAUSED


@pytest.mark.asyncio
async def test_resume_sets_running_state() -> None:
    """resume() sets state back to RUNNING (default implementation)."""
    mod = ModuleDouble()
    await mod.initialize()
    await mod.start()

    await mod.pause()
    assert mod.state == LifecycleState.PAUSED

    await mod.resume()
    assert mod.state == LifecycleState.RUNNING


# ---------------------------------------------------------------------------
# 6. Health pulse
# ---------------------------------------------------------------------------


def test_health_pulse_returns_healthpulse_object() -> None:
    """health_pulse() returns a HealthPulse instance."""
    mod = ModuleDouble()
    pulse = mod.health_pulse()
    assert isinstance(pulse, HealthPulse)


def test_health_pulse_contains_module_name() -> None:
    """health_pulse() includes the module name."""
    mod = ModuleDouble(name="my_module")
    pulse = mod.health_pulse()
    assert pulse.module_name == "my_module"


def test_health_pulse_default_status_is_healthy() -> None:
    """health_pulse() starts with HEALTHY status."""
    mod = ModuleDouble()
    pulse = mod.health_pulse()
    assert pulse.status == ModuleStatus.HEALTHY


def test_health_pulse_includes_lifecycle_state() -> None:
    """health_pulse() metrics include current lifecycle state."""
    mod = ModuleDouble()
    pulse = mod.health_pulse()
    assert "lifecycle_state" in pulse.metrics
    assert pulse.metrics["lifecycle_state"] == "uninitialized"


def test_health_pulse_includes_error_count() -> None:
    """health_pulse() metrics include error count."""
    mod = ModuleDouble()
    pulse = mod.health_pulse()
    assert "error_count" in pulse.metrics
    assert pulse.metrics["error_count"] == 0


def test_health_pulse_includes_last_error() -> None:
    """health_pulse() metrics include last error (initially None)."""
    mod = ModuleDouble()
    pulse = mod.health_pulse()
    assert "last_error" in pulse.metrics
    assert pulse.metrics["last_error"] is None


def test_health_pulse_shape_matches_inference_gateway() -> None:
    """Health pulse shape is consistent with InferenceGateway's pulse.

    Both include module_name, status, and metrics dict.
    InferenceGateway adds domain-specific metrics; ModuleInterface
    provides lifecycle_state, error_count, last_error.
    """
    mod = ModuleDouble()
    pulse = mod.health_pulse()
    pulse_dict = pulse.to_dict()

    # Must have these top-level keys
    assert "module_name" in pulse_dict
    assert "status" in pulse_dict
    assert "timestamp" in pulse_dict
    assert "metrics" in pulse_dict
    assert "notes" in pulse_dict


def test_health_pulse_to_dict() -> None:
    """HealthPulse.to_dict() serializes all fields correctly."""
    pulse = HealthPulse(
        module_name="test",
        status=ModuleStatus.DEGRADED,
        metrics={"latency_ms": 150},
        notes="running slow",
    )
    d = pulse.to_dict()

    assert d["module_name"] == "test"
    assert d["status"] == "degraded"
    assert d["metrics"]["latency_ms"] == 150
    assert d["notes"] == "running slow"
    assert isinstance(d["timestamp"], float)


def test_health_pulse_timestamp_is_current_time() -> None:
    """HealthPulse default timestamp is close to current time."""
    before = time.time()
    pulse = HealthPulse(module_name="test", status=ModuleStatus.HEALTHY)
    after = time.time()

    assert before <= pulse.timestamp <= after


# ---------------------------------------------------------------------------
# 7. set_status and error tracking
# ---------------------------------------------------------------------------


def test_set_status_healthy() -> None:
    """Setting HEALTHY status doesn't increment error count."""
    mod = ModuleDouble()
    mod.set_status(ModuleStatus.HEALTHY)
    assert mod._last_health_status == ModuleStatus.HEALTHY
    assert mod._error_count == 0


def test_set_status_error_increments_count() -> None:
    """Setting ERROR status increments error count and records note."""
    mod = ModuleDouble()
    mod.set_status(ModuleStatus.ERROR, "something broke")

    assert mod._last_health_status == ModuleStatus.ERROR
    assert mod._error_count == 1
    assert mod._last_error == "something broke"


def test_set_status_critical_increments_count() -> None:
    """Setting CRITICAL status increments error count and records note."""
    mod = ModuleDouble()
    mod.set_status(ModuleStatus.CRITICAL, "system on fire")

    assert mod._last_health_status == ModuleStatus.CRITICAL
    assert mod._error_count == 1
    assert mod._last_error == "system on fire"


def test_set_status_degraded_no_error_increment() -> None:
    """DEGRADED status does not increment error count."""
    mod = ModuleDouble()
    mod.set_status(ModuleStatus.DEGRADED)
    assert mod._last_health_status == ModuleStatus.DEGRADED
    assert mod._error_count == 0


def test_multiple_errors_accumulate() -> None:
    """Multiple error status changes accumulate error count."""
    mod = ModuleDouble()
    mod.set_status(ModuleStatus.ERROR, "err1")
    mod.set_status(ModuleStatus.CRITICAL, "err2")
    mod.set_status(ModuleStatus.ERROR, "err3")

    assert mod._error_count == 3
    assert mod._last_error == "err3"


# ---------------------------------------------------------------------------
# 8. reset_error_count
# ---------------------------------------------------------------------------


def test_reset_error_count_clears_errors() -> None:
    """reset_error_count() sets count to 0 and clears last error."""
    mod = ModuleDouble()
    mod.set_status(ModuleStatus.ERROR, "bad")
    assert mod._error_count == 1

    mod.reset_error_count()

    assert mod._error_count == 0
    assert mod._last_error is None


# ---------------------------------------------------------------------------
# 9. Restart
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_restart_goes_through_shutdown_initialize_start() -> None:
    """restart() calls shutdown → initialize → start in sequence."""
    mod = ModuleDouble()
    await mod.initialize()
    await mod.start()

    assert mod.state == LifecycleState.RUNNING

    await mod.restart()

    # After restart, module should be running again
    assert mod.state == LifecycleState.RUNNING
    assert mod.initialized is True
    assert mod.started is True
    assert mod.shut_down is True  # shutdown was called during restart


@pytest.mark.asyncio
async def test_restart_resets_error_count() -> None:
    """restart() resets error count after restart."""
    mod = ModuleDouble()
    await mod.initialize()
    await mod.start()

    mod.set_status(ModuleStatus.ERROR, "something failed")
    assert mod._error_count == 1

    await mod.restart()

    assert mod._error_count == 0
    assert mod._last_error is None


@pytest.mark.asyncio
async def test_restart_handles_shutdown_failure() -> None:
    """restart() continues even if shutdown raises (best-effort)."""
    # ModuleDouble's shutdown succeeds, but let's test with a module
    # where shutdown could fail. The base implementation catches exceptions.
    class BadShutdownModule(ModuleDouble):
        async def shutdown(self) -> None:
            raise RuntimeError("shutdown failed!")

    mod = BadShutdownModule()
    await mod.initialize()
    await mod.start()

    # restart should not raise even if shutdown fails
    await mod.restart()

    # Module should still be re-initialized and started
    assert mod.state == LifecycleState.RUNNING


# ---------------------------------------------------------------------------
# 10. Repr
# ---------------------------------------------------------------------------


def test_repr_shows_name_state_status() -> None:
    """__repr__ includes name, state, and status."""
    mod = ModuleDouble(name="test_mod")
    result = repr(mod)

    assert "test_mod" in result
    assert "uninitialized" in result
    assert "healthy" in result


@pytest.mark.asyncio
async def test_repr_updates_after_state_change() -> None:
    """repr reflects current state after lifecycle transitions."""
    mod = ModuleDouble(name="my_mod")

    result_init = repr(mod)
    assert "uninitialized" in result_init

    await mod.initialize()
    result_ready = repr(mod)
    assert "ready" in result_ready

    await mod.start()
    result_running = repr(mod)
    assert "running" in result_running


# ---------------------------------------------------------------------------
# 11. Enums
# ---------------------------------------------------------------------------


def test_module_status_values() -> None:
    """ModuleStatus enum has expected values."""
    assert ModuleStatus.HEALTHY.value == "healthy"
    assert ModuleStatus.DEGRADED.value == "degraded"
    assert ModuleStatus.ERROR.value == "error"
    assert ModuleStatus.CRITICAL.value == "critical"
    assert ModuleStatus.UNRESPONSIVE.value == "unresponsive"


def test_lifecycle_state_values() -> None:
    """LifecycleState enum has expected values."""
    assert LifecycleState.UNINITIALIZED.value == "uninitialized"
    assert LifecycleState.INITIALIZING.value == "initializing"
    assert LifecycleState.READY.value == "ready"
    assert LifecycleState.RUNNING.value == "running"
    assert LifecycleState.PAUSING.value == "pausing"
    assert LifecycleState.PAUSED.value == "paused"
    assert LifecycleState.RESUMING.value == "resuming"
    assert LifecycleState.SHUTTING_DOWN.value == "shutting_down"
    assert LifecycleState.SHUTDOWN.value == "shutdown"
    assert LifecycleState.FAILED.value == "failed"


def test_health_pulse_default_metrics_dict() -> None:
    """HealthPulse with default metrics has empty dict."""
    pulse = HealthPulse(module_name="test", status=ModuleStatus.HEALTHY)
    assert pulse.metrics == {}
    assert pulse.notes == ""


def test_set_status_with_empty_note_for_error() -> None:
    """Setting ERROR without a note still increments count."""
    mod = ModuleDouble()
    mod.set_status(ModuleStatus.ERROR)
    assert mod._error_count == 1
    assert mod._last_error == ""