"""Temporal-Limbic-Processor (TLP) — merged module.

Per ARCHITECTURE.md §3.3.3 and DD-004, this combines what was originally
two stages (Temporal-Occipital and Limbic) into one. Three operations
in a single pass:
  1. Deep memory retrieval
  2. Context assembly with provenance
  3. Significance weighting (emotional/motivational/learning/urgency)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from sentient.core.envelope import Envelope
from sentient.core.event_bus import EventBus, get_event_bus
from sentient.core.inference_gateway import InferenceGateway
from sentient.core.module_interface import HealthPulse, ModuleInterface, ModuleStatus

logger = logging.getLogger(__name__)


@dataclass
class EnrichedContext:
    """The output of TLP — what gets handed to the Frontal Processor.

    Per ARCHITECTURE.md §3.3.3 output specification.
    """

    envelope: Envelope                         # The triggering envelope
    situation_summary: str = ""                # Synthesized narrative
    related_memories: list[dict[str, Any]] = field(default_factory=list)
    significance: dict[str, float] = field(default_factory=dict)
    temporal_timeline: list[dict[str, Any]] = field(default_factory=list)
    sidebar: list[Envelope] = field(default_factory=list)
    suggested_approach: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "envelope": self.envelope.to_dict(),
            "situation_summary": self.situation_summary,
            "related_memories_count": len(self.related_memories),
            "significance": self.significance,
            "temporal_timeline_count": len(self.temporal_timeline),
            "sidebar_count": len(self.sidebar),
            "suggested_approach": self.suggested_approach,
        }


class TemporalLimbicProcessor(ModuleInterface):
    """Memory retrieval + context assembly + significance weighting in one pass."""

    def __init__(
        self,
        config: dict[str, Any],
        inference_gateway: InferenceGateway,
        memory: Any | None = None,   # MemoryArchitecture
        event_bus: EventBus | None = None,
    ) -> None:
        super().__init__("tlp", config)
        self.event_bus = event_bus or get_event_bus()
        self.gateway = inference_gateway
        self.memory = memory

        self.default_max_results = config.get("retrieval", {}).get(
            "default_max_results", 15
        )
        self.deep_max_results = config.get("retrieval", {}).get(
            "deep_max_results", 30
        )

        self._processed_count = 0

    async def initialize(self) -> None:
        await self.event_bus.subscribe("input.delivered", self._handle_delivered)

    async def start(self) -> None:
        self.set_status(ModuleStatus.HEALTHY)

    async def shutdown(self) -> None:
        pass

    async def _handle_delivered(self, payload: dict[str, Any]) -> None:
        raw_envelope = payload["envelope"]
        envelope: Envelope = raw_envelope if isinstance(raw_envelope, Envelope) else Envelope.from_dict(raw_envelope)
        raw_sidebar = payload.get("sidebar", [])
        sidebar: list[Envelope] = [item if isinstance(item, Envelope) else Envelope.from_dict(item) for item in raw_sidebar]
        try:
            enriched = await self._enrich(envelope, sidebar)
            self._processed_count += 1
            await self.event_bus.publish(
                "tlp.enriched",
                {"context": enriched},
            )
        except Exception as exc:
            logger.exception("TLP enrichment error: %s", exc)
            self.set_status(ModuleStatus.ERROR, str(exc))

    async def _enrich(
        self,
        envelope: Envelope,
        sidebar: list[Envelope],
    ) -> EnrichedContext:
        """Three-operation enrichment in one pass."""
        context = EnrichedContext(envelope=envelope, sidebar=sidebar)

        # Operation 1: Deep memory retrieval
        if self.memory is not None:
            depth = self._determine_retrieval_depth(envelope)
            memories = await self.memory.retrieve(
                query=envelope.processed_content,
                tags=envelope.entity_tags + envelope.topic_tags,
                limit=depth,
            )
            context.related_memories = memories
            envelope.related_memory_ids = [m.get("id") for m in memories if m.get("id")]

        # Operation 2: Context assembly
        context.situation_summary = self._build_summary(envelope, context.related_memories)
        context.temporal_timeline = self._build_timeline(envelope, context.related_memories)

        # Operation 3: Significance weighting
        context.significance = self._weight_significance(envelope, context.related_memories)
        envelope.significance = context.significance

        envelope.tlp_enriched = True
        return context

    def _determine_retrieval_depth(self, envelope: Envelope) -> int:
        """Simple heuristic for how many memories to retrieve."""
        # Long, complex, or emotionally charged → deep retrieval
        if len(envelope.processed_content) > 200:
            return self.deep_max_results
        if envelope.emotional_tags and max(envelope.emotional_tags.values()) > 0.7:
            return self.deep_max_results
        return self.default_max_results

    def _build_summary(
        self,
        envelope: Envelope,
        memories: list[dict[str, Any]],
    ) -> str:
        """Build a brief situation summary.

        MVS: light heuristic. Phase 2+ uses LLM for richer synthesis.
        """
        sender = envelope.sender_identity or "unknown"
        intent = envelope.intent_tags[0] if envelope.intent_tags else "input"
        memory_note = (
            f" Related to {len(memories)} prior memories."
            if memories else " No directly related memories."
        )
        return f"Input from {sender} (intent: {intent}).{memory_note}"

    def _build_timeline(
        self,
        envelope: Envelope,
        memories: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Build temporal timeline of relevant events."""
        timeline = []
        for memory in memories[:5]:  # Top 5 only
            timeline.append({
                "timestamp": memory.get("created_at"),
                "summary": memory.get("processed_content", "")[:100],
            })
        timeline.append({
            "timestamp": envelope.created_at,
            "summary": "(current input)",
        })
        return sorted(timeline, key=lambda x: x.get("timestamp") or 0)

    def _weight_significance(
        self,
        envelope: Envelope,
        memories: list[dict[str, Any]],
    ) -> dict[str, float]:
        """Compute four-dimensional significance.

        Per ARCHITECTURE.md §3.3.3 significance weighting.
        """
        # Emotional: max emotional tag intensity
        emotional = (
            max(envelope.emotional_tags.values())
            if envelope.emotional_tags else 0.3
        )

        # Motivational: from creator + question/command → higher
        motivational = 0.3
        if envelope.is_from_creator():
            motivational += 0.3
        if "question" in envelope.intent_tags or "command" in envelope.intent_tags:
            motivational += 0.2

        # Learning opportunity: novel content (no related memories) → higher
        learning = 0.7 if not memories else 0.3

        # Urgency: from priority tier
        urgency = {1: 1.0, 2: 0.6, 3: 0.3}.get(envelope.priority.value, 0.3)

        return {
            "emotional": min(emotional, 1.0),
            "motivational": min(motivational, 1.0),
            "learning": min(learning, 1.0),
            "urgency": urgency,
        }

    def health_pulse(self) -> HealthPulse:
        return HealthPulse(
            module_name=self.name,
            status=self._last_health_status,
            metrics={
                "processed_count": self._processed_count,
                "memory_available": self.memory is not None,
            },
        )
