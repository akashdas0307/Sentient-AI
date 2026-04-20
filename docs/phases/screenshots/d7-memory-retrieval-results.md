# D7 Memory Retrieval Test Results

**Date**: 2026-04-20
**Server**: http://localhost:8765 (running)
**Test DB**: ./data/test_memory.db + ./data/test_chroma (isolated test instances)
**Production DB**: ./data/memory.db (used for API endpoint tests)

## Source Code Summary

The memory system uses:
- **Class**: `MemoryArchitecture` (not `MemoryManager` -- that path does not exist)
- **Location**: `src/sentient/memory/architecture.py`
- **Supporting modules**: `gatekeeper.py`, `semantic.py`, `procedural.py`
- **Storage**: SQLite + FTS5 (structured/keyword) + ChromaDB (semantic vector)
- **Embedder**: sentence-transformers/all-MiniLM-L6-v2
- **Four memory types**: Episodic, Semantic, Procedural, Emotional (`MemoryType` enum)
- **API**: `store(candidate)` takes a dict with keys `content`, `type`, `importance`, etc.
- **API**: `retrieve(query, tags, memory_types, limit)` returns list of memory dicts

---

## Test 1: Memory Storage

**Input**: Store 4 memories of different types (episodic, semantic, procedural, emotional)

**Output**:
```
Episodic store: a1668259-c151-4076-b4d8-44cdc6fa933d
Semantic store: 24a1b877-6bb2-4610-9c99-769ab215966f
Procedural store: 2ec5a605-7f72-4514-ae90-e0d8b50c035d
Emotional store: 1ae53d7d-6e41-406f-935b-ffdb461e45f0
Total: 4, Episodic: 1, Semantic: 1, Procedural: 1, Emotional: 1
```

**Result**: PASS -- All four memory types stored successfully, returning UUID identifiers. `count()` confirms correct per-type totals.

---

## Test 2: Memory Retrieval

**Input**: Semantic search for "programming languages", "test session with user", "how to start server", and "Python"

**Output**:
```
Semantic search "programming languages": 4 results
  - [semantic] Python is an interpreted... (path: both, similarity: 0.58)
  - [procedural] To start the server... (path: semantic, similarity: 0.17)
  - [episodic] User asked about the capital... (path: semantic, similarity: 0.04)
  - [emotional] Felt frustration... (path: semantic, similarity: 0.01)

Episodic search "test session with user": 4 results
  - [episodic] User asked about the capital of France...
  - [procedural] To start the server...
  - [semantic] Python is an interpreted...
  - [emotional] Felt frustration...

Procedural search "how to start server": 4 results
  - [procedural] To start the server...
  - [emotional] Felt frustration...
  - [episodic] User asked about the capital...
  - [semantic] Python is an interpreted...

Cross-type search "Python": 4 results
  Types found: {semantic: 1, procedural: 1, episodic: 1, emotional: 1}
```

**Result**: PASS -- Multi-path retrieval works. Top result correctly matches the query semantically. Retrieval path metadata ("tag", "semantic", "both") is populated. Similarity scores decrease appropriately for less relevant results. Cross-type search returns all types.

**Observation**: The "programming languages" query correctly ranks the semantic memory about Python highest (similarity 0.58). The "test session with user" query correctly ranks the episodic memory first. Small DB means all results return for every query, but ranking is correct.

---

## Test 3: Memory Filtering by Type

**Input**: Use `memory_types` parameter to filter by type; also test convenience wrappers `retrieve_episodic()`, `retrieve_semantic()`, `retrieve_procedural()`

**Output**:
```
Episodic only (memory_types=[EPISODIC]): 4 results
  Types returned: [episodic, semantic, emotional, procedural] -- ALL types returned

Semantic only (memory_types=[SEMANTIC]): 4 results
  Types returned: [episodic, semantic, emotional, procedural] -- ALL types returned

Procedural only (memory_types=[PROCEDURAL]): 4 results
  Types returned: [procedural, semantic, emotional, episodic] -- ALL types returned

retrieve_episodic convenience: 3 results
  Types returned: [episodic, procedural, emotional] -- NOT filtered to episodic only

retrieve_semantic convenience: 0 results
retrieve_procedural convenience: 0 results
```

**Result**: FAIL -- The `memory_types` parameter is accepted by `retrieve()` but is **never applied** in the query logic. The FTS and ChromaDB queries do not include a `WHERE memory_type IN (...)` clause. All types are returned regardless of filter.

**Additional finding**: `retrieve_episodic()` convenience wrapper also returns unfiltered results. `retrieve_semantic()` and `retrieve_procedural()` query their separate tables (`semantic_memory`, `procedural_memory`), which are empty because they are only populated during sleep consolidation -- not by direct `store()` calls.

**Bug severity**: Medium -- API contract violation. The parameter is accepted and silently ignored.

---

## Test 4: Memory Importance and Novelty

**Input**: Low-importance (0.1), high-importance (0.95), near-duplicate, and exact-duplicate stores

**Output**:
```
Low-importance store (importance=0.1, threshold=0.3): cdac0799-f1ac-4042-be80-93309ffdfbf9
High-importance store (importance=0.95): 9393701e-463f-45ea-a0db-6362b62212f9
Near-duplicate store: 8961fd59-dd1d-4907-82d8-fd13cb10b7fd
Exact duplicate store: 24a1b877-6bb2-4610-9c99-769ab215966f (same ID as original)
After novelty tests: Total=7, Episodic=3, Semantic=2
```

**Result**: PARTIAL PASS

- **Exact dedup**: PASS -- Exact duplicate returned the original memory ID (reinforce action, not new insert).
- **High importance**: PASS -- Stored successfully.
- **Low importance (0.1)**: Stored despite being below the 0.3 threshold. This is correct behavior due to **recency auto-pass**: memories created within the last 24 hours bypass the importance threshold. Confirmed by testing the gatekeeper directly:
  - Recent low-importance (age < 24h): action=store
  - Old low-importance (age > 24h): action=skip, reason="importance 0.10 below threshold 0.3"
- **Near-duplicate**: Stored as a new memory (new UUID). The semantic similarity was below the dedup threshold (0.92), so it was not caught as a duplicate. This is correct for the MVS; the threshold would need tuning for production use.

**Gatekeeper defaults**:
- `importance_threshold`: 0.3
- `semantic_dedup_similarity`: 0.92
- `recency_auto_pass_hours`: 24

---

## Test 5: Memory API Endpoints (Live Server)

### /api/memory/count
**Output**:
```json
{
    "total_memories": 72,
    "by_type": {
        "episodic": 39,
        "semantic": 19,
        "procedural": 2,
        "emotional": 12
    },
    "write_count": 14,
    "retrieval_count": 12,
    "last_write_ms": 41.68,
    "last_retrieval_ms": 0.01,
    "sqlite_available": true,
    "chroma_available": true
}
```

**Result**: PASS -- Returns health pulse metrics from the production DB. 72 memories across 4 types. Both SQLite and ChromaDB available.

### /api/memory/search?q=Python&limit=5
**Output**: Returned 5 entries from production DB with full memory records including `similarity` scores and `retrieval_path` metadata. Top result was a semantic memory about capabilities (similarity 0.15).

**Result**: PASS -- Search endpoint works. Returns entries with proper structure.

---

## Test 6: Endpoint Discovery

| Endpoint | Status | Response |
|----------|--------|----------|
| `/api/memory/count` | EXISTS | JSON with memory stats (health pulse metrics) |
| `/api/memory/search?q=...` | EXISTS | JSON with `entries` array |
| `/api/memory/recent` | EXISTS | Returns `{"entries": []}` (empty for empty query) |
| `/api/memory/graph` | EXISTS | Returns `{"nodes": [...], "links": [...]}` (76 nodes, 0 links in prod DB) |
| `/api/memory/stats` | DOES NOT EXIST | Falls through to SPA fallback (returns HTML) |
| `/api/memories` | DOES NOT EXIST | Falls through to SPA fallback (returns HTML) |
| `/api/memory` | DOES NOT EXIST | Falls through to SPA fallback (returns HTML) |

**Result**: 4 valid memory API endpoints found: `count`, `search`, `recent`, `graph`.

---

## Summary Table

| Test | Status | Notes |
|------|--------|-------|
| T1: Memory Storage | PASS | All 4 types stored, count() correct |
| T2: Memory Retrieval | PASS | Multi-path retrieval works, ranking correct |
| T3: Type Filtering | FAIL | `memory_types` param accepted but not applied in SQL -- bug |
| T4: Importance/Novelty | PARTIAL | Exact dedup works, recency auto-pass works, near-duplicate not caught (threshold appropriate) |
| T5a: /api/memory/count | PASS | Returns live production stats |
| T5b: /api/memory/search | PASS | Returns entries with similarity scores |
| T6: Endpoint Discovery | PASS | 4 endpoints exist, 3 probed do not |

---

## Bugs Found

1. **`memory_types` filter not applied** (architecture.py, `retrieve()` method): The `memory_types` parameter is accepted but the FTS and ChromaDB query paths do not include a `WHERE memory_type IN (...)` filter clause. All memory types are returned regardless. This affects both the direct `retrieve()` call and the `retrieve_episodic()` convenience wrapper.

2. **`/api/memory/recent` returns empty for empty query**: The endpoint calls `retrieve(query="", limit=...)` which only triggers the ChromaDB path (FTS requires a non-empty query). If ChromaDB returns nothing matching an empty embedding, the result is empty. This may be expected behavior but is unintuitive -- "recent" should return the most recent N memories by timestamp.

3. **Memory graph has 0 links**: The `memory_links` table in production has no entries. Links are never created during the store path. This may be intentional (links created during sleep consolidation), but the graph endpoint returns a disconnected set of nodes.

4. **`retrieve_semantic()` and `retrieve_procedural()` return empty**: These convenience methods query the separate `semantic_memory` and `procedural_memory` tables, which are only populated during sleep consolidation -- not by direct `store()` calls. Direct stores go to the `memories` table only. This is correct per the architecture but may confuse API consumers.