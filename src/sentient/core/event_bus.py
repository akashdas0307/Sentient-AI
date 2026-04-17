"""Event Bus — the nervous system of the framework.

Per DD-019, all inter-module communication flows through this central
async pub/sub system. Modules publish events without knowing who subscribes.
This is the loose-coupling backbone that makes the architecture modular.

Reference: DESIGN_DECISIONS.md DD-019, ARCHITECTURE.md §5
"""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any

logger = logging.getLogger(__name__)

EventHandler = Callable[[dict[str, Any]], Awaitable[None]]


class EventBus:
    """Central async pub/sub for all inter-module communication.

    Common event types:
      - input.received           — Thalamus accepted new input
      - input.classified          — Thalamus Layer 2 finished classification
      - input.delivered           — Queue Zone delivered to Frontal Processor
      - checkpost.tagged          — Checkpost finished entity recognition
      - tlp.enriched              — TLP context assembly complete
      - cognitive.cycle.start     — Cognitive Core began reasoning
      - cognitive.cycle.complete  — Cognitive Core finished a cycle
      - cognitive.daydream.start  — Daydream session began
      - cognitive.daydream.end    — Daydream session ended
      - cognitive.reprocess       — World Model requested revision, routing back to Cognitive Core
      - decision.proposed         — Cognitive Core proposed a decision
      - decision.reviewed         — World Model reviewed a decision
      - decision.approved         — Decision approved for execution
      - decision.vetoed           — Decision vetoed by World Model
      - action.executed           — Brainstem completed an action
      - memory.candidate          — Memory write candidate from Cognitive Core
      - memory.stored             — Memory successfully stored
      - memory.retrieved          — Memory retrieval completed
      - health.pulse              — Module heartbeat
      - health.anomaly            — Anomaly detected
      - health.escalation         — Layer 4 escalation to creator
      - sleep.stage.transition    — Sleep stage changed
      - sleep.wake                — System woke from sleep
      - attention.summary.update  — Frontal Processor published attention summary
      - eal.environment.change    — EAL detected environmental change
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)
        self._wildcard_subscribers: list[EventHandler] = []
        self._event_count = 0
        self._lock = asyncio.Lock()

    async def publish(
        self,
        event_type: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Publish an event to all subscribers.

        Fire-and-forget: returns immediately, handlers run concurrently.
        Subscriber exceptions are logged but don't propagate.
        """
        if payload is None:
            payload = {}

        # Always include event_type and a sequence number in the payload
        async with self._lock:
            self._event_count += 1
            event_payload = {
                "event_type": event_type,
                "sequence": self._event_count,
                **payload,
            }

        # Get subscribers (snapshot to avoid mutation issues)
        handlers = list(self._subscribers.get(event_type, []))
        wildcard = list(self._wildcard_subscribers)

        # Dispatch concurrently; log but don't propagate exceptions
        if handlers or wildcard:
            tasks = [
                asyncio.create_task(self._safe_dispatch(h, event_payload))
                for h in handlers + wildcard
            ]
            # Don't await — fire and forget
            for t in tasks:
                t.add_done_callback(lambda task: task.exception())

    async def _safe_dispatch(
        self,
        handler: EventHandler,
        payload: dict[str, Any],
    ) -> None:
        """Run a handler, catching and logging any exception."""
        try:
            await handler(payload)
        except Exception as exc:
            logger.exception(
                "Event handler %s failed for event %s: %s",
                handler.__name__,
                payload.get("event_type"),
                exc,
            )

    async def subscribe(
        self,
        event_type: str,
        handler: EventHandler,
    ) -> None:
        """Subscribe a handler to a specific event type.

        Use '*' to subscribe to all events (useful for logging/debugging).
        """
        async with self._lock:
            if event_type == "*":
                self._wildcard_subscribers.append(handler)
            else:
                self._subscribers[event_type].append(handler)

    async def unsubscribe(
        self,
        event_type: str,
        handler: EventHandler,
    ) -> None:
        """Remove a handler subscription."""
        async with self._lock:
            if event_type == "*":
                if handler in self._wildcard_subscribers:
                    self._wildcard_subscribers.remove(handler)
            else:
                handlers = self._subscribers.get(event_type, [])
                if handler in handlers:
                    handlers.remove(handler)

    def event_count(self) -> int:
        """Total events published (for diagnostics)."""
        return self._event_count


# Singleton instance — there is one event bus per running system
_global_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """Get the global event bus singleton."""
    global _global_bus
    if _global_bus is None:
        _global_bus = EventBus()
    return _global_bus


def reset_event_bus() -> None:
    """Reset the singleton (for testing only)."""
    global _global_bus
    _global_bus = None
