"""Unit tests for pulse_network.py and registry.py.

Covers:
  - HealthRegistry: record_pulse, latest_pulse, recent_pulses, check_unresponsive,
    status_of, snapshot, all_statuses, set_expected_interval
  - HealthPulseNetwork: __init__, initialize, start, shutdown,
    _poll_loop (status changes, unresponsive detection, anomaly publishing),
    _publish_anomaly, snapshot, all_statuses, health_pulse
"""
from __future__ import annotations

import asyncio
import time
from unittest.mock import MagicMock, PropertyMock

import pytest

from sentient.core.event_bus import EventBus
from sentient.core.module_interface import HealthPulse, ModuleStatus
from sentient.health.pulse_network import HealthPulseNetwork
from sentient.health.registry import HealthRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_pulse(
    module_name: str,
    status: ModuleStatus = ModuleStatus.HEALTHY,
    timestamp: float | None = None,
    metrics: dict | None = None,
    notes: str = "",
) -> HealthPulse:
    """Create a HealthPulse with sensible defaults."""
    return HealthPulse(
        module_name=module_name,
        status=status,
        timestamp=timestamp if timestamp is not None else time.time(),
        metrics=metrics or {},
        notes=notes,
    )


def make_mock_module(name: str, status: ModuleStatus = ModuleStatus.HEALTHY) -> MagicMock:
    """Create a mock module that returns a given health status."""
    mod = MagicMock()
    # Use PropertyMock so name is a real str, not a MagicMock (important for set membership checks)
    type(mod).name = PropertyMock(return_value=name)
    mod.health_pulse = MagicMock(return_value=make_pulse(name, status))
    return mod


# ---------------------------------------------------------------------------
# HealthRegistry — core recording
# ---------------------------------------------------------------------------


class TestHealthRegistryRecordPulse:
    """Tests for HealthRegistry.record_pulse."""

    def test_record_pulse_stores_latest(self) -> None:
        reg = HealthRegistry()
        pulse = make_pulse("test_module", ModuleStatus.HEALTHY)

        reg.record_pulse(pulse)

        assert reg.latest_pulse("test_module") is pulse

    def test_record_pulse_multiple_modules(self) -> None:
        reg = HealthRegistry()
        pulse_a = make_pulse("module_a", ModuleStatus.HEALTHY)
        pulse_b = make_pulse("module_b", ModuleStatus.DEGRADED)

        reg.record_pulse(pulse_a)
        reg.record_pulse(pulse_b)

        assert reg.latest_pulse("module_a") is pulse_a
        assert reg.latest_pulse("module_b") is pulse_b

    def test_record_pulse_replaces_unresponsive_flag(self) -> None:
        reg = HealthRegistry()
        # First, record a stale pulse so check_unresponsive flags the module
        reg.set_expected_interval("lazy_module", 1.0)
        old_pulse = make_pulse("lazy_module", timestamp=time.time() - 10.0)
        reg.record_pulse(old_pulse)
        reg.check_unresponsive(3.0)
        assert "lazy_module" in reg._unresponsive_modules

        # Now record a fresh pulse → flag should be cleared
        reg.record_pulse(make_pulse("lazy_module", ModuleStatus.HEALTHY))
        assert "lazy_module" not in reg._unresponsive_modules


class TestHealthRegistryLatestPulse:
    """Tests for HealthRegistry.latest_pulse."""

    def test_latest_pulse_returns_most_recent(self) -> None:
        reg = HealthRegistry()
        old = make_pulse("mod", ModuleStatus.HEALTHY, timestamp=100.0)
        new = make_pulse("mod", ModuleStatus.HEALTHY, timestamp=200.0)

        reg.record_pulse(old)
        reg.record_pulse(new)

        assert reg.latest_pulse("mod") is new

    def test_latest_pulse_unknown_module_returns_none(self) -> None:
        reg = HealthRegistry()
        assert reg.latest_pulse("never_seen") is None


class TestHealthRegistryRecentPulses:
    """Tests for HealthRegistry.recent_pulses."""

    def test_recent_pulses_returns_last_n(self) -> None:
        reg = HealthRegistry()
        for i in range(20):
            reg.record_pulse(make_pulse("mod", timestamp=float(i)))

        result = reg.recent_pulses("mod", count=5)

        assert len(result) == 5

    def test_recent_pulses_fewer_than_count_returns_all(self) -> None:
        reg = HealthRegistry()
        reg.record_pulse(make_pulse("mod", timestamp=1.0))
        reg.record_pulse(make_pulse("mod", timestamp=2.0))

        result = reg.recent_pulses("mod", count=10)

        assert len(result) == 2

    def test_recent_pulses_unknown_module_returns_empty(self) -> None:
        reg = HealthRegistry()
        assert reg.recent_pulses("ghost") == []


class TestHealthRegistryCheckUnresponsive:
    """Tests for HealthRegistry.check_unresponsive."""

    def test_responsive_module_not_flagged(self) -> None:
        reg = HealthRegistry()
        reg.set_expected_interval("healthy_mod", 5.0)
        reg.record_pulse(make_pulse("healthy_mod", timestamp=time.time()))

        unresponsive = reg.check_unresponsive(3.0)

        assert "healthy_mod" not in unresponsive

    def test_stale_pulse_flagged(self) -> None:
        reg = HealthRegistry()
        reg.set_expected_interval("stale_mod", 1.0)  # expect pulse every 1s
        old_timestamp = time.time() - 10.0  # last pulse was 10s ago
        reg.record_pulse(make_pulse("stale_mod", timestamp=old_timestamp))

        unresponsive = reg.check_unresponsive(3.0)

        assert "stale_mod" in unresponsive

    def test_no_pulse_recorded_not_flagged_by_check(self) -> None:
        """Modules with no recorded pulse are skipped by check_unresponsive
        (they may not have started yet). status_of returns UNRESPONSIVE for them."""
        reg = HealthRegistry()
        reg.set_expected_interval("silent_mod", 1.0)
        # Do NOT record any pulse

        unresponsive = reg.check_unresponsive(3.0)

        # check_unresponsive skips modules with no pulses
        assert "silent_mod" not in unresponsive
        # But status_of returns UNRESPONSIVE for unknown modules
        assert reg.status_of("silent_mod") == ModuleStatus.UNRESPONSIVE

    def test_check_unresponsive_returns_list(self) -> None:
        reg = HealthRegistry()
        reg.set_expected_interval("mod1", 1.0)
        reg.set_expected_interval("mod2", 1.0)
        reg.record_pulse(make_pulse("mod1", timestamp=time.time() - 10.0))
        reg.record_pulse(make_pulse("mod2", timestamp=time.time()))  # healthy

        unresponsive = reg.check_unresponsive(3.0)

        assert isinstance(unresponsive, list)
        assert "mod1" in unresponsive
        assert "mod2" not in unresponsive


class TestHealthRegistryStatusOf:
    """Tests for HealthRegistry.status_of."""

    def test_status_of_healthy_module(self) -> None:
        reg = HealthRegistry()
        reg.record_pulse(make_pulse("mod", ModuleStatus.HEALTHY))

        assert reg.status_of("mod") == ModuleStatus.HEALTHY

    def test_status_of_degraded_module(self) -> None:
        reg = HealthRegistry()
        reg.record_pulse(make_pulse("mod", ModuleStatus.DEGRADED))

        assert reg.status_of("mod") == ModuleStatus.DEGRADED

    def test_status_of_unresponsive_module(self) -> None:
        reg = HealthRegistry()
        reg.set_expected_interval("mod", 1.0)
        reg.record_pulse(make_pulse("mod", timestamp=time.time() - 10.0))
        reg.check_unresponsive(3.0)

        assert reg.status_of("mod") == ModuleStatus.UNRESPONSIVE

    def test_status_of_unknown_module_is_unresponsive(self) -> None:
        reg = HealthRegistry()
        assert reg.status_of("never_registered") == ModuleStatus.UNRESPONSIVE


class TestHealthRegistrySnapshot:
    """Tests for HealthRegistry.snapshot."""

    def test_snapshot_includes_all_modules(self) -> None:
        reg = HealthRegistry()
        reg.record_pulse(make_pulse("mod_a", ModuleStatus.HEALTHY))
        reg.record_pulse(make_pulse("mod_b", ModuleStatus.DEGRADED))

        snap = reg.snapshot()

        assert "mod_a" in snap
        assert "mod_b" in snap
        assert snap["mod_a"]["status"] == "healthy"
        assert snap["mod_b"]["status"] == "degraded"

    def test_snapshot_includes_pulse_count(self) -> None:
        reg = HealthRegistry()
        for _ in range(5):
            reg.record_pulse(make_pulse("mod", ModuleStatus.HEALTHY))

        snap = reg.snapshot()

        assert snap["mod"]["pulse_count"] == 5


class TestHealthRegistryAllStatuses:
    """Tests for HealthRegistry.all_statuses."""

    def test_all_statuses_returns_dict_str_str(self) -> None:
        reg = HealthRegistry()
        reg.record_pulse(make_pulse("mod_a", ModuleStatus.HEALTHY))
        reg.record_pulse(make_pulse("mod_b", ModuleStatus.ERROR))

        statuses = reg.all_statuses()

        assert isinstance(statuses, dict)
        assert all(isinstance(v, str) for v in statuses.values())
        assert statuses["mod_a"] == "healthy"
        assert statuses["mod_b"] == "error"


# ---------------------------------------------------------------------------
# HealthPulseNetwork — construction
# ---------------------------------------------------------------------------


class TestHealthPulseNetworkInit:
    """Tests for HealthPulseNetwork.__init__."""

    def test_init_sets_intervals_from_config(self) -> None:
        config = {
            "pulse": {
                "default_interval_seconds": 10,
                "critical_module_interval_seconds": 2,
                "missed_pulse_multiplier": 5,
            }
        }
        lifecycle = MagicMock()
        net = HealthPulseNetwork(config, lifecycle)

        assert net.default_interval == 10
        assert net.critical_interval == 2
        assert net.missed_multiplier == 5

    def test_init_defaults_if_no_config(self) -> None:
        lifecycle = MagicMock()
        net = HealthPulseNetwork({}, lifecycle)

        assert net.default_interval == 30
        assert net.critical_interval == 5
        assert net.missed_multiplier == 3

    def test_init_critical_modules_hardcoded(self) -> None:
        lifecycle = MagicMock()
        net = HealthPulseNetwork({}, lifecycle)

        assert net.critical_modules == {"inference_gateway", "memory", "thalamus"}

    def test_init_creates_registry(self) -> None:
        lifecycle = MagicMock()
        net = HealthPulseNetwork({}, lifecycle)

        assert isinstance(net.registry, HealthRegistry)

    def test_init_uses_provided_event_bus(self) -> None:
        lifecycle = MagicMock()
        bus = EventBus()
        net = HealthPulseNetwork({}, lifecycle, event_bus=bus)

        assert net.event_bus is bus


# ---------------------------------------------------------------------------
# HealthPulseNetwork — initialize
# ---------------------------------------------------------------------------


class TestHealthPulseNetworkInitialize:
    """Tests for HealthPulseNetwork.initialize."""

    @pytest.mark.asyncio
    async def test_initialize_sets_intervals_for_all_modules(self) -> None:
        crit_mod = make_mock_module("inference_gateway", ModuleStatus.HEALTHY)
        reg_mod = make_mock_module("regular_mod", ModuleStatus.HEALTHY)

        lifecycle = MagicMock()
        lifecycle.all_modules.return_value = [crit_mod, reg_mod]

        net = HealthPulseNetwork({}, lifecycle)
        await net.initialize()

        # Critical module gets critical_interval (5)
        assert net.registry._expected_intervals["inference_gateway"] == 5
        # Regular module gets default_interval (30)
        assert net.registry._expected_intervals["regular_mod"] == 30

    @pytest.mark.asyncio
    async def test_initialize_sets_critical_interval_for_memory_module(self) -> None:
        mem_mod = make_mock_module("memory", ModuleStatus.HEALTHY)
        lifecycle = MagicMock()
        lifecycle.all_modules.return_value = [mem_mod]

        net = HealthPulseNetwork({}, lifecycle)
        await net.initialize()

        assert net.registry._expected_intervals["memory"] == 5


# ---------------------------------------------------------------------------
# HealthPulseNetwork — lifecycle (start/shutdown)
# ---------------------------------------------------------------------------


class TestHealthPulseNetworkLifecycle:
    """Tests for HealthPulseNetwork.start and shutdown."""

    @pytest.mark.asyncio
    async def test_shutdown_cancels_poll_task(self) -> None:
        lifecycle = MagicMock()
        lifecycle.all_modules.return_value = []
        net = HealthPulseNetwork({}, lifecycle)
        await net.initialize()
        await net.start()

        await net.shutdown()

        # After cancel, the task transitions to cancelled state
        await asyncio.sleep(0.05)
        assert net._poll_task.done()

    @pytest.mark.asyncio
    async def test_start_creates_poll_task(self) -> None:
        lifecycle = MagicMock()
        lifecycle.all_modules.return_value = []
        net = HealthPulseNetwork({}, lifecycle)
        await net.initialize()

        await net.start()

        assert net._poll_task is not None
        assert not net._poll_task.done()

        await net.shutdown()
        # After shutdown, task should be cancelled
        await asyncio.sleep(0.05)
        assert net._poll_task.done()

    @pytest.mark.asyncio
    async def test_health_pulse_returns_network_status(self) -> None:
        lifecycle = MagicMock()
        lifecycle.all_modules.return_value = []
        net = HealthPulseNetwork({}, lifecycle)
        await net.initialize()
        await net.start()

        pulse = net.health_pulse()

        assert pulse.module_name == "health_pulse_network"
        assert "modules_monitored" in pulse.metrics

        await net.shutdown()


# ---------------------------------------------------------------------------
# HealthPulseNetwork — _poll_loop and anomaly detection
# ---------------------------------------------------------------------------


class TestHealthPulseNetworkPollLoop:
    """Tests for HealthPulseNetwork._poll_loop."""

    @pytest.mark.asyncio
    async def test_poll_loop_records_pulses_from_modules(self) -> None:
        # Modules that will respond
        mod_a = make_mock_module("mod_a", ModuleStatus.HEALTHY)
        mod_b = make_mock_module("mod_b", ModuleStatus.DEGRADED)

        lifecycle = MagicMock()
        lifecycle.all_modules.return_value = [mod_a, mod_b]

        # Use short intervals so test runs fast
        config = {
            "pulse": {
                "default_interval_seconds": 0.05,
                "critical_module_interval_seconds": 0.05,
                "missed_pulse_multiplier": 3,
            }
        }
        net = HealthPulseNetwork(config, lifecycle)
        await net.initialize()
        await net.start()

        # Let the poll loop run for a short time
        await asyncio.sleep(0.25)

        # Both modules should have been polled and pulses recorded
        assert net.registry.latest_pulse("mod_a") is not None
        assert net.registry.latest_pulse("mod_b") is not None

        await net.shutdown()

    @pytest.mark.asyncio
    async def test_poll_loop_skips_self(self) -> None:
        """The network should not poll itself."""
        self_mod = make_mock_module("health_pulse_network", ModuleStatus.HEALTHY)

        lifecycle = MagicMock()
        lifecycle.all_modules.return_value = [self_mod]

        config = {"pulse": {"critical_module_interval_seconds": 0.05}}
        net = HealthPulseNetwork(config, lifecycle)
        await net.initialize()
        await net.start()

        await asyncio.sleep(0.2)

        # Self-pulse should NOT be recorded in registry (skip self)
        assert net.registry.latest_pulse("health_pulse_network") is None

        await net.shutdown()

    @pytest.mark.asyncio
    async def test_publish_anomaly_on_error_status(self) -> None:
        """_publish_anomaly publishes a health.anomaly event for ERROR status."""
        bus = EventBus()
        lifecycle = MagicMock()
        lifecycle.all_modules.return_value = []

        net = HealthPulseNetwork({}, lifecycle, event_bus=bus)
        await net.initialize()

        anomaly_events: list = []
        async def catch_anomaly(payload: dict) -> None:
            anomaly_events.append(payload)

        await bus.subscribe("health.anomaly", catch_anomaly)

        error_pulse = make_pulse("failing_mod", ModuleStatus.ERROR, notes="Connection refused")
        await net._publish_anomaly("failing_mod", error_pulse)

        await asyncio.sleep(0.05)

        assert len(anomaly_events) == 1
        assert anomaly_events[0]["module_name"] == "failing_mod"
        assert anomaly_events[0]["status"] == "error"

        await net.shutdown()

    @pytest.mark.asyncio
    async def test_publish_anomaly_on_critical_status(self) -> None:
        """_publish_anomaly publishes a health.anomaly event for CRITICAL status."""
        bus = EventBus()
        lifecycle = MagicMock()
        lifecycle.all_modules.return_value = []

        net = HealthPulseNetwork({}, lifecycle, event_bus=bus)
        await net.initialize()

        anomaly_events: list = []
        async def catch_anomaly(payload: dict) -> None:
            anomaly_events.append(payload)

        await bus.subscribe("health.anomaly", catch_anomaly)

        critical_pulse = make_pulse("critical_mod", ModuleStatus.CRITICAL, notes="Out of memory")
        await net._publish_anomaly("critical_mod", critical_pulse)

        await asyncio.sleep(0.05)

        assert len(anomaly_events) == 1
        assert anomaly_events[0]["module_name"] == "critical_mod"
        assert anomaly_events[0]["status"] == "critical"

        await net.shutdown()

    @pytest.mark.asyncio
    async def test_poll_loop_no_anomaly_on_healthy_status(self) -> None:
        """Transitioning to HEALTHY does NOT publish an anomaly."""
        bus = EventBus()
        mod = make_mock_module("good_mod", ModuleStatus.HEALTHY)

        lifecycle = MagicMock()
        lifecycle.all_modules.return_value = [mod]

        config = {"pulse": {"critical_module_interval_seconds": 0.05}}
        net = HealthPulseNetwork(config, lifecycle, event_bus=bus)
        await net.initialize()
        await net.start()

        anomaly_events: list = []
        async def catch_anomaly(payload: dict) -> None:
            anomaly_events.append(payload)

        await bus.subscribe("health.anomaly", catch_anomaly)

        await asyncio.sleep(0.2)

        # No anomaly for healthy status
        assert all(e["status"] != "healthy" for e in anomaly_events)

        await net.shutdown()


# ---------------------------------------------------------------------------
# HealthPulseNetwork — unresponsive detection
# ---------------------------------------------------------------------------


class TestHealthPulseNetworkUnresponsiveDetection:
    """Tests for unresponsive module detection via check_unresponsive."""

    @pytest.mark.asyncio
    async def test_unresponsive_module_publishes_anomaly(self) -> None:
        """A module that stops pulsing is detected and published as anomaly."""
        bus = EventBus()

        # Module that will stop responding after first poll
        mod = make_mock_module("silent_mod", ModuleStatus.HEALTHY)

        lifecycle = MagicMock()
        lifecycle.all_modules.return_value = [mod]

        config = {
            "pulse": {
                "critical_module_interval_seconds": 0.05,
                "default_interval_seconds": 0.05,
                "missed_pulse_multiplier": 2,  # 2x interval = 0.1s timeout
            }
        }
        net = HealthPulseNetwork(config, lifecycle, event_bus=bus)
        await net.initialize()
        await net.start()

        anomaly_events: list = []
        async def catch_anomaly(payload: dict) -> None:
            anomaly_events.append(payload)

        await bus.subscribe("health.anomaly", catch_anomaly)

        # Let first poll happen
        await asyncio.sleep(0.15)

        # Now make the module stop responding
        mod.health_pulse.side_effect = Exception("Module went silent")

        # Wait past the missed-pulse threshold
        await asyncio.sleep(0.3)

        # Should have received an UNRESPONSIVE anomaly
        unresponsive_anomalies = [
            e for e in anomaly_events
            if e["status"] == "unresponsive"
        ]
        assert len(unresponsive_anomalies) >= 1
        assert unresponsive_anomalies[0]["module_name"] == "silent_mod"

        await net.shutdown()

    @pytest.mark.asyncio
    async def test_check_unresponsive_finds_stale_module(self) -> None:
        """HealthRegistry.check_unresponsive returns modules past threshold."""
        reg = HealthRegistry()
        reg.set_expected_interval("lazy", 0.05)  # 50ms expected interval
        old_pulse = make_pulse("lazy", timestamp=time.time() - 1.0)  # 1s old
        reg.record_pulse(old_pulse)

        # missed_multiplier=3, interval=0.05 → threshold = 0.15s
        # pulse is 1s old → well past threshold
        unresponsive = reg.check_unresponsive(3.0)

        assert "lazy" in unresponsive


# ---------------------------------------------------------------------------
# HealthPulseNetwork — snapshot and all_statuses
# ---------------------------------------------------------------------------


class TestHealthPulseNetworkQueries:
    """Tests for snapshot() and all_statuses() queries."""

    @pytest.mark.asyncio
    async def test_snapshot_delegates_to_registry(self) -> None:
        lifecycle = MagicMock()
        lifecycle.all_modules.return_value = []
        net = HealthPulseNetwork({}, lifecycle)
        await net.initialize()
        await net.start()

        snap = net.snapshot()

        assert isinstance(snap, dict)

        await net.shutdown()

    @pytest.mark.asyncio
    async def test_all_statuses_delegates_to_registry(self) -> None:
        lifecycle = MagicMock()
        lifecycle.all_modules.return_value = []
        net = HealthPulseNetwork({}, lifecycle)
        await net.initialize()
        await net.start()

        statuses = net.all_statuses()

        assert isinstance(statuses, dict)

        await net.shutdown()


# ---------------------------------------------------------------------------
# InnateResponse integration — subscribe to anomaly events
# ---------------------------------------------------------------------------


class TestInnateResponseIntegration:
    """Tests verifying InnateResponse can subscribe to anomaly events."""

    @pytest.mark.asyncio
    async def test_can_subscribe_to_anomaly_events(self) -> None:
        """Verify InnateResponse pattern: subscribe to health.anomaly."""
        bus = EventBus()

        recovery_actions: list = []

        async def innate_response_handler(payload: dict) -> None:
            recovery_actions.append(payload)

        await bus.subscribe("health.anomaly", innate_response_handler)

        # Simulate an anomaly being published
        await bus.publish("health.anomaly", {
            "module_name": "inference_gateway",
            "status": "critical",
            "notes": "Connection refused",
        })

        await asyncio.sleep(0.05)

        assert len(recovery_actions) == 1
        assert recovery_actions[0]["module_name"] == "inference_gateway"

    @pytest.mark.asyncio
    async def test_anomaly_payload_includes_all_fields(self) -> None:
        """Anomaly event payload should include module_name, status, metrics, notes, timestamp."""
        bus = EventBus()

        received: list = []

        async def handler(payload: dict) -> None:
            received.append(payload)

        await bus.subscribe("health.anomaly", handler)

        await bus.publish("health.anomaly", {
            "module_name": "memory",
            "status": "error",
            "metrics": {"cpu_percent": 95.0},
            "notes": "OOM killer invoked",
            "timestamp": 1234567890.0,
        })

        await asyncio.sleep(0.05)

        assert len(received) == 1
        p = received[0]
        assert p["module_name"] == "memory"
        assert p["status"] == "error"
        assert p["metrics"]["cpu_percent"] == 95.0
        assert p["notes"] == "OOM killer invoked"
        assert p["timestamp"] == 1234567890.0
        assert p["event_type"] == "health.anomaly"
        assert "sequence" in p

    @pytest.mark.asyncio
    async def test_wildcard_subscriber_receives_anomaly_events(self) -> None:
        """A wildcard subscriber ('*') also receives health.anomaly events."""
        bus = EventBus()

        all_events: list = []

        async def wildcard_receiver(payload: dict) -> None:
            all_events.append(payload)

        await bus.subscribe("*", wildcard_receiver)

        await bus.publish("health.anomaly", {"module_name": "thalamus", "status": "degraded"})
        await bus.publish("input.received", {"text": "hello"})

        await asyncio.sleep(0.05)

        # Wildcard should receive both events
        assert len(all_events) >= 2
        anomaly_events = [e for e in all_events if e.get("module_name") == "thalamus"]
        assert len(anomaly_events) == 1
