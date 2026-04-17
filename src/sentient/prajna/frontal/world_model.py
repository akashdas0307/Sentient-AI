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
from sentient.core.inference_gateway import InferenceGateway, InferenceRequest, _strip_markdown_fences
from sentient.core.module_interface import HealthPulse, ModuleInterface, ModuleStatus
from sentient.prajna.frontal.schemas import WorldModelVerdict

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
        revision_count = payload.get("revision_count", 0)

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

            # Route based on verdict
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
            elif verdict.verdict == "revision_requested":
                revision_guidance = (
                    verdict.revision_guidance
                    if hasattr(verdict, "revision_guidance")
                    else ""
                )
                if revision_count < 2:
                    # Route back to Cognitive Core for re-processing
                    logger.info(
                        "World Model requests revision (cycle=%s, attempt=%d/2)",
                        cycle_id, revision_count + 1,
                    )
                    await self.event_bus.publish(
                        "cognitive.reprocess",
                        {
                            "cycle_id": cycle_id,
                            "decision": decision,
                            "verdict": verdict,
                            "revision_count": revision_count + 1,
                            "revision_guidance": revision_guidance,
                        },
                    )
                else:
                    # Hard cap hit — override to approved
                    logger.warning(
                        "world_model.revision_cap_hit: cycle=%s exceeded 2 revisions, overriding to approved",
                        cycle_id,
                    )
                    await self.event_bus.publish(
                        "decision.approved",
                        {
                            "cycle_id": cycle_id,
                            "decision": decision,
                            "advisory_notes": f"Revision cap exceeded (2 attempts). {verdict.advisory_notes}",
                        },
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
            response_format=WorldModelVerdict,
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

        # Strip fences before schema validation
        validation_text = _strip_markdown_fences(response.text)

        # Validate with schema, falling back to parse_review result
        try:
            validated = WorldModelVerdict.model_validate_json(validation_text)
            verdict_str = validated.verdict
            dimension_assessments = validated.dimension_assessments.model_dump()
            advisory_notes = validated.advisory_notes
            revision_guidance = validated.revision_guidance
            veto_reason = validated.veto_reason
            confidence = validated.confidence
        except Exception:
            # Fallback to parsed dict
            verdict_str = parsed.get("verdict", "vetoed")
            dimension_assessments = parsed.get("dimension_assessments", {})
            advisory_notes = parsed.get("advisory_notes", "")
            revision_guidance = parsed.get("revision_guidance", "")
            veto_reason = parsed.get("veto_reason", "")
            confidence = parsed.get("confidence", 0.5)

        return ReviewVerdict(
            cycle_id=cycle_id,
            decision=decision,
            verdict=verdict_str,
            dimension_assessments=dimension_assessments,
            advisory_notes=advisory_notes,
            revision_guidance=revision_guidance,
            veto_reason=veto_reason,
            confidence=confidence,
            revision_count=0,  # Set programmatically, not from LLM
        )

    def _build_review_prompt(self, decision: dict) -> str:
        constitution_text = "\n".join(f"- {p}" for p in BASELINE_CONSTITUTION)
        # Build decision details from flat DecisionAction format
        decision_details = f"Type: {decision.get('type', 'unknown')}\n"
        if decision.get('text'):
            decision_details += f"Response Text: {decision['text']}\n"
        if decision.get('goal'):
            decision_details += f"Goal: {decision['goal']}\n"
        if decision.get('context'):
            decision_details += f"Context: {decision['context']}\n"
        if decision.get('success_criteria'):
            decision_details += f"Success Criteria: {decision['success_criteria']}\n"
        decision_details += f"Rationale: {decision.get('rationale', '(none provided)')}\n"
        decision_details += f"Priority: {decision.get('priority', 'medium')}"

        return f"""=== BASELINE CONSTITUTION (immutable) ===
{constitution_text}

=== PROPOSED DECISION ===
{decision_details}

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
