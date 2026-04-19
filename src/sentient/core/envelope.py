"""Standard envelope format for all data flowing through the system.

Per the architecture, every input (external or internal) is normalized into
this envelope structure. The Thalamus produces it from external inputs;
internal modules (Memory, Health, Sleep, World Model) produce envelopes
for queue-bound items in the same format.

Reference: ARCHITECTURE.md §3.1, DESIGN_DECISIONS.md DD-019
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Priority(Enum):
    """Three-tier priority system from PRD FR-1.3."""

    TIER_1_IMMEDIATE = 1   # Breaks cycle, processed instantly
    TIER_2_ELEVATED = 2    # Shortens batching window
    TIER_3_NORMAL = 3      # Standard batching


class SourceType(Enum):
    """Where the envelope originated. Used for trust and routing decisions."""

    # External sources (through Thalamus plugins)
    CHAT = "chat"
    VOICE = "voice"
    AMBIENT_AUDIO = "ambient_audio"
    VISUAL = "visual"
    BROWSER = "browser"
    FILE_SYSTEM = "file_system"
    CALENDAR = "calendar"
    EMAIL = "email"
    TELEGRAM = "telegram"
    SYSTEM_MONITOR = "system_monitor"

    # Internal sources (queue-bound from other modules)
    INTERNAL_LIMBIC = "internal_limbic"
    INTERNAL_HEALTH = "internal_health"
    INTERNAL_DREAM = "internal_dream"
    INTERNAL_WORLD_MODEL = "internal_world_model"
    INTERNAL_MEMORY = "internal_memory"
    INTERNAL_SCHEDULED = "internal_scheduled"
    INTERNAL_EAL = "internal_eal"


class TrustLevel(Enum):
    """Trust hierarchy from FR-9 multi-human handling."""

    TIER_1_CREATOR = 1     # Full transparency, absolute authority
    TIER_2_TRUSTED = 2     # Delegated authority, bounded trust
    TIER_3_EXTERNAL = 3    # No authority, request-only
    SYSTEM = 0             # Internal — fully trusted


@dataclass
class Envelope:
    """The standard data envelope flowing through the system.

    Every piece of data — chat message, sensor reading, internal alert,
    scheduled trigger — uses this format. The same envelope flows from
    Thalamus → Checkpost → Queue Zone → TLP → Cognitive Core, with each
    stage enriching the metadata.
    """

    # === Identity ===
    envelope_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parent_id: str | None = None   # If this envelope spawned from another

    # === Source ===
    source_type: SourceType = SourceType.CHAT
    plugin_name: str = ""          # Which specific plugin or module produced this
    sender_identity: str | None = None   # Who/what is the originating entity
    trust_level: TrustLevel = TrustLevel.SYSTEM

    # === Priority ===
    priority: Priority = Priority.TIER_3_NORMAL

    # === Timing ===
    created_at: float = field(default_factory=time.time)
    expires_at: float | None = None   # For time-sensitive items
    received_at: float | None = None  # When Thalamus accepted it
    delivered_at: float | None = None # When Frontal Processor consumed it

    # === Content ===
    raw_content: Any = None        # As received from plugin
    processed_content: str = ""    # Normalized text representation
    metadata: dict[str, Any] = field(default_factory=dict)

    # === Tags (added progressively through pipeline) ===
    entity_tags: list[str] = field(default_factory=list)      # Recognized entities
    topic_tags: list[str] = field(default_factory=list)       # Topics/categories
    intent_tags: list[str] = field(default_factory=list)      # Detected intents
    emotional_tags: dict[str, float] = field(default_factory=dict)  # Emotion: intensity

    # === Pipeline state (added by each module) ===
    checkpost_processed: bool = False
    tlp_enriched: bool = False
    significance: dict[str, float] = field(default_factory=dict)
    # significance keys: emotional, motivational, learning, urgency

    # === Memory associations (added by TLP) ===
    related_memory_ids: list[str] = field(default_factory=list)

    # === Confidence and provenance ===
    confidence: float = 1.0   # How sure we are about the envelope contents
    processing_notes: list[str] = field(default_factory=list)

    def add_tag(self, category: str, tag: str) -> None:
        """Add a tag to the appropriate category."""
        target = {
            "entity": self.entity_tags,
            "topic": self.topic_tags,
            "intent": self.intent_tags,
        }.get(category)
        if target is not None and tag not in target:
            target.append(tag)

    def add_emotion(self, emotion: str, intensity: float) -> None:
        """Add or update an emotional tag (intensity 0.0-1.0)."""
        self.emotional_tags[emotion] = max(0.0, min(1.0, intensity))

    def is_expired(self) -> bool:
        """Check if this envelope has expired."""
        return self.expires_at is not None and time.time() > self.expires_at

    def age_seconds(self) -> float:
        """How long since this envelope was created."""
        return time.time() - self.created_at

    def is_external(self) -> bool:
        """True if this came from outside the system."""
        return self.source_type.value not in {
            "internal_limbic", "internal_health", "internal_dream",
            "internal_world_model", "internal_memory", "internal_scheduled",
            "internal_eal",
        }

    def is_from_creator(self) -> bool:
        """True if this is from the Tier 1 human."""
        return self.trust_level == TrustLevel.TIER_1_CREATOR

    def to_dict(self) -> dict[str, Any]:
        """Serialize for logging/storage."""
        return {
            "envelope_id": self.envelope_id,
            "parent_id": self.parent_id,
            "source_type": self.source_type.value,
            "plugin_name": self.plugin_name,
            "sender_identity": self.sender_identity,
            "trust_level": self.trust_level.value,
            "priority": self.priority.value,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "received_at": self.received_at,
            "delivered_at": self.delivered_at,
            "processed_content": self.processed_content,
            "metadata": self.metadata,
            "entity_tags": self.entity_tags,
            "topic_tags": self.topic_tags,
            "intent_tags": self.intent_tags,
            "emotional_tags": self.emotional_tags,
            "checkpost_processed": self.checkpost_processed,
            "tlp_enriched": self.tlp_enriched,
            "significance": self.significance,
            "related_memory_ids": self.related_memory_ids,
            "confidence": self.confidence,
            "processing_notes": self.processing_notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Envelope:
        """Reconstruct an Envelope from a dict (e.g., after JSON deserialization).

        Handles nested enums and defensively fills missing fields with sensible defaults.
        """
        # Resolve source_type enum (can be string or int from dataclasses.asdict)
        source_type_val = data.get("source_type")
        if isinstance(source_type_val, str):
            try:
                source_type = SourceType(source_type_val)
            except ValueError:
                source_type = SourceType.CHAT
        elif isinstance(source_type_val, int):
            try:
                source_type = SourceType(source_type_val)
            except ValueError:
                source_type = SourceType.CHAT
        else:
            source_type = source_type_val or SourceType.CHAT

        # Resolve trust_level enum (can be string or int)
        trust_val = data.get("trust_level")
        if isinstance(trust_val, str):
            try:
                trust_level = TrustLevel(trust_val)
            except ValueError:
                trust_level = TrustLevel.SYSTEM
        elif isinstance(trust_val, int):
            try:
                trust_level = TrustLevel(trust_val)
            except ValueError:
                trust_level = TrustLevel.SYSTEM
        else:
            trust_level = trust_val or TrustLevel.SYSTEM

        # Resolve priority enum (can be string or int)
        priority_val = data.get("priority")
        if isinstance(priority_val, str):
            try:
                priority = Priority(priority_val)
            except ValueError:
                priority = Priority.TIER_3_NORMAL
        elif isinstance(priority_val, int):
            try:
                priority = Priority(priority_val)
            except ValueError:
                priority = Priority.TIER_3_NORMAL
        else:
            priority = priority_val or Priority.TIER_3_NORMAL

        return cls(
            envelope_id=data.get("envelope_id", ""),
            parent_id=data.get("parent_id"),
            source_type=source_type,
            plugin_name=data.get("plugin_name", ""),
            sender_identity=data.get("sender_identity"),
            trust_level=trust_level,
            priority=priority,
            created_at=data.get("created_at", 0.0),
            expires_at=data.get("expires_at"),
            received_at=data.get("received_at"),
            delivered_at=data.get("delivered_at"),
            raw_content=data.get("raw_content"),
            processed_content=data.get("processed_content", ""),
            metadata=data.get("metadata", {}),
            entity_tags=data.get("entity_tags", []),
            topic_tags=data.get("topic_tags", []),
            intent_tags=data.get("intent_tags", []),
            emotional_tags=data.get("emotional_tags", {}),
            checkpost_processed=data.get("checkpost_processed", False),
            tlp_enriched=data.get("tlp_enriched", False),
            significance=data.get("significance", {}),
            related_memory_ids=data.get("related_memory_ids", []),
            confidence=data.get("confidence", 1.0),
            processing_notes=data.get("processing_notes", []),
        )
