"""Health Pulse Network — Layer 1 continuous monitoring.

Per DD-015, this uses NO LLM. Pure deterministic code that:
  - Polls every registered module for its health pulse on schedule
  - Stores pulses in the Health Registry
  - Detects missed pulses (UNRESPONSIVE modules)
  - Publishes anomaly events for Layer 2 (Innate Response) to handle
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from sentient.core.event_bus import EventBus, get_event_bus
from sentient.core.module_interface import HealthPulse, ModuleInterface, ModuleStatus
from sentient.health.registry import HealthRegistry

logger = logging.getLogger(__name__)


class HealthPulseNetwork(ModuleInterface):
    """Continuously polls modules and publishes anomalies."""

    def __init__(
        self,
        config: dict[str, Any],
        lifecycle_manager: Any,   # LifecycleManager
        event_bus: EventBus | None = None,
    ) -> None:
        super().__init__("health_pulse_network", config)
        self.event_bus = event_bus or get_event_bus()
        self.lifecycle = lifecycle_manager

        pulse_cfg = config.get("pulse", {})
        self.default_interval = pulse_cfg.get("default_interval_seconds", 30)
        self.critical_interval = pulse_cfg.get("critical_module_interval_seconds", 5)
        self.missed_multiplier = pulse_cfg.get("missed_pulse_multiplier", 3)

        # Which modules count as critical (polled more frequently)
        self.critical_modules = {
            "inference_gateway",
            "memory",
            "thalamus",
        }

        self.registry = HealthRegistry()
        self._poll_task: asyncio.Task | None = None
        self._last_statuses: dict[str, ModuleStatus] = {}

    # === Lifecycle ===

    async def initialize(self) -> None:
        # Register expected intervals for all modules
        for module in self.lifecycle.all_modules():
            interval = (
                self.critical_interval
                if module.name in self.critical_modules
                else self.default_interval
            )
            self.registry.set_expected_interval(module.name, interval)

    async def start(self) -> None:
        self._poll_task = asyncio.create_task(self._poll_loop())
        self.set_status(ModuleStatus.HEALTHY)

    async def shutdown(self) -> None:
        if self._poll_task:
            self._poll_task.cancel()

    # === Polling loop ===

    async def _poll_loop(self) -> None:
        """Continuously poll all modules and check for anomalies."""
        tick = 0
        while True:
            try:
                await asyncio.sleep(self.critical_interval)
                tick += 1

                # Poll critical modules every tick
                # Poll regular modules every (default/critical) ticks
                regular_poll_every = max(
                    1, self.default_interval // self.critical_interval
                )

                for module in self.lifecycle.all_modules():
                    if module.name == self.name:
                        continue   # Don't poll ourselves
                    is_critical = module.name in self.critical_modules
                    if not is_critical and tick % regular_poll_every != 0:
                        continue

                    pulse = module.health_pulse()
                    self.registry.record_pulse(pulse)

                    # Detect status changes → anomalies
                    previous = self._last_statuses.get(module.name)
                    if previous != pulse.status:
                        if pulse.status in (
                            ModuleStatus.ERROR,
                            ModuleStatus.CRITICAL,
                        ):
                            await self._publish_anomaly(module.name, pulse)
                        self._last_statuses[module.name] = pulse.status

                # Check for unresponsive modules (missed pulses)
                unresponsive = self.registry.check_unresponsive(
                    self.missed_multiplier
                )
                for module_name in unresponsive:
                    if self._last_statuses.get(module_name) != ModuleStatus.UNRESPONSIVE:
                        await self._publish_anomaly(
                            module_name,
                            HealthPulse(
                                module_name=module_name,
                                status=ModuleStatus.UNRESPONSIVE,
                                notes="No pulse received within expected window",
                            ),
                        )
                        self._last_statuses[module_name] = ModuleStatus.UNRESPONSIVE

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.exception("Health pulse poll loop error: %s", exc)

    async def _publish_anomaly(self, module_name: str, pulse: HealthPulse) -> None:
        """Publish an anomaly event for Innate Response to handle."""
        logger.warning(
            "Health anomaly detected: module=%s status=%s notes=%s",
            module_name, pulse.status.value, pulse.notes,
        )
        await self.event_bus.publish(
            "health.anomaly",
            {
                "module_name": module_name,
                "status": pulse.status.value,
                "metrics": pulse.metrics,
                "notes": pulse.notes,
                "timestamp": pulse.timestamp,
            },
        )

    # === Queries (for dashboard) ===

    def snapshot(self) -> dict[str, Any]:
        return self.registry.snapshot()

    def all_statuses(self) -> dict[str, str]:
        return self.registry.all_statuses()

    def health_pulse(self) -> HealthPulse:
        return HealthPulse(
            module_name=self.name,
            status=self._last_health_status,
            metrics={
                "modules_monitored": len(self.registry._expected_intervals),
                "current_anomalies": sum(
                    1 for status in self._last_statuses.values()
                    if status in (
                        ModuleStatus.ERROR,
                        ModuleStatus.CRITICAL,
                        ModuleStatus.UNRESPONSIVE,
                    )
                ),
            },
        )
