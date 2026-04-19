"""Procedural memory store — behavioral patterns extracted from consolidation."""
from __future__ import annotations

import json
import logging
import sqlite3
import time
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ProceduralPattern(BaseModel):
    """A behavioral pattern extracted from episodic memories during consolidation."""

    pattern_id: str  # UUID generated post-extraction
    description: str
    trigger_context: str = ""
    confidence: float = 0.5  # 0.0-1.0
    evidence_episode_ids: list[str] = []
    evidence_count: int = 0
    first_observed: float  # Unix timestamp
    last_reinforced: float  # Unix timestamp
    reinforcement_count: int = 1


class ProceduralStore:
    """SQLite-backed store for procedural patterns."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._ensure_table()

    def _ensure_table(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS procedural_memory (
                pattern_id TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                trigger_context TEXT NOT NULL DEFAULT '',
                confidence REAL NOT NULL DEFAULT 0.5,
                evidence_episode_ids TEXT NOT NULL DEFAULT '[]',
                evidence_count INTEGER NOT NULL DEFAULT 0,
                first_observed REAL NOT NULL,
                last_reinforced REAL NOT NULL,
                reinforcement_count INTEGER NOT NULL DEFAULT 1,
                created_at REAL NOT NULL
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_procedural_confidence ON procedural_memory(confidence)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_procedural_first_observed ON procedural_memory(first_observed)"
        )

    async def store(self, pattern: ProceduralPattern) -> str:
        """Store a procedural pattern. Returns the pattern_id."""
        now = time.time()
        self._conn.execute(
            """
            INSERT INTO procedural_memory (
                pattern_id, description, trigger_context, confidence,
                evidence_episode_ids, evidence_count, first_observed,
                last_reinforced, reinforcement_count, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                pattern.pattern_id,
                pattern.description,
                pattern.trigger_context,
                pattern.confidence,
                json.dumps(pattern.evidence_episode_ids),
                pattern.evidence_count,
                pattern.first_observed,
                pattern.last_reinforced,
                pattern.reinforcement_count,
                now,
            ),
        )
        return pattern.pattern_id

    async def retrieve(self, context: str, k: int = 3) -> list[dict[str, Any]]:
        """Retrieve top-k procedural patterns using FTS5 or LIKE fallback."""
        if not context:
            rows = self._conn.execute(
                """
                SELECT * FROM procedural_memory
                ORDER BY confidence DESC, reinforcement_count DESC
                LIMIT ?
                """,
                (k,),
            ).fetchall()
        else:
            # Try FTS5 first, fall back to LIKE
            try:
                escaped = context.replace('"', '""')
                rows = self._conn.execute(
                    """
                    SELECT pm.* FROM procedural_memory pm
                    WHERE pm.pattern_id IN (
                        SELECT pattern_id FROM procedural_memory
                        WHERE description MATCH ? OR trigger_context MATCH ?
                        ORDER BY confidence DESC
                        LIMIT ?
                    )
                    """,
                    (f'"{escaped}"', f'"{escaped}"', k),
                ).fetchall()
            except sqlite3.OperationalError:
                # Fall back to LIKE
                like_pattern = f"%{context}%"
                rows = self._conn.execute(
                    """
                    SELECT * FROM procedural_memory
                    WHERE description LIKE ? OR trigger_context LIKE ?
                    ORDER BY confidence DESC
                    LIMIT ?
                    """,
                    (like_pattern, like_pattern, k),
                ).fetchall()

        return [self._row_to_dict(row) for row in rows]

    async def reinforce(self, pattern_id: str) -> None:
        """Bump confidence by 0.05 (capped at 1.0) and increment reinforcement_count."""
        self._conn.execute(
            """
            UPDATE procedural_memory
            SET confidence = MIN(1.0, confidence + 0.05),
                reinforcement_count = reinforcement_count + 1,
                last_reinforced = ?
            WHERE pattern_id = ?
            """,
            (time.time(), pattern_id),
        )

    async def list_all(self) -> list[dict[str, Any]]:
        """Return all procedural patterns ordered by confidence descending."""
        rows = self._conn.execute(
            """
            SELECT * FROM procedural_memory
            ORDER BY confidence DESC, reinforcement_count DESC
            """
        ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        result["evidence_episode_ids"] = json.loads(result.get("evidence_episode_ids", "[]"))
        return result