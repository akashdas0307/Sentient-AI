"""Memory Architecture — four memory types with dual storage.

Per ARCHITECTURE.md §3.3.4 sub-section 4 and DD-007:
  - Four types: Episodic, Semantic, Procedural, Emotional
  - Dual storage: SQLite+FTS5 (structured) + ChromaDB (semantic)
  - Logic-based Gatekeeper (no LLM in write path) — DD-008
  - Multi-path retrieval
  - Six-step lifecycle: Capture → Gatekeeper → Tagging → Storage → Retrieval → Evolution
"""

from sentient.memory.architecture import MemoryArchitecture, MemoryType
from sentient.memory.gatekeeper import MemoryGatekeeper

__all__ = ["MemoryArchitecture", "MemoryType", "MemoryGatekeeper"]
