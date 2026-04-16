"""Frontal Processor — the core of Prajñā.

Five sub-sections:
  - Cognitive Core (inner monologue, 7-step reasoning)
  - World Model (Supplementary-World-View, different LLM)
  - Memory Architecture (4 types, dual storage) — separate package
  - Persona Manager (3-layer identity) — separate package
  - Agent Harness Adapter (delegates execution)
"""

from sentient.prajna.frontal.cognitive_core import CognitiveCore
from sentient.prajna.frontal.world_model import WorldModel
from sentient.prajna.frontal.harness_adapter import HarnessAdapter

__all__ = ["CognitiveCore", "WorldModel", "HarnessAdapter"]
