"""Thalamus — Input Gateway.

Per ARCHITECTURE.md §3.1, normalizes all inputs into envelope format,
classifies priority, filters noise, deduplicates, delivers to Prajñā.
"""

from sentient.thalamus.gateway import Thalamus
from sentient.thalamus.heuristic_engine import HeuristicEngine
from sentient.thalamus.plugins.base import InputPlugin

__all__ = ["Thalamus", "HeuristicEngine", "InputPlugin"]
