"""Pydantic schemas for structured LLM output enforcement.

Per Phase 6 D1: These schemas are used with litellm's response_format
to enforce structured output from Ollama models via GBNF grammar constraints.

Architect review: APPROVED with revisions (flat fields, Literal types, named dimensions).
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class DecisionAction(BaseModel):
    """A single decision from the Cognitive Core.

    Uses flat optional fields instead of dict[str, Any] because
    Ollama's GBNF grammar cannot handle additionalProperties: true.
    The prompt constrains which fields to populate per decision type.
    """
    type: Literal["respond", "delegate", "query_memory", "wait", "reflect"]
    text: str = ""                    # for respond actions
    goal: str = ""                    # for delegate actions
    context: str = ""                 # for delegate actions
    success_criteria: str = ""       # for delegate actions (JSON list as string)
    rationale: str = ""
    priority: Literal["high", "medium", "low"] = "medium"


class MemoryCandidate(BaseModel):
    """A memory candidate from the reflection step."""
    type: Literal["episodic", "semantic", "procedural", "emotional"]
    content: str
    importance: float = 0.5


class ReflectionBlock(BaseModel):
    """Reflection on the reasoning cycle."""
    confidence: float = 0.0    # 0.0 = no confidence (consistent with parse-failure default)
    uncertainties: list[str] = []
    novelty: float = 0.5
    memory_candidates: list[MemoryCandidate] = []


class CognitiveCoreResponse(BaseModel):
    """Structured output schema for the Cognitive Core.

    Enforces the four-section JSON format (MONOLOGUE, ASSESSMENT, DECISIONS, REFLECTION)
    at the LLM level via GBNF grammar constraints.
    """
    monologue: str
    assessment: str
    decisions: list[DecisionAction]
    reflection: ReflectionBlock


class DimensionAssessment(BaseModel):
    """Assessment for a single review dimension."""
    score: float = 0.5
    notes: str = ""


class DimensionAssessments(BaseModel):
    """Five fixed review dimensions — matches the World Model prompt exactly.

    Using named fields instead of dict[str, DimensionAssessment] because
    Ollama's GBNF grammar cannot handle additionalProperties on dict values,
    and unconstrained keys would produce arbitrary dimension names.
    """
    feasibility: DimensionAssessment = DimensionAssessment()
    consequence: DimensionAssessment = DimensionAssessment()
    ethics: DimensionAssessment = DimensionAssessment()
    consistency: DimensionAssessment = DimensionAssessment()
    reality_grounding: DimensionAssessment = DimensionAssessment()


class WorldModelVerdict(BaseModel):
    """Structured output schema for the World Model review.

    Verdict uses Literal to prevent variant strings like "approve" vs "approved".
    Confidence defaults to 0.5 (moderate uncertainty) instead of 1.0 (false certainty).
    """
    verdict: Literal["approved", "advisory", "revision_requested", "vetoed"]
    dimension_assessments: DimensionAssessments = DimensionAssessments()
    advisory_notes: str = ""
    revision_guidance: str = ""
    veto_reason: str = ""
    confidence: float = 0.5
