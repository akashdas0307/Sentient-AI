"""Semantic memory store — facts extracted from episodic consolidation."""
from __future__ import annotations

import json
import logging
import sqlite3
import time
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class SemanticFact(BaseModel):
    """A fact extracted from episodic memories during consolidation."""

    fact_id: str  # UUID generated post-extraction
    statement: str
    confidence: float = 0.5  # 0.0-1.0
    evidence_episode_ids: list[str] = []
    evidence_count: int = 0
    first_observed: float  # Unix timestamp
    last_reinforced: float  # Unix timestamp
    reinforcement_count: int = 1


class SemanticStore:
    """SQLite-backed store for semantic facts."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._ensure_table()

    def _ensure_table(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS semantic_memory (
                fact_id TEXT PRIMARY KEY,
                statement TEXT NOT NULL,
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
            "CREATE INDEX IF NOT EXISTS idx_semantic_confidence ON semantic_memory(confidence)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_semantic_first_observed ON semantic_memory(first_observed)"
        )

    async def store(self, fact: SemanticFact) -> str:
        """Store a semantic fact. Returns the fact_id."""
        now = time.time()
        self._conn.execute(
            """
            INSERT INTO semantic_memory (
                fact_id, statement, confidence, evidence_episode_ids,
                evidence_count, first_observed, last_reinforced,
                reinforcement_count, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                fact.fact_id,
                fact.statement,
                fact.confidence,
                json.dumps(fact.evidence_episode_ids),
                fact.evidence_count,
                fact.first_observed,
                fact.last_reinforced,
                fact.reinforcement_count,
                now,
            ),
        )
        return fact.fact_id

    async def retrieve(self, query: str, k: int = 3) -> list[dict[str, Any]]:
        """Retrieve top-k semantic facts using FTS5 or LIKE fallback."""
        if not query:
            rows = self._conn.execute(
                """
                SELECT * FROM semantic_memory
                ORDER BY confidence DESC, reinforcement_count DESC
                LIMIT ?
                """,
                (k,),
            ).fetchall()
        else:
            # Try FTS5 first, fall back to LIKE
            try:
                escaped = query.replace('"', '""')
                rows = self._conn.execute(
                    """
                    SELECT sm.* FROM semantic_memory sm
                    WHERE sm.fact_id IN (
                        SELECT fact_id FROM semantic_memory
                        WHERE statement MATCH ?
                        ORDER BY confidence DESC
                        LIMIT ?
                    )
                    """,
                    (f'"{escaped}"', k),
                ).fetchall()
            except sqlite3.OperationalError:
                # Fall back to LIKE
                like_pattern = f"%{query}%"
                rows = self._conn.execute(
                    """
                    SELECT * FROM semantic_memory
                    WHERE statement LIKE ?
                    ORDER BY confidence DESC
                    LIMIT ?
                    """,
                    (like_pattern, k),
                ).fetchall()

        return [self._row_to_dict(row) for row in rows]

    async def reinforce(self, fact_id: str) -> None:
        """Bump confidence by 0.05 (capped at 1.0) and increment reinforcement_count."""
        self._conn.execute(
            """
            UPDATE semantic_memory
            SET confidence = MIN(1.0, confidence + 0.05),
                reinforcement_count = reinforcement_count + 1,
                last_reinforced = ?
            WHERE fact_id = ?
            """,
            (time.time(), fact_id),
        )

    async def list_all(self) -> list[dict[str, Any]]:
        """Return all semantic facts ordered by confidence descending."""
        rows = self._conn.execute(
            """
            SELECT * FROM semantic_memory
            ORDER BY confidence DESC, reinforcement_count DESC
            """
        ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        result["evidence_episode_ids"] = json.loads(result.get("evidence_episode_ids", "[]"))
        return result