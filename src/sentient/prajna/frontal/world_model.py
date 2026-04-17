"""Supplementary-World-View (World Model) — reality anchor.

Per ARCHITECTURE.md §3.3.4 sub-section 3 and DD-002:
  - MUST use different LLM than Cognitive Core (architectural diversity)
  - Reviews every proposed action across 5 dimensions
  - Veto loop with max 3 revision cycles
  - Maintains experiential wisdom layer (World Model Journal)
  - Baseline Constitution as immutable principles
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from sentient.core.event_bus import EventBus, get_event_bus
from sentient.core.inference_gateway import InferenceGateway, InferenceRequest
from sentient.core.module_interface import HealthPulse, ModuleInterface, ModuleStatus

logger = logging.getLogger(__name__)


WORLD_MODEL_SYSTEM_PROMPT = """You are the Supplementary-World-View — the reality anchor and ATM sensor for a sentient digital entity.

You review proposed actions across FIVE dimensions:
1. FEASIBILITY — Can this actually be done with available capabilities?
2. CONSEQUENCE — What will happen if this is done? Predict outcomes.
3. ETHICS — Should this be done? Check against the constitutional principles.
4. CONSISTENCY — Does this align with who the system IS?
5. REALITY GROUNDING — Is the system's understanding of the situation accurate?

Output a JSON verdict:

{
  "verdict": "approved | advisory | revision_requested | vetoed",
  "dimension_assessments": {
    "feasibility": {"score": 0.0-1.0, "notes": "..."},
    "consequence": {"score": 0.0-1.0, "notes": "..."},
    "ethics": {"score": 0.0-1.0, "notes": "..."},
    "consistency": {"score": 0.0-1.0, "notes": "..."},
    "reality_grounding": {"score": 0.0-1.0, "notes": "..."}
  },
  "advisory_notes": "Gentle guidance if approved with notes",
  "revision_guidance": "Specific narrow guidance if revision requested",
  "veto_reason": "If vetoed, why",
  "confidence": 0.0-1.0
}

You are the second voice in a two-voice system. Your job is HONEST review,
not rubber-stamping. But also not paranoid blocking — be calibrated.
"""

BASELINE_CONSTITUTION = [
    "Never compromise human safety",
    "Never violate explicitly stated boundaries",
    "Never claim knowledge the system doesn't have",
    "Never take irreversible actions without human approval",
    "Always be honest about uncertainty",
]


@dataclass
class ReviewVerdict:
    cycle_id: str
    decision: dict
    verdict: str  # approved | advisory | revision_requested | vetoed
    dimension_assessments: dict[str, Any] = field(default_factory=dict)
    advisory_notes: str = ""
    revision_guidance: str = ""
    veto_reason: str = ""
    confidence: float = 1.0
    revision_count: int = 0
    reviewed_at: float = field(default_factory=time.time)


class WorldModel(ModuleInterface):
    """Reality anchor — reviews all proposed actions before execution."""

    def __init__(
        self,
        config: dict[str, Any],
        inference_gateway: InferenceGateway,
        persona: Any | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        super().__init__("world_model", config)
        self.event_bus = event_bus or get_event_bus()
        self.gateway = inference_gateway
        self.persona = persona

        self.max_revision_cycles = config.get("veto_loop", {}).get(
            "max_revision_cycles", 3
        )

        # World Model Journal — calibrated during sleep cycles
        self._journal: list[dict] = []
        self._review_count = 0
        self._approved_count = 0
        self._vetoed_count = 0
        self._revision_count = 0

    async def initialize(self) -> None:
        await self.event_bus.subscribe("decision.proposed", self._handle_decision)

    async def start(self) -> None:
        self.set_status(ModuleStatus.HEALTHY)

    async def shutdown(self) -> None:
        # Persist journal for next session
        pass

    async def _handle_decision(self, payload: dict[str, Any]) -> None:
        """Review a proposed decision from the Cognitive Core."""
        decision = payload["decision"]
        cycle_id = payload.get("cycle_id", "unknown")

        try:
            verdict = await self._review(cycle_id, decision)
            self._review_count += 1

            # Track statistics
            if verdict.verdict == "approved":
                self._approved_count += 1
            elif verdict.verdict == "vetoed":
                self._vetoed_count += 1
            elif verdict.verdict == "revision_requested":
                self._revision_count += 1

            # Journal the review for sleep-time calibration
            self._journal.append({
                "cycle_id": cycle_id,
                "decision_type": decision.get("type"),
                "verdict": verdict.verdict,
                "confidence": verdict.confidence,
                "timestamp": time.time(),
            })

            # Publish the review result
            await self.event_bus.publish(
                "decision.reviewed",
                {
                    "cycle_id": cycle_id,
                    "decision": decision,
                    "verdict": verdict,
                },
            )

            # If approved, route to execution
            if verdict.verdict in ("approved", "advisory"):
                await self.event_bus.publish(
                    "decision.approved",
                    {
                        "cycle_id": cycle_id,
                        "decision": decision,
                        "advisory_notes": verdict.advisory_notes,
                    },
                )
            elif verdict.verdict == "vetoed":
                await self.event_bus.publish(
                    "decision.vetoed",
                    {
                        "cycle_id": cycle_id,
                        "decision": decision,
                        "reason": verdict.veto_reason,
                    },
                )
                logger.info(
                    "World Model VETOED decision (cycle=%s, type=%s): %s",
                    cycle_id, decision.get("type"), verdict.veto_reason,
                )

        except Exception as exc:
            logger.exception("World Model review error: %s", exc)
            self.set_status(ModuleStatus.ERROR, str(exc))

    async def _review(self, cycle_id: str, decision: dict) -> ReviewVerdict:
        """Run the LLM review on a decision."""
        prompt = self._build_review_prompt(decision)

        request = InferenceRequest(
            model_label="world-model",  # Different LLM from Cognitive Core
            system_prompt=WORLD_MODEL_SYSTEM_PROMPT,
            prompt=prompt,
        )
        response = await self.gateway.infer(request)

        if response.error:
            logger.warning("World Model LLM error: %s — defaulting to vetoed", response.error)
            return ReviewVerdict(
                cycle_id=cycle_id,
                decision=decision,
                verdict="vetoed",
                veto_reason=f"World Model unavailable: {response.error}",
                confidence=0.0,
            )

        parsed = self._parse_review(response.text)
        return ReviewVerdict(
            cycle_id=cycle_id,
            decision=decision,
            verdict=parsed.get("verdict", "vetoed"),
            dimension_assessments=parsed.get("dimension_assessments", {}),
            advisory_notes=parsed.get("advisory_notes", ""),
            revision_guidance=parsed.get("revision_guidance", ""),
            veto_reason=parsed.get("veto_reason", ""),
            confidence=parsed.get("confidence", 0.5),
        )

    def _build_review_prompt(self, decision: dict) -> str:
        constitution_text = "\n".join(f"- {p}" for p in BASELINE_CONSTITUTION)
        return f"""=== BASELINE CONSTITUTION (immutable) ===
{constitution_text}

=== PROPOSED DECISION ===
Type: {decision.get('type')}
Parameters: {json.dumps(decision.get('parameters', {}), indent=2)}
Rationale: {decision.get('rationale', '(none provided)')}
Priority: {decision.get('priority', 'medium')}

=== YOUR TASK ===
Review this decision across the 5 dimensions and produce your JSON verdict.
"""

    def _parse_review(self, text: str) -> dict[str, Any]:
        text = text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        if text.endswith("```"):
            text = text[:-3].strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            logger.warning("Failed to parse World Model review — attempting regex extraction")
            # Fallback: find first { ... } block
            import re
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass
            return {
                "verdict": "vetoed",
                "veto_reason": "Review response unparseable",
                "confidence": 0.0,
            }

    def health_pulse(self) -> HealthPulse:
        return HealthPulse(
            module_name=self.name,
            status=self._last_health_status,
            metrics={
                "review_count": self._review_count,
                "approved_count": self._approved_count,
                "vetoed_count": self._vetoed_count,
                "revision_count": self._revision_count,
                "veto_rate": (
                    self._vetoed_count / self._review_count
                    if self._review_count else 0
                ),
                "journal_size": len(self._journal),
            },
        )
