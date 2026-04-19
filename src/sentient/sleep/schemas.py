"""Pydantic schemas for consolidation LLM output."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ExtractedFact(BaseModel):
    """A single semantic fact extracted from episodic memories."""
    statement: str = Field(description="A factual statement that is supported by evidence across multiple episodes")
    confidence: float = Field(description="Confidence score 0.0-1.0", ge=0.0, le=1.0)
    evidence_episode_ids: list[str] = Field(description="IDs of episodes that support this fact. Minimum 2 required.")
    importance: float = Field(default=0.5, description="Importance of this fact for future reference")


class ExtractedPattern(BaseModel):
    """A single behavioral or preference pattern extracted from episodic memories."""
    description: str = Field(description="A behavioral pattern or preference observed across episodes")
    trigger_context: str = Field(default="", description="Context or situation that triggers this pattern")
    confidence: float = Field(description="Confidence score 0.0-1.0", ge=0.0, le=1.0)
    evidence_episode_ids: list[str] = Field(description="IDs of episodes that support this pattern. Minimum 2 required.")
    importance: float = Field(default=0.5, description="Importance of this pattern for future reference")


class SemanticFactList(BaseModel):
    """Structured output schema for semantic extraction."""
    facts: list[ExtractedFact] = Field(description="List of semantic facts extracted from episodic memories")


class ProceduralPatternList(BaseModel):
    """Structured output schema for procedural extraction."""
    patterns: list[ExtractedPattern] = Field(description="List of behavioral patterns extracted from episodic memories")
