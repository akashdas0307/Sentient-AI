"""Health Registry — Layer 1 in-memory data store.

Per ARCHITECTURE.md §3.6 and DD-015, this is pure code, no LLM.
Holds the last N pulses from each module. If a module stops pulsing,
that absence IS the signal (detected by missed pulses).
"""
from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Any

from sentient.core.module_interface import HealthPulse, ModuleStatus


class HealthRegistry:
    """In-memory registry of recent health pulses."""

    def __init__(self, retention_per_module: int = 100) -> None:
        self._pulses: dict[str, deque[HealthPulse]] = defaultdict(
            lambda: deque(maxlen=retention_per_module)
        )
        self._expected_intervals: dict[str, float] = {}
        self._unresponsive_modules: set[str] = set()

    def record_pulse(self, pulse: HealthPulse) -> None:
        """Store a pulse. Automatically removes UNRESPONSIVE flag."""
        self._pulses[pulse.module_name].append(pulse)
        self._unresponsive_modules.discard(pulse.module_name)

    def set_expected_interval(self, module_name: str, seconds: float) -> None:
        """Configure expected pulse interval for a module."""
        self._expected_intervals[module_name] = seconds

    def latest_pulse(self, module_name: str) -> HealthPulse | None:
        """Get the most recent pulse for a module."""
        pulses = self._pulses.get(module_name)
        return pulses[-1] if pulses else None

    def recent_pulses(self, module_name: str, count: int = 10) -> list[HealthPulse]:
        """Get the most recent N pulses."""
        pulses = list(self._pulses.get(module_name, []))
        return pulses[-count:]

    def check_unresponsive(self, missed_multiplier: float = 3.0) -> list[str]:
        """Detect modules that have stopped pulsing.

        A module is UNRESPONSIVE if its last pulse is older than
        expected_interval * missed_multiplier.
        """
        now = time.time()
        unresponsive = []
        for module_name, interval in self._expected_intervals.items():
            latest = self.latest_pulse(module_name)
            if latest is None:
                continue
            age = now - latest.timestamp
            if age > interval * missed_multiplier:
                unresponsive.append(module_name)
                self._unresponsive_modules.add(module_name)
        return unresponsive

    def status_of(self, module_name: str) -> ModuleStatus:
        """Current status (considering missed pulses)."""
        if module_name in self._unresponsive_modules:
            return ModuleStatus.UNRESPONSIVE
        latest = self.latest_pulse(module_name)
        return latest.status if latest else ModuleStatus.UNRESPONSIVE

    def snapshot(self) -> dict[str, Any]:
        """Full snapshot for dashboard display."""
        return {
            module_name: {
                "latest": pulses[-1].to_dict() if pulses else None,
                "pulse_count": len(pulses),
                "status": self.status_of(module_name).value,
            }
            for module_name, pulses in self._pulses.items()
        }

    def all_statuses(self) -> dict[str, str]:
        """Quick status summary for all modules."""
        return {
            name: self.status_of(name).value
            for name in self._pulses.keys()
        }
