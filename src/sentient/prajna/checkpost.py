"""Pre-Temporal-Occipital-Checkpost — first stage of Prajñā pipeline.

Per ARCHITECTURE.md §3.3.1:
  - Entity recognition (who/what is this about)
  - Intent classification
  - Source tagging
  - Flash memory lookup for known entities
  - Three-phase learning for new data sources
"""
from __future__ import annotations

import logging
from typing import Any

from sentient.core.envelope import Envelope
from sentient.core.event_bus import EventBus, get_event_bus
from sentient.core.inference_gateway import InferenceGateway
from sentient.core.module_interface import HealthPulse, ModuleInterface, ModuleStatus

logger = logging.getLogger(__name__)


class Checkpost(ModuleInterface):
    """First stage of Prajñā: deep identification and contextual tagging."""

    def __init__(
        self,
        config: dict[str, Any],
        inference_gateway: InferenceGateway,
        memory: Any | None = None,   # MemoryArchitecture (forward ref)
        event_bus: EventBus | None = None,
    ) -> None:
        super().__init__("checkpost", config)
        self.event_bus = event_bus or get_event_bus()
        self.gateway = inference_gateway
        self.memory = memory

        self._processed_count = 0
        self._latencies_ms: list[float] = []

    async def initialize(self) -> None:
        await self.event_bus.subscribe("input.classified", self._handle_input)
        logger.info("Checkpost initialized")

    async def start(self) -> None:
        self.set_status(ModuleStatus.HEALTHY)

    async def shutdown(self) -> None:
        pass

    async def _handle_input(self, payload: dict[str, Any]) -> None:
        """Process an envelope from the Thalamus."""
        envelope: Envelope = payload["envelope"]
        try:
            await self._process(envelope)
            self._processed_count += 1
            await self.event_bus.publish(
                "checkpost.tagged",
                {"envelope": envelope},
            )
        except Exception as exc:
            logger.exception("Checkpost processing error: %s", exc)
            self.set_status(ModuleStatus.ERROR, str(exc))

    async def _process(self, envelope: Envelope) -> None:
        """Tag the envelope with entities, intents, and source context.

        MVS implementation: light heuristic tagging + optional LLM enhancement.
        Phase 2+ should expand to full entity recognition with the local model.
        """
        # Flash memory lookup for known entities (if memory available)
        if self.memory is not None and envelope.entity_tags:
            for entity in envelope.entity_tags:
                # Stub: in full implementation, query memory for entity context
                # and attach last_seen timestamp, recent topics, etc.
                pass

        # For MVS, intent tags from chat plugin are sufficient.
        # In Phase 2+, run the checkpost LLM for richer tagging.
        if envelope.processed_content and len(envelope.processed_content) > 30:
            # Only invoke LLM for substantive inputs to control cost
            await self._llm_enhance(envelope)

        envelope.checkpost_processed = True

    async def _llm_enhance(self, envelope: Envelope) -> None:
        """Use the checkpost LLM to add deeper tagging.

        STUB: In full implementation, prompt the local LLM to extract
        entities, refine intent, and detect emotional tone.
        """
        # MVS: skip LLM call to keep cost down. Light heuristic only.
        # Phase 2+ implementation:
        #
        # request = InferenceRequest(
        #     model_label="checkpost",
        #     system_prompt=CHECKPOST_SYSTEM_PROMPT,
        #     prompt=f"Tag this input:\n{envelope.processed_content}",
        # )
        # response = await self.gateway.infer(request)
        # parsed = parse_checkpost_response(response.text)
        # envelope.entity_tags.extend(parsed.get("entities", []))
        # envelope.topic_tags.extend(parsed.get("topics", []))
        # for emotion, intensity in parsed.get("emotions", {}).items():
        #     envelope.add_emotion(emotion, intensity)
        pass

    def health_pulse(self) -> HealthPulse:
        avg_latency = (
            sum(self._latencies_ms[-100:]) / min(len(self._latencies_ms), 100)
            if self._latencies_ms else 0
        )
        return HealthPulse(
            module_name=self.name,
            status=self._last_health_status,
            metrics={
                "processed_count": self._processed_count,
                "avg_latency_ms": round(avg_latency, 2),
            },
        )
