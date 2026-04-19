"""Daydream Seed Engine — three source types for idle reflection seeds.

Per DD-020, when the system enters a daydream it picks from:
  1. RandomMemorySeed    — episodic memory weighted by recency × importance
  2. EmotionalResidueSeed — memories with emotional tags from the past N minutes
  3. CuriositySeed       — FIFO queue of follow-up questions from reasoning cycles

The selector randomly tries sources in order until one returns a seed.
If all fail (cold start), falls back to the static stub text.
"""
from __future__ import annotations

import logging
import random
import time
from abc import ABC, abstractmethod
from collections import deque
from typing import TYPE_CHECKING, Any

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from sentient.core.event_bus import EventBus
    from sentient.memory.architecture import MemoryArchitecture


class DaydreamSeed(ABC):
    """Abstract base for a daydream seed source."""

    @abstractmethod
    async def get_seed(self) -> str | None:
        """Return a seed string, or None if this source has nothing."""
        raise NotImplementedError


class RandomMemorySeed(DaydreamSeed):
    """Sample episodic memories weighted by recency × importance.

    Uses memory.retrieve_episodic() with a random-ish query.
    Cold start: returns None when no episodic memories exist.
    """

    def __init__(self, memory: MemoryArchitecture) -> None:
        self.memory = memory

    async def get_seed(self) -> str | None:
        """Pick a random episodic memory weighted by recency × importance."""
        try:
            memories = await self.memory.retrieve_episodic(
                context=_random_episodic_queries(),
                k=5,
            )
            if not memories:
                return None

            # Score by recency × importance
            now = time.time()
            scored = []
            for mem in memories:
                importance = float(mem.get("importance", 0.5))
                created_at = mem.get("created_at", now)
                # recency score: half-life of 7 days
                age_seconds = now - created_at
                half_life_seconds = 7 * 86400
                recency = 2 ** (-age_seconds / half_life_seconds)
                score = recency * importance
                scored.append((score, mem))

            scored.sort(key=lambda x: x[0], reverse=True)
            chosen = scored[0][1]
            content = chosen.get("content", "") or chosen.get("processed_content", "")
            return f"(memory trigger) {content[:300]}"
        except Exception as exc:
            logger.warning("RandomMemorySeed failed: %s", exc)
            return None


class EmotionalResidueSeed(DaydreamSeed):
    """Pull memories with emotional tags from the recent window.

    Falls back to most recent memory if no emotional tags found.
    Cold start: returns None.
    """

    def __init__(
        self,
        memory: MemoryArchitecture,
        window_minutes: int = 30,
    ) -> None:
        self.memory = memory
        self.window_minutes = window_minutes

    async def get_seed(self) -> str | None:
        """Return most emotionally resonant recent memory, or fallback to recent."""
        try:
            cutoff = time.time() - (self.window_minutes * 60)
            # Search for emotionally-tagged memories
            all_memories = await self.memory.retrieve(
                query="",
                limit=20,
            )
            emotional_memories = [
                m for m in all_memories
                if self._has_emotional_tags(m) and m.get("created_at", 0) >= cutoff
            ]
            if emotional_memories:
                chosen = emotional_memories[0]
            else:
                # Fallback: most recent memory
                recent = sorted(
                    [m for m in all_memories if m.get("created_at", 0) >= cutoff],
                    key=lambda m: m.get("created_at", 0),
                    reverse=True,
                )
                if recent:
                    chosen = recent[0]
                else:
                    # Last resort: most recent overall
                    all_memories_sorted = sorted(
                        all_memories,
                        key=lambda m: m.get("created_at", 0),
                        reverse=True,
                    )
                    if all_memories_sorted:
                        chosen = all_memories_sorted[0]
                    else:
                        return None

            content = chosen.get("content", "") or chosen.get("processed_content", "")
            return f"(emotional residue) {content[:300]}"
        except Exception as exc:
            logger.warning("EmotionalResidueSeed failed: %s", exc)
            return None

    def _has_emotional_tags(self, memory: dict[str, Any]) -> bool:
        """Check if memory has meaningful emotional tags."""
        import json

        raw = memory.get("emotional_tags", {})
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except Exception:
                return False
        if not isinstance(raw, dict):
            return False
        # Filter out empty/false values
        return any(bool(v) for v in raw.values())


class CuriositySeed(DaydreamSeed):
    """FIFO queue of follow-up questions from reasoning cycles.

    Questions are added via add_curiosity() when the LLM produces
    curiosity_candidates during reflection. Emits curiosity.queued
    events via the event bus.

    Max size is enforced: oldest item is dropped when capacity is exceeded.
    """

    def __init__(
        self,
        event_bus: EventBus,
        max_size: int = 20,
    ) -> None:
        self._queue: deque[str] = deque(maxlen=max_size)
        self._event_bus = event_bus

    def add_curiosity(self, question: str) -> None:
        """Add a question to the curiosity queue.

        Emits a curiosity.queued event.
        """
        # Avoid duplicates
        if question in self._queue:
            return
        self._queue.append(question)
        self._emit_queued(question)

    def _emit_queued(self, question: str) -> None:
        """Emit curiosity.queued event asynchronously."""
        try:
            import asyncio
            loop = asyncio.get_running_loop()
            loop.create_task(
                self._event_bus.publish(
                    "curiosity.queued",
                    {"question": question[:200], "queue_size": len(self._queue)},
                )
            )
        except Exception as exc:
            logger.warning("Failed to emit curiosity.queued event: %s", exc)

    async def get_seed(self) -> str | None:
        """Pop and return the oldest curiosity question (FIFO)."""
        if not self._queue:
            return None
        return self._queue.popleft()

    @property
    def queue_size(self) -> int:
        """Current number of items in the curiosity queue."""
        return len(self._queue)


class DaydreamSeedSelector:
    """Selects a daydream seed from one of several sources.

    Tries sources in random order. Returns first non-None result.
    Falls back to the stub text if all sources fail.
    """

    def __init__(
        self,
        sources: list[DaydreamSeed],
        stub_text: str | None = None,
    ) -> None:
        self._sources = sources
        self._stub = stub_text or _DEFAULT_STUB

    async def select_seed(self) -> str:
        """Try each source in random order, return first non-None result.

        Falls back to stub text if all sources return None.
        """
        if not self._sources:
            return self._stub

        shuffled = self._sources[:]
        random.shuffle(shuffled)

        for source in shuffled:
            try:
                seed = await source.get_seed()
                if seed is not None:
                    logger.debug("Daydream seed selected from %s", source.__class__.__name__)
                    return seed
            except Exception as exc:
                logger.warning(
                    "Seed source %s raised: %s — trying next",
                    source.__class__.__name__, exc,
                )
                continue

        logger.debug("All seed sources exhausted, using stub text")
        return self._stub


# Default stub used when all sources are exhausted
_DEFAULT_STUB = (
    "=== DAYDREAM SEED ===\n"
    "(idle reflection — let your thoughts wander naturally)"
)

# Random episodic query pool for variety
_EPISODIC_QUERIES = [
    "recent conversation",
    "interesting moment",
    "meaningful interaction",
    "what I learned",
    "something I noticed",
    "curious thought",
    "open question",
]


def _random_episodic_queries() -> str:
    """Return a random query string to vary episodic retrieval."""
    return random.choice(_EPISODIC_QUERIES)