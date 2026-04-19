"""Thalamus Gateway — the input gateway module.

Per ARCHITECTURE.md §3.1:
  - Layer 1: Heuristic engine (fast, no LLM)
  - Layer 2: Local LLM classifier (nuanced classification on batch)
  - Adaptive batching window (5-60s)
  - Plugin registry (passive + active + self-created)
  - Attention summary subscriber for relevance gating
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from typing import Any

from sentient.core.envelope import Envelope, Priority
from sentient.core.event_bus import EventBus, get_event_bus
from sentient.core.module_interface import HealthPulse, ModuleInterface, ModuleStatus
from sentient.thalamus.heuristic_engine import HeuristicEngine
from sentient.thalamus.plugins.base import InputPlugin

logger = logging.getLogger(__name__)


class Thalamus(ModuleInterface):
    """Input Gateway — collects, normalizes, classifies, and forwards inputs."""

    def __init__(
        self,
        config: dict[str, Any],
        event_bus: EventBus | None = None,
    ) -> None:
        super().__init__("thalamus", config)
        self.event_bus = event_bus or get_event_bus()

        # Configuration
        batching_cfg = config.get("batching", {})
        self.min_window = batching_cfg.get("min_window_seconds", 5)
        self.max_window = batching_cfg.get("max_window_seconds", 60)
        self.current_window = batching_cfg.get("default_window_seconds", 30)

        # Layer 1
        self.heuristic = HeuristicEngine(config.get("heuristic_engine", {}))

        # Plugin registry
        self._plugins: dict[str, InputPlugin] = {}

        # Batching state
        self._current_batch: list[Envelope] = []
        self._current_batch_outbox: list[Envelope] = []  # snapshot for emission
        self._batch_started_at: float | None = None
        self._batch_lock = asyncio.Lock()
        self._batch_task: asyncio.Task | None = None

        # Recent envelope window for dedup (last 100)
        self._recent_envelopes: deque[Envelope] = deque(maxlen=100)

        # Attention summary from Frontal Processor
        self._attention_summary: dict[str, Any] = {}

        # Stats
        self._envelopes_received = 0
        self._envelopes_forwarded = 0
        self._batches_emitted = 0

    # === Lifecycle ===

    async def initialize(self) -> None:
        # Subscribe to attention summary updates
        await self.event_bus.subscribe(
            "attention.summary.update",
            self._handle_attention_summary,
        )
        logger.info("Thalamus initialized")

    async def start(self) -> None:
        # Start the batching window task
        self._batch_task = asyncio.create_task(self._batching_loop())
        self.set_status(ModuleStatus.HEALTHY)
        logger.info("Thalamus started (window=%ds)", self.current_window)

    async def shutdown(self) -> None:
        if self._batch_task:
            self._batch_task.cancel()
            try:
                await self._batch_task
            except asyncio.CancelledError:
                pass
        # Shut down all plugins
        for plugin in self._plugins.values():
            try:
                await plugin.shutdown()
            except Exception as exc:
                logger.warning("Plugin %s shutdown error: %s", plugin.name, exc)

    # === Plugin management ===

    async def register_plugin(self, plugin: InputPlugin) -> None:
        """Register an input plugin and wire it up to forward to Thalamus."""
        if plugin.name in self._plugins:
            raise ValueError(f"Plugin {plugin.name} already registered")
        plugin.set_emit_callback(self._receive_from_plugin)
        await plugin.initialize()
        await plugin.start()
        self._plugins[plugin.name] = plugin
        logger.info("Thalamus registered plugin: %s", plugin.name)

    def get_plugin(self, name: str) -> InputPlugin | None:
        return self._plugins.get(name)

    def list_plugins(self) -> list[str]:
        return list(self._plugins.keys())

    # === Receiving from plugins ===

    async def _receive_from_plugin(self, envelope: Envelope) -> None:
        """Called by plugins when they have a new envelope."""
        self._envelopes_received += 1
        envelope.received_at = time.time()

        # Dedup check
        if self.heuristic.is_likely_duplicate(envelope, list(self._recent_envelopes)):
            envelope.processing_notes.append("dedup: skipped as likely duplicate")
            logger.debug("Thalamus: dropped duplicate envelope %s", envelope.envelope_id)
            return

        self._recent_envelopes.append(envelope)

        # Layer 1: heuristic priority classification
        priority = self.heuristic.classify(envelope)
        envelope.priority = priority

        await self.event_bus.publish(
            "input.received",
            {
                "envelope_id": envelope.envelope_id,
                "source_type": envelope.source_type.value,
                "priority": priority.value,
                "envelope": envelope,
            },
        )

        # Tier 1: bypass batching, forward immediately
        if priority == Priority.TIER_1_IMMEDIATE:
            await self._forward_immediately(envelope)
            return

        # Tier 2/3: add to batch
        async with self._batch_lock:
            self._current_batch.append(envelope)
            if self._batch_started_at is None:
                self._batch_started_at = time.time()
            # Tier 2 shortens the window
            if priority == Priority.TIER_2_ELEVATED:
                # Force batch to emit after min_window
                await self._maybe_emit_batch(force_after=self.min_window)

    async def _forward_immediately(self, envelope: Envelope) -> None:
        """Forward Tier 1 envelope without batching."""
        # Flush any current batch first to preserve ordering
        async with self._batch_lock:
            if self._current_batch:
                await self._emit_current_batch()
        # Then forward this envelope alone
        await self._forward_envelope(envelope)
        self._envelopes_forwarded += 1

    # === Batching ===

    async def _batching_loop(self) -> None:
        """Background task that emits batches at the current window interval."""
        while True:
            try:
                await asyncio.sleep(1.0)  # Check every second
                await self._maybe_emit_batch()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.exception("Batching loop error: %s", exc)

    async def _maybe_emit_batch(self, force_after: float | None = None) -> None:
        """Check if it's time to emit the current batch."""
        # Snapshot the batch under lock, then release before emitting to
        # avoid holding the lock while downstream handlers call back in.
        async with self._batch_lock:
            if not self._current_batch or self._batch_started_at is None:
                return
            elapsed = time.time() - self._batch_started_at
            window = force_after if force_after is not None else self.current_window
            logger.debug(
                "_maybe_emit_batch: batch=%d elapsed=%.3f window=%.3f",
                len(self._current_batch), elapsed, window,
            )
            if elapsed < window:
                return
            # Snapshot into outbox — done under lock
            self._current_batch_outbox = list(self._current_batch)
            self._current_batch = []
            self._batch_started_at = None

        # Emit without lock held
        await self._emit_current_batch()

    async def _emit_current_batch(self) -> None:
        """Emit the current batch.

        The _batch_lock is NOT held during this method (the snapshot was taken
        before acquiring the lock in _maybe_emit_batch). This prevents deadlock
        when downstream handlers call back into thalamus while the lock is held.
        """
        batch = self._current_batch_outbox
        self._current_batch_outbox = []
        self._batch_started_at = None
        self._batches_emitted += 1

        # Forward each envelope (no lock held — event bus is async-safe)
        # In a future enhancement, Layer 2 LLM classification would happen here
        # for nuanced relevance/priority refinement on the whole batch.
        for envelope in batch:
            await self._forward_envelope(envelope)
            self._envelopes_forwarded += 1

    async def _forward_envelope(self, envelope: Envelope) -> None:
        """Send envelope to Checkpost (next stage of Prajñā pipeline)."""
        await self.event_bus.publish(
            "input.classified",
            {"envelope": envelope},
        )

    # === Attention summary handling ===

    async def _handle_attention_summary(self, payload: dict[str, Any]) -> None:
        """Receive attention summary broadcast from Frontal Processor."""
        self._attention_summary = payload.get("summary", {})

        # Adapt batching window based on Frontal Processor state
        focus = self._attention_summary.get("current_focus", "idle")
        if focus == "active_conversation":
            self.current_window = self.min_window
        elif focus == "idle":
            self.current_window = self.max_window
        else:
            self.current_window = self.config.get("batching", {}).get(
                "default_window_seconds", 30
            )

    # === Health ===

    def health_pulse(self) -> HealthPulse:
        return HealthPulse(
            module_name=self.name,
            status=self._last_health_status,
            metrics={
                "envelopes_received": self._envelopes_received,
                "envelopes_forwarded": self._envelopes_forwarded,
                "batches_emitted": self._batches_emitted,
                "current_window_seconds": self.current_window,
                "active_plugins": list(self._plugins.keys()),
                "current_batch_size": len(self._current_batch),
            },
        )
