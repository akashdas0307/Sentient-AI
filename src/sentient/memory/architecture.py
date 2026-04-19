"""Memory Architecture — four-type memory with dual storage.

Per ARCHITECTURE.md §3.3.4 sub-section 4:
  - Four types: Episodic, Semantic, Procedural, Emotional
  - Dual storage: SQLite+FTS5 (structured) + ChromaDB (semantic)
  - Six-step lifecycle: Capture → Gatekeeper → Tagging → Storage → Retrieval → Evolution
"""
from __future__ import annotations

import logging
import sqlite3
import time
import uuid
from enum import Enum
from pathlib import Path
from typing import Any

from sentient.core.event_bus import EventBus, get_event_bus
from sentient.core.module_interface import HealthPulse, ModuleInterface, ModuleStatus
from sentient.memory.gatekeeper import MemoryGatekeeper
from sentient.memory.semantic import SemanticStore
from sentient.memory.procedural import ProceduralStore

logger = logging.getLogger(__name__)


class MemoryType(Enum):
    """Four memory types per DD-005 (skills as memory type, not separate system)."""

    EPISODIC = "episodic"      # Specific events, conversations
    SEMANTIC = "semantic"      # Facts, knowledge, understanding
    PROCEDURAL = "procedural"  # Skills, learned patterns for how to do things
    EMOTIONAL = "emotional"    # Emotional associations (layer + standalone)


SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    memory_type TEXT NOT NULL,
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    importance REAL NOT NULL DEFAULT 0.5,
    confidence REAL NOT NULL DEFAULT 1.0,
    created_at REAL NOT NULL,
    last_accessed_at REAL,
    access_count INTEGER DEFAULT 0,
    reinforcement_count INTEGER DEFAULT 1,
    source_envelope_id TEXT,
    source_cycle_id TEXT,
    entity_tags TEXT DEFAULT '[]',       -- JSON array
    topic_tags TEXT DEFAULT '[]',        -- JSON array
    emotional_tags TEXT DEFAULT '{}',    -- JSON object
    metadata TEXT DEFAULT '{}',          -- JSON object
    is_archived INTEGER DEFAULT 0,
    archived_at REAL
);

CREATE INDEX IF NOT EXISTS idx_memory_type ON memories(memory_type);
CREATE INDEX IF NOT EXISTS idx_created_at ON memories(created_at);
CREATE INDEX IF NOT EXISTS idx_content_hash ON memories(content_hash);
CREATE INDEX IF NOT EXISTS idx_archived ON memories(is_archived);
CREATE INDEX IF NOT EXISTS idx_importance ON memories(importance);

CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
    id UNINDEXED,
    content,
    entity_tags,
    topic_tags,
    tokenize = 'porter'
);

CREATE TABLE IF NOT EXISTS memory_links (
    from_memory_id TEXT NOT NULL,
    to_memory_id TEXT NOT NULL,
    link_type TEXT NOT NULL,         -- 'related', 'contradicts', 'precedes', etc.
    strength REAL DEFAULT 0.5,
    created_at REAL NOT NULL,
    PRIMARY KEY (from_memory_id, to_memory_id, link_type)
);

CREATE TABLE IF NOT EXISTS contradictions (
    id TEXT PRIMARY KEY,
    memory_a_id TEXT NOT NULL,
    memory_b_id TEXT NOT NULL,
    detected_at REAL NOT NULL,
    resolved_at REAL,
    resolution TEXT,                 -- 'a_supersedes' | 'b_supersedes' | 'both_valid' | 'ambiguous'
    notes TEXT
);

CREATE TABLE IF NOT EXISTS consolidation_log (
    id TEXT PRIMARY KEY,
    consolidated_at REAL NOT NULL,
    scope TEXT NOT NULL,             -- 'daily' | 'weekly' | 'monthly' | 'quarterly'
    summary_content TEXT,
    source_memory_count INTEGER,
    coverage_start REAL,
    coverage_end REAL
);

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
);
CREATE INDEX IF NOT EXISTS idx_semantic_confidence ON semantic_memory(confidence);
CREATE INDEX IF NOT EXISTS idx_semantic_first_observed ON semantic_memory(first_observed);

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
);
CREATE INDEX IF NOT EXISTS idx_procedural_confidence ON procedural_memory(confidence);
CREATE INDEX IF NOT EXISTS idx_procedural_first_observed ON procedural_memory(first_observed);

CREATE TABLE IF NOT EXISTS world_model_calibration (
    id TEXT PRIMARY KEY,
    cycle_id TEXT NOT NULL,
    verdict_type TEXT NOT NULL,
    original_confidence REAL NOT NULL,
    adjustment REAL NOT NULL,
    new_confidence REAL NOT NULL,
    reason TEXT,
    calibrated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_wm_cal_cycle ON world_model_calibration(cycle_id);

CREATE TABLE IF NOT EXISTS identity_snapshots (
    id TEXT PRIMARY KEY,
    snapshot_data TEXT NOT NULL,
    personality_traits TEXT NOT NULL DEFAULT '{}',
    maturity_stage TEXT NOT NULL,
    self_understanding TEXT NOT NULL DEFAULT '{}',
    snapshot_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_identity_snap_at ON identity_snapshots(snapshot_at);
"""


class MemoryArchitecture(ModuleInterface):
    """Unified memory system with four types and dual storage."""

    def __init__(
        self,
        config: dict[str, Any],
        event_bus: EventBus | None = None,
    ) -> None:
        super().__init__("memory", config)
        self.event_bus = event_bus or get_event_bus()

        storage_cfg = config.get("storage", {})
        self.sqlite_path = Path(storage_cfg.get("sqlite_path", "./data/memory.db"))
        self.chroma_path = Path(storage_cfg.get("chroma_path", "./data/chroma"))

        self.gatekeeper = MemoryGatekeeper(config.get("gatekeeper", {}))

        self.retrieval_cfg = config.get("retrieval", {})
        self.default_limit = self.retrieval_cfg.get("default_max_results", 15)

        self._conn: sqlite3.Connection | None = None
        self._chroma_client = None
        self._chroma_collection = None
        self._embedder = None
        self.semantic_store: SemanticStore | None = None
        self.procedural_store: ProceduralStore | None = None

        self._write_count = 0
        self._retrieval_count = 0
        self._last_write_latency_ms: float = 0.0
        self._last_retrieval_latency_ms: float = 0.0

    # === Lifecycle ===

    async def initialize(self) -> None:
        # Ensure directories exist
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self.chroma_path.mkdir(parents=True, exist_ok=True)

        # SQLite setup
        self._conn = sqlite3.connect(
            str(self.sqlite_path),
            isolation_level=None,   # autocommit
            check_same_thread=False,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SQLITE_SCHEMA)

        # Initialize semantic and procedural stores
        self.semantic_store = SemanticStore(self._conn)
        self.procedural_store = ProceduralStore(self._conn)

        # Add consolidation_weight column to memories if it doesn't exist
        try:
            self._conn.execute(
                "ALTER TABLE memories ADD COLUMN consolidation_weight REAL DEFAULT 0.0"
            )
        except sqlite3.OperationalError:
            pass  # Column already exists

        # ChromaDB setup (lazy — may take time on first init to load embedder)
        try:
            import chromadb
            self._chroma_client = chromadb.PersistentClient(path=str(self.chroma_path))
            self._chroma_collection = self._chroma_client.get_or_create_collection(
                name="memories",
                metadata={"hnsw:space": "cosine"},
            )
        except ImportError:
            logger.warning("ChromaDB not available — semantic search disabled")

        # Embedder setup
        try:
            from sentence_transformers import SentenceTransformer
            model_name = self.config.get("embeddings", {}).get(
                "model", "all-MiniLM-L6-v2"
            )
            self._embedder = SentenceTransformer(model_name)
        except ImportError:
            logger.warning(
                "sentence-transformers not available — semantic embeddings disabled"
            )

        logger.info("Memory Architecture initialized at %s", self.sqlite_path)

    async def start(self) -> None:
        await self.event_bus.subscribe("memory.candidate", self._handle_candidate)
        self.set_status(ModuleStatus.HEALTHY)

    async def shutdown(self) -> None:
        if self._conn:
            self._conn.close()

    # === Write path ===

    async def _handle_candidate(self, payload: dict[str, Any]) -> None:
        """Receive a memory candidate from Cognitive Core reflection."""
        candidate = payload.get("candidate", {})
        source_envelope_id = payload.get("source_envelope_id")
        source_cycle_id = payload.get("cycle_id")

        if not candidate.get("content"):
            return

        # Enrich with defaults
        candidate.setdefault("created_at", time.time())
        candidate.setdefault("importance", 0.5)
        candidate.setdefault("type", MemoryType.EPISODIC.value)

        try:
            await self.store(
                candidate,
                source_envelope_id=source_envelope_id,
                source_cycle_id=source_cycle_id,
            )
        except Exception as exc:
            logger.exception("Memory storage error: %s", exc)
            self.set_status(ModuleStatus.ERROR, str(exc))

    async def store(
        self,
        candidate: dict[str, Any],
        source_envelope_id: str | None = None,
        source_cycle_id: str | None = None,
    ) -> str | None:
        """Run a candidate through the full write pipeline. Returns memory_id or None."""
        start = time.time()

        # Check existing by hash for exact dedup
        content = candidate.get("content", "")
        content_hash = self.gatekeeper._hash_content(content)
        existing_by_hash = {}
        if self._conn:
            cursor = self._conn.execute(
                "SELECT id, content FROM memories WHERE content_hash = ?",
                (content_hash,),
            )
            for row in cursor:
                existing_by_hash[content_hash] = {"id": row["id"], "content": row["content"]}

        # Get semantically similar for dedup + contradiction detection
        similar_memories = []
        if self._chroma_collection and self._embedder:
            try:
                embedding = self._embedder.encode(content).tolist()
                results = self._chroma_collection.query(
                    query_embeddings=[embedding],
                    n_results=5,
                )
                if results.get("ids") and results["ids"][0]:
                    for idx, mem_id in enumerate(results["ids"][0]):
                        similar_memories.append({
                            "id": mem_id,
                            "similarity": 1.0 - results["distances"][0][idx],
                            "processed_content": results["documents"][0][idx],
                        })
            except Exception as exc:
                logger.warning("Semantic similarity check failed: %s", exc)

        # Gatekeeper decision — use lower importance threshold for daydream-origin memories
        original_threshold = None
        metadata = candidate.get("metadata", {})
        if metadata.get("origin") == "daydream":
            daydream_threshold = self.gatekeeper.importance_threshold  # default 0.3
            # Use 0.2 or the configured daydream_min_importance
            config_threshold = self.config.get("daydream_min_importance", 0.2)
            original_threshold = self.gatekeeper.importance_threshold
            self.gatekeeper.importance_threshold = min(daydream_threshold, config_threshold)

        decision = self.gatekeeper.evaluate(
            candidate,
            existing_by_hash=existing_by_hash,
            similar_memories=similar_memories,
        )

        # Restore original threshold
        if original_threshold is not None:
            self.gatekeeper.importance_threshold = original_threshold

        if decision.action == "skip":
            logger.debug("Gatekeeper skipped memory: %s", decision.reason)
            return None

        if decision.action == "reinforce":
            await self._reinforce(decision.target_memory_id)
            return decision.target_memory_id

        if decision.action == "update":
            return await self._update_existing(
                decision.target_memory_id, candidate,
            )

        if decision.action == "flag_contradiction":
            await self._record_contradiction(
                candidate, decision.target_memory_id, decision.metadata,
            )
            # Still store the new memory — contradiction resolves during sleep
            # fall through to store

        # Store new memory
        memory_id = str(uuid.uuid4())
        await self._store_new(
            memory_id=memory_id,
            candidate=candidate,
            source_envelope_id=source_envelope_id,
            source_cycle_id=source_cycle_id,
            content_hash=content_hash,
        )

        self._write_count += 1
        self._last_write_latency_ms = (time.time() - start) * 1000

        await self.event_bus.publish(
            "memory.stored",
            {
                "memory_id": memory_id,
                "memory_type": candidate.get("type"),
                "importance": candidate.get("importance"),
            },
        )
        return memory_id

    async def _store_new(
        self,
        memory_id: str,
        candidate: dict[str, Any],
        source_envelope_id: str | None,
        source_cycle_id: str | None,
        content_hash: str,
    ) -> None:
        """Insert into SQLite and ChromaDB."""
        import json

        content = candidate.get("content", "")
        memory_type = candidate.get("type", MemoryType.EPISODIC.value)
        importance = float(candidate.get("importance", 0.5))
        confidence = float(candidate.get("confidence", 1.0))
        created_at = candidate.get("created_at", time.time())
        entity_tags = candidate.get("entity_tags", [])
        topic_tags = candidate.get("topic_tags", [])
        emotional_tags = candidate.get("emotional_tags", {})

        # SQLite insert
        if self._conn:
            self._conn.execute(
                """
                INSERT INTO memories (
                    id, memory_type, content, content_hash, importance, confidence,
                    created_at, source_envelope_id, source_cycle_id,
                    entity_tags, topic_tags, emotional_tags, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    memory_id, memory_type, content, content_hash, importance, confidence,
                    created_at, source_envelope_id, source_cycle_id,
                    json.dumps(entity_tags), json.dumps(topic_tags),
                    json.dumps(emotional_tags), json.dumps(candidate.get("metadata", {})),
                ),
            )
            # FTS index
            self._conn.execute(
                """
                INSERT INTO memories_fts (id, content, entity_tags, topic_tags)
                VALUES (?, ?, ?, ?)
                """,
                (memory_id, content, " ".join(entity_tags), " ".join(topic_tags)),
            )

        # ChromaDB insert (semantic)
        if self._chroma_collection and self._embedder:
            try:
                embedding = self._embedder.encode(content).tolist()
                self._chroma_collection.add(
                    ids=[memory_id],
                    embeddings=[embedding],
                    documents=[content],
                    metadatas=[{
                        "memory_type": memory_type,
                        "importance": importance,
                        "created_at": created_at,
                    }],
                )
            except Exception as exc:
                logger.warning("ChromaDB insert failed: %s", exc)

    async def _reinforce(self, memory_id: str) -> None:
        """Increment reinforcement count and importance for repeated memory."""
        if not self._conn:
            return
        self._conn.execute(
            """
            UPDATE memories
            SET reinforcement_count = reinforcement_count + 1,
                importance = MIN(1.0, importance + 0.05),
                last_accessed_at = ?
            WHERE id = ?
            """,
            (time.time(), memory_id),
        )

    async def _update_existing(
        self,
        memory_id: str,
        new_candidate: dict[str, Any],
    ) -> str:
        """Update existing memory with new information (semantic match)."""
        # MVS: simple reinforcement. Phase 2+ merges content via sleep consolidation.
        await self._reinforce(memory_id)
        return memory_id

    async def _record_contradiction(
        self,
        candidate: dict[str, Any],
        existing_id: str,
        metadata: dict[str, Any],
    ) -> None:
        """Log a contradiction for sleep-time resolution."""
        if not self._conn:
            return
        self._conn.execute(
            """
            INSERT INTO contradictions (id, memory_a_id, memory_b_id, detected_at)
            VALUES (?, ?, ?, ?)
            """,
            (str(uuid.uuid4()), metadata.get("contradicts", existing_id),
             "pending_new", time.time()),
        )

    # === Retrieval ===

    async def retrieve(
        self,
        query: str = "",
        tags: list[str] | None = None,
        memory_types: list[MemoryType] | None = None,
        limit: int | None = None,
        include_archived: bool = False,
    ) -> list[dict[str, Any]]:
        """Multi-path retrieval combining tag-based and semantic search.

        Returns list of memory dicts with similarity/relevance scores.
        """
        import json
        start = time.time()
        limit = limit or self.default_limit

        results_by_id: dict[str, dict] = {}

        # Path 1: Tag-based search via SQLite FTS
        if self._conn and (tags or query):
            fts_query_parts = []
            if query:
                # Escape FTS special chars; simple approach
                escaped = query.replace('"', '""')
                fts_query_parts.append(f'"{escaped}"')
            if tags:
                fts_query_parts.extend(tags)
            fts_query = " OR ".join(fts_query_parts) if fts_query_parts else None

            if fts_query:
                try:
                    rows = self._conn.execute(
                        """
                        SELECT m.* FROM memories m
                        JOIN memories_fts f ON m.id = f.id
                        WHERE memories_fts MATCH ?
                          AND (? = 1 OR m.is_archived = 0)
                        ORDER BY m.importance DESC, m.created_at DESC
                        LIMIT ?
                        """,
                        (fts_query, 1 if include_archived else 0, limit),
                    ).fetchall()
                    for row in rows:
                        memory = dict(row)
                        memory["entity_tags"] = json.loads(memory.get("entity_tags", "[]"))
                        memory["topic_tags"] = json.loads(memory.get("topic_tags", "[]"))
                        memory["emotional_tags"] = json.loads(memory.get("emotional_tags", "{}"))
                        memory["processed_content"] = memory["content"]
                        memory["retrieval_path"] = "tag"
                        results_by_id[memory["id"]] = memory
                except sqlite3.OperationalError as exc:
                    logger.warning("FTS query error: %s", exc)

        # Path 2: Semantic search via ChromaDB
        if self._chroma_collection and self._embedder and query:
            try:
                embedding = self._embedder.encode(query).tolist()
                chroma_results = self._chroma_collection.query(
                    query_embeddings=[embedding],
                    n_results=limit,
                )
                if chroma_results.get("ids") and chroma_results["ids"][0]:
                    for idx, mem_id in enumerate(chroma_results["ids"][0]):
                        if mem_id in results_by_id:
                            results_by_id[mem_id]["similarity"] = (
                                1.0 - chroma_results["distances"][0][idx]
                            )
                            results_by_id[mem_id]["retrieval_path"] = "both"
                        else:
                            # Fetch full record from SQLite
                            row = self._conn.execute(
                                "SELECT * FROM memories WHERE id = ?", (mem_id,),
                            ).fetchone() if self._conn else None
                            if row:
                                memory = dict(row)
                                memory["entity_tags"] = json.loads(
                                    memory.get("entity_tags", "[]")
                                )
                                memory["topic_tags"] = json.loads(
                                    memory.get("topic_tags", "[]")
                                )
                                memory["emotional_tags"] = json.loads(
                                    memory.get("emotional_tags", "{}")
                                )
                                memory["processed_content"] = memory["content"]
                                memory["similarity"] = (
                                    1.0 - chroma_results["distances"][0][idx]
                                )
                                memory["retrieval_path"] = "semantic"
                                results_by_id[mem_id] = memory
            except Exception as exc:
                logger.warning("Chroma query failed: %s", exc)

        # Update access counts (background effect — reinforcement)
        if self._conn and results_by_id:
            ids_tuple = list(results_by_id.keys())
            placeholders = ",".join("?" * len(ids_tuple))
            self._conn.execute(
                f"""
                UPDATE memories
                SET access_count = access_count + 1,
                    last_accessed_at = ?
                WHERE id IN ({placeholders})
                """,
                [time.time(), *ids_tuple],
            )

        # Rank combined results
        results = list(results_by_id.values())
        results.sort(
            key=lambda m: (
                m.get("similarity", 0) * 0.5
                + float(m.get("importance", 0)) * 0.3
                + (1.0 / (1.0 + (time.time() - m.get("created_at", 0)) / 86400)) * 0.2
            ),
            reverse=True,
        )

        self._retrieval_count += 1
        self._last_retrieval_latency_ms = (time.time() - start) * 1000
        return results[:limit]

    async def retrieve_episodic(
        self,
        context: str,
        k: int = 3,
    ) -> list[dict[str, Any]]:
        """Retrieve top-k episodic memories semantically related to context.

        Convenience wrapper for retrieve() with episodic filter.
        Returns empty list if memory subsystem is unavailable.
        """
        try:
            return await self.retrieve(
                query=context,
                memory_types=[MemoryType.EPISODIC],
                limit=k,
            )
        except Exception as exc:
            logger.warning("Episodic retrieval failed: %s", exc)
            return []

    async def retrieve_semantic(self, query: str, k: int = 3) -> list[dict[str, Any]]:
        """Retrieve top-k semantic facts matching query. Returns empty list if unavailable."""
        if self.semantic_store is None:
            return []
        try:
            return await self.semantic_store.retrieve(query, k)
        except Exception as exc:
            logger.warning("Semantic retrieval failed: %s", exc)
            return []

    async def retrieve_procedural(self, context: str, k: int = 3) -> list[dict[str, Any]]:
        """Retrieve top-k procedural patterns matching context. Returns empty list if unavailable."""
        if self.procedural_store is None:
            return []
        try:
            return await self.procedural_store.retrieve(context, k)
        except Exception as exc:
            logger.warning("Procedural retrieval failed: %s", exc)
            return []

    async def count(self, memory_type: MemoryType | None = None) -> int:
        """Count stored memories."""
        if not self._conn:
            return 0
        if memory_type:
            row = self._conn.execute(
                "SELECT COUNT(*) as c FROM memories WHERE memory_type = ? AND is_archived = 0",
                (memory_type.value,),
            ).fetchone()
        else:
            row = self._conn.execute(
                "SELECT COUNT(*) as c FROM memories WHERE is_archived = 0",
            ).fetchone()
        return row["c"] if row else 0

    async def has_daydreamed_recently(self, hours: float = 1.0) -> bool:
        """Check if any daydream-origin memories exist within the given time window.

        Args:
            hours: Time window in hours (default 1.0). Memories older than this
                window are not considered.

        Returns:
            True if at least one episodic memory with origin="daydream" exists
            within the time window; False otherwise.
        """
        if not self._conn:
            return False
        cutoff = time.time() - (hours * 3600)
        try:
            # Use json_extract on the metadata column to find origin="daydream"
            row = self._conn.execute(
                """
                SELECT 1 FROM memories
                WHERE memory_type = ?
                  AND created_at >= ?
                  AND is_archived = 0
                  AND json_extract(metadata, '$.origin') = 'daydream'
                LIMIT 1
                """,
                (MemoryType.EPISODIC.value, cutoff),
            ).fetchone()
            return row is not None
        except Exception as exc:
            logger.warning("has_daydreamed_recently check failed: %s", exc)
            return False

    def health_pulse(self) -> HealthPulse:
        total = 0
        counts_by_type: dict[str, int] = {}
        if self._conn:
            try:
                for mtype in MemoryType:
                    row = self._conn.execute(
                        "SELECT COUNT(*) as c FROM memories WHERE memory_type = ? AND is_archived = 0",
                        (mtype.value,),
                    ).fetchone()
                    counts_by_type[mtype.value] = row["c"] if row else 0
                    total += counts_by_type[mtype.value]
            except Exception:
                pass

        return HealthPulse(
            module_name=self.name,
            status=self._last_health_status,
            metrics={
                "total_memories": total,
                "by_type": counts_by_type,
                "write_count": self._write_count,
                "retrieval_count": self._retrieval_count,
                "last_write_ms": round(self._last_write_latency_ms, 2),
                "last_retrieval_ms": round(self._last_retrieval_latency_ms, 2),
                "sqlite_available": self._conn is not None,
                "chroma_available": self._chroma_collection is not None,
            },
        )
