"""Layer 1 Heuristic Engine — fast rule-based pattern matching.

Per DD-015, Layer 1 uses NO LLM. Pure deterministic code for:
  - Tier 1 interrupt detection (urgency keywords, system health critical)
  - Basic deduplication by timestamp correlation
  - Volume spike detection (when audio plugin is active in Phase 2)

Reference: ARCHITECTURE.md §3.1
"""
from __future__ import annotations

import logging
from typing import Any

from sentient.core.envelope import Envelope, Priority

logger = logging.getLogger(__name__)


class HeuristicEngine:
    """Fast deterministic pattern matching for Layer 1 input classification."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.tier1_keywords: list[str] = [
            kw.lower() for kw in config.get("tier1_keywords", [])
        ]
        self.tier1_health_threshold: str = config.get(
            "tier1_health_flag_threshold", "CRITICAL"
        )

    def classify(self, envelope: Envelope) -> Priority:
        """Determine envelope priority using Layer 1 rules.

        Returns Priority. If Tier 1 is detected, the Thalamus should
        immediately collapse the batching window and forward.
        """
        # Health alerts at CRITICAL/SYSTEM_DOWN are always Tier 1
        if envelope.source_type.value == "internal_health":
            severity = envelope.metadata.get("severity", "")
            if severity in ("CRITICAL", "SYSTEM_DOWN"):
                return Priority.TIER_1_IMMEDIATE

        # Creator messages get baseline elevated priority
        if envelope.is_from_creator():
            base_priority = Priority.TIER_2_ELEVATED
        else:
            base_priority = Priority.TIER_3_NORMAL

        # Check for urgency keywords in content
        content_lower = envelope.processed_content.lower()
        for keyword in self.tier1_keywords:
            if keyword in content_lower:
                envelope.processing_notes.append(f"tier1: keyword '{keyword}'")
                return Priority.TIER_1_IMMEDIATE

        # Direct questions to creator from creator → elevated
        if envelope.is_from_creator() and "?" in envelope.processed_content:
            return Priority.TIER_2_ELEVATED

        return base_priority

    def is_likely_duplicate(
        self,
        envelope: Envelope,
        recent_envelopes: list[Envelope],
        window_seconds: float = 5.0,
    ) -> bool:
        """Detect if this envelope is a duplicate of something received recently.

        Used to merge same-event multi-sensor inputs (Job 4 of Thalamus).
        """
        for other in recent_envelopes:
            if abs(envelope.created_at - other.created_at) > window_seconds:
                continue
            # Same source + similar content → likely duplicate
            if (
                envelope.source_type == other.source_type
                and envelope.sender_identity == other.sender_identity
                and envelope.processed_content == other.processed_content
            ):
                return True
        return False
