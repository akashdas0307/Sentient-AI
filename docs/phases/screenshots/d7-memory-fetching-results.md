# D7: On-Demand Memory Fetching Test Results

**Date**: 2026-04-20
**Branch**: `auto/phase-10-aliveness-audit`
**Server**: http://localhost:8765 (running)

---

## 1. How Memories Are Stored

### Schema (SQLite + ChromaDB dual storage)

Each memory record in SQLite contains:

| Field | Type | Purpose |
|-------|------|---------|
| `id` | TEXT (UUID) | Primary key |
| `memory_type` | TEXT | One of: episodic, semantic, procedural, emotional |
| `content` | TEXT | The memory text |
| `content_hash` | TEXT | SHA-256 of content for exact dedup |
| `importance` | REAL | 0.0-1.0, gatekeeper threshold |
| `confidence` | REAL | 0.0-1.0 |
| `created_at` | REAL | Unix timestamp |
| `last_accessed_at` | REAL | Updated on retrieval (reinforcement) |
| `access_count` | INTEGER | Incremented on retrieval |
| `reinforcement_count` | INTEGER | Incremented on reinforcement |
| `source_envelope_id` | TEXT | Link to originating envelope |
| `source_cycle_id` | TEXT | Link to originating cognitive cycle |
| `entity_tags` | TEXT (JSON array) | Named entities extracted |
| `topic_tags` | TEXT (JSON array) | Topic categories |
| `emotional_tags` | TEXT (JSON object) | Emotional valence markers |
| `metadata` | TEXT (JSON object) | Extensible metadata (e.g., origin="daydream") |
| `is_archived` | INTEGER | Soft delete flag |
| `consolidation_weight` | REAL | Sleep consolidation weight |

Additional tables: `memory_links` (inter-memory relationships), `contradictions` (detected contradictions), `consolidation_log` (sleep consolidation records), `semantic_memory` (extracted facts), `procedural_memory` (learned patterns).

ChromaDB stores: `id`, `embedding` (all-MiniLM-L6-v2), `document` (content), `metadata` (type, importance, created_at).

### Storage Flow

1. Cognitive Core produces `memory_candidates` in its reflection output
2. Event `memory.candidate` is published with the candidate dict
3. `MemoryArchitecture._handle_candidate()` receives the event
4. Content is hashed for exact dedup check
5. Embedding similarity search finds semantically similar existing memories
6. `MemoryGatekeeper.evaluate()` makes a deterministic decision (no LLM)
7. Result: `store` (new), `reinforce` (exact dedup), `update` (semantic dedup), `flag_contradiction`, or `skip` (below threshold)
8. On `store`: inserted into both SQLite (with FTS5 index) and ChromaDB
9. Event `memory.stored` is published with the new memory_id

---

## 2. How Memories Are Retrieved

### Three retrieval paths (combined in `MemoryArchitecture.retrieve()`)

**Path 1: Tag-based / FTS5 full-text search (SQLite)**
- Uses `memories_fts` virtual table with Porter tokenizer
- Supports query text and tag-based search
- Results ranked by `importance DESC, created_at DESC`
- Fallback: gracefully handles query parse errors

**Path 2: Semantic similarity search (ChromaDB)**
- Uses `all-MiniLM-L6-v2` sentence-transformer embeddings
- Cosine similarity in HuggingFace space
- Returns top-k results with similarity scores
- Falls back gracefully if ChromaDB unavailable

**Path 3: Combined scoring**
- When both paths return results for the same memory, it gets `retrieval_path: "both"`
- Final ranking uses weighted formula: `similarity * 0.5 + importance * 0.3 + recency * 0.2`
- Access counts are incremented for all returned memories (reinforcement on read)

### Specialized retrieval methods

| Method | Scope | Notes |
|--------|-------|-------|
| `retrieve(query, tags, memory_types, limit)` | All types | Primary multi-path method |
| `retrieve_episodic(context, k)` | Episodic only | Convenience wrapper |
| `retrieve_semantic(query, k)` | Semantic facts | Uses `SemanticStore` (separate SQLite table) |
| `retrieve_procedural(context, k)` | Procedural patterns | Uses `ProceduralStore` (separate SQLite table) |
| `count(memory_type)` | Count | Filtered or total memory count |

### Test Results

| Query | Results | Path |
|-------|---------|------|
| `retrieve(query='test', limit=5)` | 5 results | semantic |
| `retrieve(query='What is the server status?', limit=3)` | 3 results | semantic |
| `retrieve(query='How does memory work?', limit=3)` | 3 results | mixed |
| `retrieve(query='User preferences', limit=3)` | 3 results | semantic |
| `retrieve(query='Error logs', limit=3)` | 3 results | mixed |
| `retrieve(query='', limit=5)` | **0 results** | **BUG: empty query returns nothing** |
| `retrieve(tags=['Akash'], limit=5)` | 1 result | tag |
| `retrieve_episodic('conversation about AI', k=3)` | 3 results | episodic |
| `retrieve_semantic('AI framework', k=3)` | 0 results | SemanticStore separate table |
| `retrieve_procedural('how to respond', k=3)` | 0 results | ProceduralStore separate table |

**Not available**: `retrieve_by_id`, `get_recent`, `retrieve_by_time_range` -- these methods do not exist on `MemoryArchitecture`.

---

## 3. How Memory Context Is Injected into Cognitive Cycles

### Automatic injection (on every user input)

The `CognitiveCore._assemble_prompt()` method automatically retrieves and injects memory context into the reasoning prompt:

1. **Episodic memory block** (`RECENT EPISODIC MEMORY`):
   - Triggers when `self.memory` is available and `self.episodic_memory_enabled` is True
   - Skipped during daydreams
   - Uses `self.memory.retrieve_episodic(input_text, k=3)` with the envelope's `processed_content`
   - Shows up to 3 memories with importance scores

2. **Consolidated knowledge block** (`CONSOLIDATED KNOWLEDGE`):
   - Triggers when `self.memory` and `self.semantic_memory_enabled` are True
   - Skipped during daydreams
   - Uses `self.memory.retrieve_semantic(input_text, k=3)`
   - Shows semantic facts with confidence scores

3. **Behavioral patterns block** (`BEHAVIORAL PATTERNS`):
   - Triggers when `self.memory` and `self.procedural_memory_enabled` are True
   - Skipped during daydreams
   - Uses `self.memory.retrieve_procedural(context_text, k=3)`
   - Shows patterns with confidence and trigger context

4. **Input block** (`RELATED MEMORIES`):
   - TLP enrichment includes `related_memories` from the `EnrichedContext`
   - These are retrieved by TLP's `_enrich()` method using `self.memory.retrieve(query=..., tags=..., limit=...)`

### On-demand vs Automatic

**Current design is fully automatic** -- there is no mechanism for the Cognitive Core to request additional memory retrieval mid-cycle. Memory retrieval happens in two places:

1. **TLP stage** (before cognitive processing): Broad retrieval based on input content + tags
2. **Prompt assembly** (inside cognitive core): Type-specific retrieval (episodic, semantic, procedural)

The Cognitive Core cannot say "I need more memories about X" during a cycle. The LLM output includes `memory_candidates` in its `reflection` field, but these are write-only (storage candidates, not retrieval requests).

---

## 4. API Endpoints Exposing Memory

| Endpoint | Method | Status | Notes |
|----------|--------|--------|-------|
| `/api/memory/count` | GET | Working | Returns total counts by type, write/retrieval stats, SQLite/ChromaDB availability |
| `/api/memory/search?q=...&limit=...` | GET | Working | Calls `memory.retrieve(query=q, limit=limit)`, returns entries |
| `/api/memory/recent?limit=...` | GET | **Buggy** | Calls `memory.retrieve(query="", limit=...)` which returns empty -- needs a time-based query |
| `/api/memory/graph` | GET | Working | Returns all nodes and links for visualization. Currently 90 nodes, 0 links |
| `/api/cognitive/recent` | GET | Working | Returns cognitive core metrics (cycle count, daydream count, idle seconds) |

**Not exposed via API**: store, delete, retrieve_by_id, retrieve_by_time_range, semantic/procedural-specific queries, contradiction listing.

---

## 5. Gaps Identified

### Gap 1: No on-demand memory retrieval during cognitive cycles
The Cognitive Core has no mechanism to request additional memories mid-reasoning. If the LLM determines it needs more context about a specific topic, there is no feedback loop to retrieve more. The `reflection.memory_candidates` field is write-only.

**Impact**: The agent cannot do "deep dive" retrieval when it realizes its initial context is insufficient.

### Gap 2: `/api/memory/recent` endpoint returns empty
The endpoint calls `memory.retrieve(query="", limit=...)`, but the `retrieve()` method skips both FTS (empty query) and ChromaDB (empty query) paths, returning zero results. A time-based query (`ORDER BY created_at DESC LIMIT N`) would be more appropriate.

### Gap 3: Missing retrieval methods
`retrieve_by_id`, `get_recent`, and `retrieve_by_time_range` do not exist. These would be needed for:
- Looking up specific memories by ID (referenced in links or contradictions)
- Getting recent context without a semantic query
- Time-range queries for "what happened in the last hour"

### Gap 4: Memory links are never created
The `memory_links` table exists in the schema but no code writes to it. The graph API returns 0 links despite having 90 nodes. Inter-memory relationships are not being established.

### Gap 5: Daydream memories use a lower gatekeeper threshold
Daydream-origin memories bypass the importance threshold (using `min(default_threshold, daydream_min_importance)` where daydream_min_importance defaults to 0.2). This means low-importance idle thoughts get stored, which could fill the memory with noise.

### Gap 6: No semantic search on the SemanticStore and ProceduralStore
Both `SemanticStore.retrieve()` and `ProceduralStore.retrieve()` use FTS5 or LIKE fallback, not embedding-based semantic search. They are separate from the main ChromaDB collection.

---

## 6. How the Gatekeeper Works

The `MemoryGatekeeper` is a deterministic, zero-LLM filter on the write path. It evaluates each candidate through 5 steps:

### Step 1: Recency auto-pass
- If `age_hours < recency_auto_pass_hours` (default 24h), skip the importance threshold check
- Very recent memories are always stored (they might become important later)

### Step 2: Importance threshold
- If `importance < importance_threshold` (default 0.3), the candidate is **skipped**
- Daydream memories get a lower threshold (0.2 by default)

### Step 3: Exact deduplication (content hash)
- SHA-256 of `content.strip().lower()` is computed
- If hash matches an existing memory, action = **reinforce** (increment importance by 0.05, access count)

### Step 4: Semantic deduplication (embedding similarity)
- If any existing memory has cosine similarity >= `semantic_dedup_similarity` (default 0.92), action = **update** (reinforce existing)

### Step 5: Contradiction detection
- If similarity is between 0.6 and 0.92, and one content has negation words while the other does not, action = **flag_contradiction**
- Contradiction is logged for sleep-time resolution, but the new memory is still stored

### Gatekeeper Test Results

| Scenario | Action | Reason |
|----------|--------|--------|
| importance=0.1 (below threshold) | skip | "importance 0.10 below threshold 0.3" |
| Exact content duplicate | reinforce | "exact content match -- reinforcing existing memory" |
| Semantic similarity >= 0.92 | update | "semantic match (0.95) -- updating existing" |
| Negation contradiction (0.6-0.92 similarity) | flag_contradiction | "possible contradiction with existing memory" |
| Normal new memory (low similarity) | store | "passes all gatekeeper filters" |
| Low importance but recent (< 24h) | store | "passes all gatekeeper filters" (auto-pass) |

---

## Test Summary

| Test | Result |
|------|--------|
| API: `/api/memory/count` | PASS - returns correct counts (93 total, by type) |
| API: `/api/memory/search?q=...` | PASS - returns matching results with similarity scores |
| API: `/api/memory/recent` | FAIL - returns empty (bug: empty query) |
| API: `/api/memory/graph` | PASS - returns 90 nodes, 0 links |
| API: `/api/cognitive/recent` | PASS - returns cycle metrics |
| Direct: `store()` | PASS - stored test memory, got UUID back |
| Direct: `retrieve()` with queries | PASS - returns ranked results |
| Direct: `retrieve_episodic()` | PASS - returns episodic memories |
| Direct: `retrieve_semantic()` | PASS - returns 0 (no facts in separate table yet) |
| Direct: `retrieve_procedural()` | PASS - returns 0 (no patterns in separate table yet) |
| Direct: `retrieve(query="")` | FAIL - returns 0 results (no fallback for empty query) |
| Direct: `retrieve_by_id()` | N/A - method does not exist |
| Direct: `get_recent()` | N/A - method does not exist |
| Direct: `retrieve_by_time_range()` | N/A - method does not exist |
| Gatekeeper: below threshold | PASS - correctly skips |
| Gatekeeper: exact dedup | PASS - correctly reinforces |
| Gatekeeper: semantic dedup | PASS - correctly updates |
| Gatekeeper: contradiction | PASS - correctly flags |
| Gatekeeper: normal store | PASS - correctly stores |
| Gatekeeper: recency auto-pass | PASS - correctly bypasses threshold |
| Chat: memory-injected query | PARTIAL - turn submitted but response not captured (async processing, turn TTL expired) |

---

## Architecture Summary

```
User Input
    |
    v
Thalamus (input plugin)
    |
    v
Event: input.delivered
    |
    v
TLP (Temporal-Limbic-Processor)
    |-- Operation 1: memory.retrieve(query=input_content, tags=...)
    |-- Operation 2: Build EnrichedContext (situation_summary, related_memories, significance, timeline)
    |-- Operation 3: Significance weighting (emotional/motivational/learning/urgency)
    |
    v
Event: tlp.enriched
    |
    v
Cognitive Core
    |-- _assemble_prompt():
    |     |-- IDENTITY block (from PersonaManager)
    |     |-- CURRENT STATE block
    |     |-- INPUT block (with related_memories from TLP)
    |     |-- RECENT EPISODIC MEMORY block (retrieve_episodic, k=3)
    |     |-- CONSOLIDATED KNOWLEDGE block (retrieve_semantic, k=3)
    |     |-- BEHAVIORAL PATTERNS block (retrieve_procedural, k=3)
    |     |-- INSTRUCTION block
    |
    v
LLM Inference (structured JSON output)
    |
    v
Decision.proposed events -> World Model -> Brainstem
    |
    v
memory.candidate events -> Gatekeeper -> Memory Store (or skip/reinforce/update)
```

**Key insight**: Memory is injected at two points -- TLP does broad retrieval before cognitive processing, and Cognitive Core does type-specific retrieval during prompt assembly. Both are automatic and pre-computed. There is no on-demand retrieval during the cognitive cycle itself.