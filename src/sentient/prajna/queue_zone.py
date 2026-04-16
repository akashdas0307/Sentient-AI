"""Queue Zone — attentional gatekeeper.

Per ARCHITECTURE.md §3.3.2:
  - Idle mode: 30s accumulation window with Tier 1 collapse
  - Active mode: interrupt / inject / hold decisions
  - Anti-starvation: priority aging + batch summarization
  - Receives from: Checkpost (external), plus internal sources
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from sentient.core.envelope import Envelope, Priority
from sentient.core.event_bus import EventBus, get_event_bus
from sentient.core.module_interface import HealthPulse, ModuleInterface, ModuleStatus

logger = logging.getLogger(__name__)


@dataclass
class _QueueItem:
    """Wrapped envelope with queue metadata."""
    envelope: Envelope
    queued_at: float = field(default_factory=time.time)
    delivery_attempts: int = 0

    def effective_priority(self, age_to_t2: float, age_to_t1: float) -> Priority:
        """Compute priority with aging applied."""
        age = time.time() - self.queued_at
        original = self.envelope.priority
        if original == Priority.TIER_3_NORMAL and age >= age_to_t2:
            return Priority.TIER_2_ELEVATED
        if original == Priority.TIER_2_ELEVATED and age >= age_to_t1:
            return Priority.TIER_1_IMMEDIATE
        return original


class QueueZone(ModuleInterface):
    """Attentional gatekeeper for the Frontal Processor."""

    def __init__(
        self,
        config: dict[str, Any],
        event_bus: EventBus | None = None,
    ) -> None:
        super().__init__("queue_zone", config)
        self.event_bus = event_bus or get_event_bus()

        self.starvation_t2 = config.get("starvation", {}).get(
            "age_to_tier2_seconds", 1800
        )
        self.starvation_t1 = config.get("starvation", {}).get(
            "age_to_tier1_seconds", 21600
        )
        self.batch_summary_threshold = config.get("batch_summarization", {}).get(
            "threshold_count", 20
        )

        self._hold_queue: deque[_QueueItem] = deque()
        self._sidebar: deque[Envelope] = deque(maxlen=20)
        self._frontal_busy = False    # True if Frontal Processor is actively reasoning

        self._delivered_count = 0
        self._aged_count = 0

    # === Lifecycle ===

    async def initialize(self) -> None:
        # Subscribe to all internal sources that feed the Queue Zone
        await self.event_bus.subscribe("checkpost.tagged", self._receive_envelope_event)
        await self.event_bus.subscribe(
            "internal.queue_item",
            self._receive_internal_event,
        )
        # Track Frontal Processor busy state
        await self.event_bus.subscribe("cognitive.cycle.start", self._on_cycle_start)
        await self.event_bus.subscribe("cognitive.cycle.complete", self._on_cycle_complete)
        logger.info("Queue Zone initialized")

    async def start(self) -> None:
        # Background task for delivery + aging
        self._delivery_task = asyncio.create_task(self._delivery_loop())
        self.set_status(ModuleStatus.HEALTHY)

    async def shutdown(self) -> None:
        if hasattr(self, "_delivery_task"):
            self._delivery_task.cancel()

    # === Receiving ===

    async def _receive_envelope_event(self, payload: dict[str, Any]) -> None:
        envelope: Envelope = payload["envelope"]
        await self.enqueue(envelope)

    async def _receive_internal_event(self, payload: dict[str, Any]) -> None:
        """Internal sources (Limbic, Health, Dream, World Model, etc.)
        publish to 'internal.queue_item' with an envelope payload.
        """
        envelope: Envelope = payload["envelope"]
        await self.enqueue(envelope)

    async def enqueue(self, envelope: Envelope) -> None:
        """Add an envelope to the queue with appropriate routing."""
        item = _QueueItem(envelope=envelope)

        # Active mode decision
        if self._frontal_busy:
            decision = self._active_mode_decision(envelope)
            if decision == "interrupt":
                # Tier 1 — break in, deliver now
                await self._deliver(item)
                return
            elif decision == "inject":
                # Add to sidebar for Frontal Processor to glance at
                self._sidebar.append(envelope)
                await self.event_bus.publish(
                    "queue.sidebar.updated",
                    {"sidebar_size": len(self._sidebar)},
                )
                return
            # 'hold' falls through to queue
        else:
            # Idle mode — Tier 1 still gets immediate
            if envelope.priority == Priority.TIER_1_IMMEDIATE:
                await self._deliver(item)
                return

        # Queue it
        self._hold_queue.append(item)

    def _active_mode_decision(self, envelope: Envelope) -> str:
        """Decide interrupt/inject/hold for an envelope arriving during active reasoning.

        Per ARCHITECTURE.md §3.3.2:
          - Tier 1 → interrupt
          - Topical relevance OR from creator OR time-sensitive → inject
          - Otherwise → hold
        """
        if envelope.priority == Priority.TIER_1_IMMEDIATE:
            return "interrupt"
        if envelope.is_from_creator():
            return "inject"
        if envelope.expires_at is not None:
            return "inject"
        # Topical relevance check would compare envelope tags with current focus.
        # For MVS, default to hold for non-creator non-urgent inputs.
        return "hold"

    # === Delivery ===

    async def _delivery_loop(self) -> None:
        """Continuously check for items to deliver and age priorities."""
        while True:
            try:
                await asyncio.sleep(2.0)
                await self._deliver_pending()
                if len(self._hold_queue) >= self.batch_summary_threshold:
                    await self._summarize_batch()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.exception("Queue Zone delivery loop error: %s", exc)

    async def _deliver_pending(self) -> None:
        """Deliver eligible items, applying priority aging."""
        if self._frontal_busy:
            # In active mode, only Tier 1 delivers (already handled in enqueue)
            return

        # In idle mode, deliver in priority order with aging applied
        if not self._hold_queue:
            return

        # Find highest-effective-priority item
        sorted_items = sorted(
            self._hold_queue,
            key=lambda item: item.effective_priority(
                self.starvation_t2, self.starvation_t1
            ).value,
        )

        # Deliver one item per cycle
        item = sorted_items[0]
        self._hold_queue.remove(item)
        await self._deliver(item)

    async def _deliver(self, item: _QueueItem) -> None:
        """Send envelope to TLP."""
        item.envelope.delivered_at = time.time()
        self._delivered_count += 1
        await self.event_bus.publish(
            "input.delivered",
            {
                "envelope": item.envelope,
                "sidebar": list(self._sidebar),  # Snapshot for context
            },
        )

    async def _summarize_batch(self) -> None:
        """When queue exceeds threshold, generate digest.

        STUB: In full implementation, use local LLM to summarize the queued
        items into a single digest envelope and replace the queue with that.
        """
        logger.info(
            "Queue Zone: batch summarization triggered (depth=%d)",
            len(self._hold_queue),
        )
        # MVS: just log; Phase 2+ implements actual summarization

    # === Cycle tracking ===

    async def _on_cycle_start(self, payload: dict[str, Any]) -> None:
        self._frontal_busy = True

    async def _on_cycle_complete(self, payload: dict[str, Any]) -> None:
        self._frontal_busy = False

    # === Health ===

    def health_pulse(self) -> HealthPulse:
        oldest_age = (
            time.time() - self._hold_queue[0].queued_at
            if self._hold_queue else 0
        )
        return HealthPulse(
            module_name=self.name,
            status=self._last_health_status,
            metrics={
                "queue_depth": len(self._hold_queue),
                "sidebar_size": len(self._sidebar),
                "oldest_item_age_seconds": round(oldest_age, 1),
                "delivered_count": self._delivered_count,
                "frontal_busy": self._frontal_busy,
            },
        )
