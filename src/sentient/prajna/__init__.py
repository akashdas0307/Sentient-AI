"""Prajñā — Intelligence Core (Sanskrit for wisdom/awareness).

Four-step pipeline: Checkpost → Queue Zone → TLP → Frontal Processor.
Per ARCHITECTURE.md §3.3.
"""

from sentient.prajna.checkpost import Checkpost
from sentient.prajna.queue_zone import QueueZone
from sentient.prajna.temporal_limbic import TemporalLimbicProcessor

__all__ = ["Checkpost", "QueueZone", "TemporalLimbicProcessor"]
