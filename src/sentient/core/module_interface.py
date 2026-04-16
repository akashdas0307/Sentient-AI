"""Module Interface — the lifecycle contract every module implements.

Per ARCHITECTURE.md §5.2, every module follows this same contract:
initialize → start → (operate) → pause → resume → shutdown.

This standardization means the LifecycleManager can manage any module
uniformly, and sleep transitions become: pause non-essential modules,
run sleep jobs, resume on wake.

Also defines the health pulse format (FR-7.1, DD-015).
"""
from __future__ import annotations

import abc
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ModuleStatus(Enum):
    """Health status reported by every module via health pulse."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"      # Working but not optimally
    ERROR = "error"            # Recoverable failure
    CRITICAL = "critical"      # Severe — needs immediate attention
    UNRESPONSIVE = "unresponsive"  # Detected externally — module not pulsing


class LifecycleState(Enum):
    """Where a module is in its lifecycle."""

    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    PAUSING = "pausing"
    PAUSED = "paused"
    RESUMING = "resuming"
    SHUTTING_DOWN = "shutting_down"
    SHUTDOWN = "shutdown"
    FAILED = "failed"


@dataclass
class HealthPulse:
    """Lightweight heartbeat signal emitted by every module.

    Per DD-015 Layer 1, no LLM involvement. Pure deterministic data.
    """

    module_name: str
    status: ModuleStatus
    timestamp: float = field(default_factory=time.time)
    metrics: dict[str, Any] = field(default_factory=dict)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "module_name": self.module_name,
            "status": self.status.value,
            "timestamp": self.timestamp,
            "metrics": self.metrics,
            "notes": self.notes,
        }


class ModuleInterface(abc.ABC):
    """Contract every module in the framework must implement.

    Provides:
      - Standard lifecycle (initialize / start / pause / resume / shutdown)
      - Health pulse emission
      - Lifecycle state tracking
      - Restart capability (used by Innate Response)
    """

    def __init__(self, name: str, config: dict[str, Any] | None = None) -> None:
        self.name = name
        self.config = config or {}
        self.state = LifecycleState.UNINITIALIZED
        self._last_health_status = ModuleStatus.HEALTHY
        self._error_count = 0
        self._last_error: str | None = None

    # === Lifecycle methods (must be implemented by subclasses) ===

    @abc.abstractmethod
    async def initialize(self) -> None:
        """Setup resources, load config, prepare for operation.

        Called once before start(). May raise to indicate init failure.
        """
        ...

    @abc.abstractmethod
    async def start(self) -> None:
        """Begin active operation.

        After this returns, the module should be processing events,
        listening on subscriptions, etc.
        """
        ...

    async def pause(self) -> None:
        """Suspend operation (for sleep transitions).

        Default implementation is no-op. Override if module needs to
        save state or stop background tasks during sleep.
        """
        self.state = LifecycleState.PAUSED

    async def resume(self) -> None:
        """Resume from pause.

        Default implementation is no-op. Override to restore state
        and resume background tasks.
        """
        self.state = LifecycleState.RUNNING

    @abc.abstractmethod
    async def shutdown(self) -> None:
        """Clean shutdown — close connections, save state, release resources.

        Should be idempotent and complete in bounded time.
        """
        ...

    # === Health reporting ===

    def health_pulse(self) -> HealthPulse:
        """Emit current health status.

        Subclasses should override to provide module-specific metrics
        (per ARCHITECTURE.md §3.1 module-specific metrics table).
        """
        return HealthPulse(
            module_name=self.name,
            status=self._last_health_status,
            metrics={
                "lifecycle_state": self.state.value,
                "error_count": self._error_count,
                "last_error": self._last_error,
            },
        )

    def set_status(self, status: ModuleStatus, note: str = "") -> None:
        """Update health status (called internally by the module)."""
        self._last_health_status = status
        if status in (ModuleStatus.ERROR, ModuleStatus.CRITICAL):
            self._error_count += 1
            self._last_error = note

    def reset_error_count(self) -> None:
        """Called by Innate Response after successful recovery."""
        self._error_count = 0
        self._last_error = None

    # === Restart support ===

    async def restart(self) -> None:
        """Restart this module (used by Layer 2 Innate Response).

        Default: shutdown → initialize → start. Override for custom logic.
        """
        try:
            await self.shutdown()
        except Exception:
            pass  # Best effort
        await self.initialize()
        await self.start()
        self.reset_error_count()

    # === Metadata ===

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} name={self.name} "
            f"state={self.state.value} status={self._last_health_status.value}>"
        )
