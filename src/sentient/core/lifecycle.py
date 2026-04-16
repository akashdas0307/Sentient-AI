"""Lifecycle Manager — orchestrates module startup, sleep transitions, and shutdown.

Per ARCHITECTURE.md §6.3 startup sequence, modules initialize in a specific
order so that dependencies are ready when needed (e.g., Inference Gateway
before any module that needs LLM calls).
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable
from typing import Any

from sentient.core.event_bus import EventBus, get_event_bus
from sentient.core.module_interface import LifecycleState, ModuleInterface, ModuleStatus

logger = logging.getLogger(__name__)


class LifecycleManager:
    """Manages the lifecycle of all framework modules.

    Responsibilities:
      - Start modules in dependency order
      - Coordinate sleep stage transitions (pause/resume)
      - Clean shutdown on system stop
      - Restart failed modules (delegated from Innate Response)
    """

    def __init__(self, event_bus: EventBus | None = None) -> None:
        self.event_bus = event_bus or get_event_bus()
        self._modules: dict[str, ModuleInterface] = {}
        self._startup_order: list[str] = []
        self._essential_modules: set[str] = set()  # Don't pause during sleep
        self._running = False

    # === Module registration ===

    def register(
        self,
        module: ModuleInterface,
        essential: bool = False,
    ) -> None:
        """Register a module with the lifecycle manager.

        Modules are started in registration order. Essential modules are
        not paused during sleep stages.
        """
        if module.name in self._modules:
            raise ValueError(f"Module {module.name} already registered")
        self._modules[module.name] = module
        self._startup_order.append(module.name)
        if essential:
            self._essential_modules.add(module.name)
        logger.debug("Registered module: %s (essential=%s)", module.name, essential)

    def get_module(self, name: str) -> ModuleInterface | None:
        """Look up a module by name."""
        return self._modules.get(name)

    def all_modules(self) -> Iterable[ModuleInterface]:
        """Iterate over all registered modules."""
        return self._modules.values()

    # === Startup ===

    async def startup(self) -> None:
        """Initialize and start all modules in registration order.

        Per ARCHITECTURE.md §6.3, the canonical order is:
          Event Bus → Inference Gateway → Memory → Health → Persona →
          Thalamus → Prajñā → Brainstem → Sleep → API
        """
        logger.info("Lifecycle: starting %d modules", len(self._modules))
        self._running = True

        for name in self._startup_order:
            module = self._modules[name]
            try:
                await self._initialize_with_retry(module)
                await self._start_with_retry(module)
                logger.info("Lifecycle: started %s", name)
            except Exception as exc:
                logger.exception(
                    "Lifecycle: module %s failed during startup: %s",
                    name,
                    exc,
                )
                module.state = LifecycleState.FAILED
                module.set_status(ModuleStatus.CRITICAL, str(exc))
                # Continue with remaining modules — degraded operation is
                # better than no operation. Health system will alert.

        await self.event_bus.publish(
            "lifecycle.startup.complete",
            {
                "module_count": len(self._modules),
                "failed_count": sum(
                    1 for m in self._modules.values()
                    if m.state == LifecycleState.FAILED
                ),
            },
        )

    async def _initialize_with_retry(
        self,
        module: ModuleInterface,
        max_attempts: int = 3,
    ) -> None:
        """Try to initialize with retries on failure."""
        last_exc: Exception | None = None
        for attempt in range(max_attempts):
            try:
                module.state = LifecycleState.INITIALIZING
                await module.initialize()
                module.state = LifecycleState.READY
                return
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "Init attempt %d/%d failed for %s: %s",
                    attempt + 1, max_attempts, module.name, exc,
                )
                if attempt < max_attempts - 1:
                    await asyncio.sleep(2 ** attempt)
        # All retries failed
        raise last_exc or RuntimeError(f"Init failed for {module.name}")

    async def _start_with_retry(
        self,
        module: ModuleInterface,
        max_attempts: int = 3,
    ) -> None:
        """Try to start with retries."""
        last_exc: Exception | None = None
        for attempt in range(max_attempts):
            try:
                await module.start()
                module.state = LifecycleState.RUNNING
                return
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "Start attempt %d/%d failed for %s: %s",
                    attempt + 1, max_attempts, module.name, exc,
                )
                if attempt < max_attempts - 1:
                    await asyncio.sleep(2 ** attempt)
        raise last_exc or RuntimeError(f"Start failed for {module.name}")

    # === Sleep transitions ===

    async def pause_for_sleep(self) -> None:
        """Pause non-essential modules for sleep transition.

        Essential modules (Health, Memory, Sleep itself, Inference Gateway,
        Thalamus sleep-mode monitor) keep running. Per DD-014, this happens
        during Stage 1 (Settling).
        """
        logger.info("Lifecycle: pausing modules for sleep")
        for name, module in self._modules.items():
            if name in self._essential_modules:
                continue
            if module.state != LifecycleState.RUNNING:
                continue
            try:
                module.state = LifecycleState.PAUSING
                await module.pause()
            except Exception as exc:
                logger.exception("Failed to pause %s: %s", name, exc)

    async def resume_from_sleep(self) -> None:
        """Resume paused modules on wake."""
        logger.info("Lifecycle: resuming modules from sleep")
        for name, module in self._modules.items():
            if name in self._essential_modules:
                continue
            if module.state != LifecycleState.PAUSED:
                continue
            try:
                module.state = LifecycleState.RESUMING
                await module.resume()
            except Exception as exc:
                logger.exception("Failed to resume %s: %s", name, exc)

    # === Restart (Innate Response Layer 2) ===

    async def restart_module(self, name: str) -> bool:
        """Restart a specific module. Returns True on success."""
        module = self._modules.get(name)
        if module is None:
            logger.warning("Cannot restart unknown module: %s", name)
            return False
        try:
            logger.info("Lifecycle: restarting %s", name)
            await module.restart()
            await self.event_bus.publish(
                "lifecycle.module.restarted",
                {"module_name": name},
            )
            return True
        except Exception as exc:
            logger.exception("Restart failed for %s: %s", name, exc)
            await self.event_bus.publish(
                "lifecycle.module.restart_failed",
                {"module_name": name, "error": str(exc)},
            )
            return False

    # === Shutdown ===

    async def shutdown(self) -> None:
        """Shut down all modules in reverse startup order."""
        logger.info("Lifecycle: shutting down")
        self._running = False

        for name in reversed(self._startup_order):
            module = self._modules[name]
            try:
                module.state = LifecycleState.SHUTTING_DOWN
                await module.shutdown()
                module.state = LifecycleState.SHUTDOWN
            except Exception as exc:
                logger.exception("Shutdown error for %s: %s", name, exc)

        await self.event_bus.publish("lifecycle.shutdown.complete", {})

    # === Status queries ===

    def is_running(self) -> bool:
        """True if the framework is in active operation."""
        return self._running

    def status_summary(self) -> dict[str, Any]:
        """Snapshot of all module statuses (for dashboard)."""
        return {
            "running": self._running,
            "modules": {
                name: {
                    "state": module.state.value,
                    "status": module.health_pulse().status.value,
                }
                for name, module in self._modules.items()
            },
        }
