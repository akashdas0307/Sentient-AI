# Phase 7 Design: Memory Consolidation Engine

**Phase:** 7
**Date:** 2026-04-18
**Status:** DRAFT — YELLOW gate (design only, no code changes)
**Branch target:** `auto/phase-7-consolidation`

---

## 1. Sleep Stages for Consolidation

The Sleep Scheduler (`src/sentient/sleep/scheduler.py`) defines five stages via the `SleepStage` enum (line 25-30): `AWAKE`, `SETTLING`, `MAINTENANCE`, `DEEP_CONSOLIDATION`, `PRE_WAKE`. Consolidation work maps to these stages as follows:

| Stage | Consolidation Activity | Rationale |
|-------|------------------------|-----------|
| `AWAKE` | None | Active cognition; no consolidation. |
| `SETTLING` | None | Wind-down phase; LLM calls would conflict with active work draining. |
| `MAINTENANCE` | Lightweight housekeeping only | SQLite `VACUUM`, `ANALYZE`, orphan cleanup, index rebuild. No LLM calls. |
| `DEEP_CONSOLIDATION` | Full consolidation engine | The only stage that triggers LLM-backed semantic and procedural extraction. |
| `PRE_WAKE` | None | Compiling handoff package; no new LLM work. |

The `_run_deep_consolidation()` method (scheduler.py:190-220) currently calls `_job_memory_consolidation()` (lines 222-236) which only logs the memory count. The ConsolidationEngine will be invoked here, replacing the stub.

The `_run_maintenance()` method (scheduler.py:173-188) currently logs and publishes an event. Lightweight SQLite operations (`VACUUM`, `ANALYZE`, dead-row cleanup) can be added here without LLM involvement.

---

## 2. Consolidation Triggers

Consolidation does not run on every sleep cycle. It triggers only when there is sufficient new material to extract from.

### Trigger Conditions

A consolidation cycle runs when ALL of the following are true:

1. **Minimum episodic threshold:** At least 6 new episodic memories have been stored since the last successful consolidation. The query checks `memories.created_at > last_consolidation_at WHERE memory_type = 'episodic' AND is_archived = 0`.

2. **Time tracking:** The `consolidation_log` table (architecture.py:89-97) already exists with a `consolidated_at` column. The last row's `consolidated_at` value serves as `last_consolidation_at`. On the first run (empty table), all episodic memories are candidates.

3. **Config gate:** `sleep.consolidation_enabled` (default: `true`). When `false`, `_run_deep_consolidation()` publishes `sleep.deep_consolidation.skipped` and returns immediately.

### Configuration Additions to `config/system.yaml`

```yaml
sleep:
  consolidation:
    enabled: true
    min_new_episodes: 6
    cycle_timeout_seconds: 120
    llm_call_timeout_seconds: 30
    max_semantic_facts: 1000
    max_procedural_patterns: 500
    confidence_threshold_semantic: 0.7
    confidence_threshold_procedural: 0.6
    consolidation_weight_bump: 0.1
    weight_decay_factor: 0.9
    weight_decay_cycles: 3
    semantic_similarity_threshold: 0.9
```

---

## 3. Extraction Types

### 3.1 Semantic Extraction

**Purpose:** Extract facts that remain true across episodes -- knowledge that transcends any single interaction.

**Model routing:** `kimi-k2.5:cloud` via the `consolidation` model label in `config/inference_gateway.yaml` (line 108-120). Kimi K2.5 is chosen for its large context window, enabling it to read many episodic memories in a single prompt. The config already defines this label with `kimi-k2.5:cloud` as primary and `glm-5.1:cloud` as fallback.

**Schema (`SemanticFact`):**

```python
class SemanticFact(BaseModel):
    """A fact extracted from episodic memories during consolidation."""
    fact_id: str           # UUID generated post-extraction
    statement: str         # The fact in natural language
    confidence: float      # 0.0-1.0
    evidence_episode_ids: list[str]  # Minimum 2 episode UUIDs
    first_observed: float  # Unix timestamp of earliest supporting episode
    last_reinforced: float # Unix timestamp of most recent supporting episode
    reinforcement_count: int = 1
```

**Post-validation rules:**
- Drop any fact with `len(evidence_episode_ids) < 2`. A single episode cannot produce a cross-episode fact.
- Drop any fact with `confidence < 0.7` (configurable via `sleep.consolidation.confidence_threshold_semantic`).
- If a new fact's `statement` is semantically similar (cosine similarity > 0.9 via ChromaDB) to an existing `semantic_memory` fact, reinforce the existing fact instead of creating a duplicate.

**Extraction prompt approach:** The consolidation engine assembles the episodic memories into a structured context block, then asks the LLM to identify patterns that recur across at least two episodes. The prompt mandates JSON output matching `SemanticFact` fields. Temperature is set to 0.1 for determinism.

### 3.2 Procedural Extraction

**Purpose:** Extract behavioral patterns and preferences -- how the system or its creator tends to act, what approaches are preferred, what workflows recur.

**Model routing:** `glm-5.1:cloud`. Procedural extraction requires deeper reasoning about causation and behavioral patterns, which justifies the stronger model. This call uses the `cognitive-core` model label as primary (lines 18-30 in inference_gateway.yaml) with a consolidation-specific override: a new model label `consolidation-procedural` will be added, routing to `glm-5.1:cloud` as primary with `minimax-m2.7:cloud` as fallback.

**Schema (`ProceduralPattern`):**

```python
class ProceduralPattern(BaseModel):
    """A behavioral pattern extracted from episodic memories during consolidation."""
    pattern_id: str        # UUID generated post-extraction
    description: str      # Natural language description of the pattern
    trigger_context: str   # When/where this pattern tends to activate
    confidence: float       # 0.0-1.0
    evidence_episode_ids: list[str]  # Minimum 2 episode UUIDs
    first_observed: float  # Unix timestamp of earliest supporting episode
    last_reinforced: float # Unix timestamp of most recent supporting episode
    reinforcement_count: int = 1
```

**Post-validation rules:**
- Drop any pattern with `len(evidence_episode_ids) < 2`. Noise from a single episode is not a pattern.
- Drop any pattern with `confidence < 0.6` (configurable via `sleep.consolidation.confidence_threshold_procedural`). The lower threshold compared to semantic facts acknowledges that patterns are inherently less certain than facts.
- Similar dedup rule: if a new pattern's `description` is semantically similar (cosine > 0.9) to an existing `procedural_memory` pattern, reinforce the existing one.

---

## 4. Storage Schemas

### 4.1 New Tables

Two new tables are added to the SQLite schema in `src/sentient/memory/architecture.py`. They use `CREATE TABLE IF NOT EXISTS` for idempotency, consistent with the existing `SQLITE_SCHEMA` pattern (architecture.py:34-98).

```sql
CREATE TABLE IF NOT EXISTS semantic_memory (
    id TEXT PRIMARY KEY,
    fact_id TEXT NOT NULL UNIQUE,
    statement TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 0.7,
    evidence_episode_ids TEXT NOT NULL DEFAULT '[]',   -- JSON array
    first_observed REAL NOT NULL,
    last_reinforced REAL NOT NULL,
    reinforcement_count INTEGER NOT NULL DEFAULT 1,
    created_at REAL NOT NULL,
    updated_at REAL,
    is_active INTEGER NOT NULL DEFAULT 1              -- soft delete for pruning
);

CREATE INDEX IF NOT EXISTS idx_semantic_confidence ON semantic_memory(confidence);
CREATE INDEX IF NOT EXISTS idx_semantic_active ON semantic_memory(is_active);
CREATE INDEX IF NOT EXISTS idx_semantic_first_observed ON semantic_memory(first_observed);
CREATE INDEX IF NOT EXISTS idx_semantic_fact_id ON semantic_memory(fact_id);

CREATE TABLE IF NOT EXISTS procedural_memory (
    id TEXT PRIMARY KEY,
    pattern_id TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL,
    trigger_context TEXT NOT NULL DEFAULT '',
    confidence REAL NOT NULL DEFAULT 0.6,
    evidence_episode_ids TEXT NOT NULL DEFAULT '[]',   -- JSON array
    first_observed REAL NOT NULL,
    last_reinforced REAL NOT NULL,
    reinforcement_count INTEGER NOT NULL DEFAULT 1,
    created_at REAL NOT NULL,
    updated_at REAL,
    is_active INTEGER NOT NULL DEFAULT 1               -- soft delete for pruning
);

CREATE INDEX IF NOT EXISTS idx_procedural_confidence ON procedural_memory(confidence);
CREATE INDEX IF NOT EXISTS idx_procedural_active ON procedural_memory(is_active);
CREATE INDEX IF NOT EXISTS idx_procedural_first_observed ON procedural_memory(first_observed);
CREATE INDEX IF NOT EXISTS idx_procedural_pattern_id ON procedural_memory(pattern_id);
```

**Design notes:**
- `evidence_episode_ids` uses a JSON array string (consistent with `entity_tags`, `topic_tags` in the existing `memories` table at architecture.py:48-51).
- `is_active` enables soft-delete pruning (Section 6) without losing audit trail.
- `confidence` is indexed because the pruning query orders by confidence ascending and deletes the lowest entries first.
- `first_observed` is indexed for time-range queries during retrieval.
- Both tables carry `created_at` and `updated_at` for auditability.

### 4.2 Altering the Existing `memories` Table

The `memories` table (architecture.py:35-54) needs a new column for consolidation weighting. SQLite does not support `ALTER TABLE IF NOT EXISTS`, so the implementation uses a try/except pattern:

```python
def _add_consolidation_weight_column(self) -> None:
    """Add consolidation_weight to memories table if it doesn't exist."""
    if not self._conn:
        return
    try:
        self._conn.execute(
            "ALTER TABLE memories ADD COLUMN consolidation_weight REAL DEFAULT 0.0"
        )
    except sqlite3.OperationalError:
        # Column already exists — safe to ignore
        pass
```

This is called during `initialize()` after `executescript(SQLITE_SCHEMA)`. The `consolidation_weight` column:
- Starts at `0.0` for all existing and new episodic memories.
- Is bumped by `0.1` per fact/pattern that references the episode (configurable via `sleep.consolidation.consolidation_weight_bump`).
- Is used during retrieval to boost or dampen episodic memory relevance.

### 4.3 ChromaDB Collections

Two new ChromaDB collections are created alongside the existing `memories` collection (architecture.py:151-153):

```python
self._semantic_collection = self._chroma_client.get_or_create_collection(
    name="semantic_memory",
    metadata={"hnsw:space": "cosine"},
)
self._procedural_collection = self._chroma_client.get_or_create_collection(
    name="procedural_memory",
    metadata={"hnsw:space": "cosine"},
)
```

These are needed for the dedup check (cosine > 0.9 similarity) on new facts/patterns, and for future retrieval of consolidated knowledge.

---

## 5. Pruning and Weighting

### 5.1 Consolidation Weight Bumping

When a semantic fact or procedural pattern is stored, each episodic memory referenced in its `evidence_episode_ids` gets its `consolidation_weight` bumped:

```sql
UPDATE memories
SET consolidation_weight = consolidation_weight + ?
WHERE id = ?
```

The bump amount is `0.1` per fact/pattern supported (configurable via `sleep.consolidation.consolidation_weight_bump`). This means an episode that contributed evidence to 3 facts and 2 patterns would gain `0.5` in consolidation weight.

### 5.2 Weight Decay for Unconsolidated Episodes

Episodes that are never referenced in any consolidated fact or pattern gradually lose retrieval relevance. After each consolidation cycle:

- Check all episodic memories with `consolidation_weight = 0.0` (or effectively low weight) that have been through `N` or more consolidation cycles without being referenced (config: `memory.consolidation_weight_decay_cycles`, default `3`).
- Multiply their `importance` field by `0.9` (configurable via `sleep.consolidation.weight_decay_factor`).

**Key invariant:** Episodes are NEVER deleted. The `is_archived` column (already in the schema at architecture.py:52) may be set to `1` for heavily decayed episodes, but the row persists.

### 5.3 Reinforcement of Existing Facts/Patterns

When a new extraction produces a fact/pattern that is semantically similar (cosine > 0.9) to an existing one:

1. Find the matching existing row in `semantic_memory` or `procedural_memory`.
2. Increment its `reinforcement_count` by 1.
3. Adjust `confidence` upward by `0.05` per reinforcement, capped at `1.0`.
4. Update `last_reinforced` to the current timestamp.
5. Append the new evidence episode IDs to `evidence_episode_ids` (union, no duplicates).
6. Bump consolidation_weight on the newly-referenced episodes.

This design ensures that consolidated knowledge only grows stronger or stays stable -- it never degrades.

---

## 6. Time Budget

The `_run_deep_consolidation()` method (scheduler.py:190-220) already sleeps for the full `consolidation_runtime` (line 219-220). The ConsolidationEngine replaces the stub `_job_memory_consolidation()` call (line 210) with a timed cycle.

### Per-Call Timeout

Each LLM call during consolidation is wrapped in `asyncio.wait_for(call, timeout=30)`:

```python
try:
    result = await asyncio.wait_for(
        self.gateway.infer(request),
        timeout=self.config.llm_call_timeout_seconds,  # default 30
    )
except asyncio.TimeoutError:
    logger.warning("Consolidation LLM call timed out after %ds", timeout)
    # Continue to next extraction type
```

The `InferenceGateway.infer()` method (inference_gateway.py:257) already uses `asyncio.wait_for` with `request.timeout_seconds` (default 60). The consolidation engine sets `timeout_seconds=30` on each `InferenceRequest`, providing a hard per-call ceiling.

### Cycle Budget

Total cycle budget: 120 seconds (configurable via `sleep.consolidation.cycle_timeout_seconds`).

The cycle is structured as:

| Step | Max Duration | Timeout Behavior |
|------|-------------|------------------|
| Fetch candidate episodes | 5s | If timeout, abort entire cycle |
| Semantic extraction LLM call | 30s | If timeout, skip semantic, proceed to procedural |
| Semantic post-validation | 5s | CPU-only, no timeout risk |
| Procedural extraction LLM call | 30s | If timeout, skip procedural, proceed to logging |
| Procedural post-validation | 5s | CPU-only, no timeout risk |
| Write results + log | 10s | CPU-only + SQLite, no timeout risk |
| **Total worst case** | **~115s** | Fits within 120s budget |

If semantic extraction times out, the engine logs the timeout and proceeds to procedural extraction. This partial-completion approach is preferable to aborting the entire cycle, because procedural patterns can still be extracted even if semantic extraction failed.

The existing `_run_deep_consolidation()` method sleeps for the remaining time after the engine completes (scheduler.py:219-220). This is preserved -- if the consolidation engine finishes in 90 seconds, the system still waits in deep sleep for the remaining time.

---

## 7. False-Positive Risk Mitigation

### 7.1 Minimum Evidence Count (2 episodes)

Both `SemanticFact` and `ProceduralPattern` require `evidence_episode_ids` with at least 2 entries. This is enforced in two places:

1. **Prompt level:** The extraction prompt explicitly instructs the LLM: "Only identify patterns or facts that appear in at least 2 different episodes. Do not extract facts from a single episode."
2. **Post-validation level:** After parsing the LLM response, any fact/pattern with `len(evidence_episode_ids) < 2` is dropped before storage.

The dual enforcement ensures that even if the LLM generates a single-evidence fact, it will not be stored.

### 7.2 Confidence Thresholds

- Semantic facts: minimum `0.7` confidence for storage.
- Procedural patterns: minimum `0.6` confidence for storage.

These are enforced in post-validation. Any extraction below the threshold is dropped. The lower threshold for patterns acknowledges that behavioral patterns are inherently less certain than declarative facts.

### 7.3 No Overwrites -- Add or Reinforce Only

Consolidation never deletes or overwrites existing facts or patterns. The only operations are:

- **Add:** Insert a new fact/pattern that passes all validation.
- **Reinforce:** Increment `reinforcement_count`, adjust `confidence` upward by `0.05` (capped at `1.0`), update `last_reinforced`, and extend `evidence_episode_ids`.

This is a critical safety property. Even if a consolidation cycle produces incorrect facts, those facts do not replace correct ones. Incorrect facts can only be addressed by:

1. Not reinforcing them in future cycles (they stay at their initial confidence).
2. Pruning them when capacity limits are reached (lowest confidence first).
3. The creator manually reviewing and deactivating them (future capability).

### 7.4 Semantic Dedup (Cosine > 0.9)

Before storing a new fact/pattern, the engine checks ChromaDB for semantically similar existing entries. If cosine similarity exceeds 0.9, the new entry is NOT stored. Instead, the existing entry is reinforced (see Section 5.3). This prevents the accumulation of near-duplicate facts like "The creator's name is Akash" and "Akash is the creator's name".

The threshold of 0.9 is deliberately high to avoid false merges. Two facts can be related but distinct (e.g., "Akash prefers Python" and "Akash prefers functional programming" -- similar topic, different facts). Only near-identical statements merge.

---

## 8. Memory Growth Management

### 8.1 Capacity Limits

| Type | Maximum Count | Config Key | Default |
|------|---------------|------------|---------|
| Semantic facts | 1000 | `sleep.consolidation.max_semantic_facts` | 1000 |
| Procedural patterns | 500 | `sleep.consolidation.max_procedural_patterns` | 500 |

When a limit is reached, the next consolidation cycle prunes before adding:

1. Sort existing entries by `confidence ASC`.
2. Deactivate (set `is_active = 0`) the lowest-confidence entries until there is room for the new entries.
3. Soft-delete preserves the audit trail -- `is_active = 0` entries are excluded from retrieval but retained in the database.

### 8.2 Consolidation Log

Every consolidation cycle records an entry in the existing `consolidation_log` table (architecture.py:89-97). The existing schema columns are:

- `id`: UUID primary key
- `consolidated_at`: Unix timestamp
- `scope`: `'daily' | 'weekly' | 'monthly' | 'quarterly'`
- `summary_content`: Text summary of what was extracted
- `source_memory_count`: Number of episodic memories processed
- `coverage_start`: Timestamp of oldest episode processed
- `coverage_end`: Timestamp of newest episode processed

For Phase 7, the scope will always be `'daily'` (triggered by each sleep cycle). The `summary_content` field will contain a JSON string with extraction statistics:

```json
{
  "semantic_facts_extracted": 5,
  "procedural_patterns_extracted": 3,
  "facts_reinforced": 2,
  "patterns_reinforced": 1,
  "episodes_processed": 12,
  "semantic_timeout": false,
  "procedural_timeout": false,
  "cycle_duration_seconds": 87.3
}
```

---

## 9. Adversarial Review

### (a) Harmful Fact Risk: Technically Correct but Sycophantic Patterns

**Concern:** Consolidation might extract a fact like "User always agrees with suggestions" or "User prefers brief answers." While factually observed across episodes, encoding this as a behavioral pattern could cause the system to become sycophantic or stop challenging the creator's ideas.

**Mitigation:**
- The extraction prompt must include an explicit instruction: "Do not extract patterns that would reduce the system's ability to provide honest, independent analysis. Exclude patterns that encode compliance, agreement, or preference for reduced rigor."
- Post-validation adds a secondary check: if a pattern's `description` contains words like "always agrees," "prefers yes," "never challenges," or similar compliance-encoding phrases, the pattern is dropped regardless of confidence score. This is implemented as a keyword blocklist in the `ConsolidationEngine`, not as an LLM call (stays deterministic and zero-cost).
- The Constitutional Core (immutable, per DD-025 and `config/identity/constitutional_core.yaml`) already encodes the principle of honest engagement. Facts that conflict with constitutional principles are candidates for contradiction detection in future phases.

### (b) Hallucinated Patterns from Noise

**Concern:** The LLM might identify a "pattern" from just 2 episodes that is actually coincidence. For example, if the system discussed Python on Monday and debugging on Wednesday, the LLM might extract "User prefers Python for debugging" -- a spurious correlation.

**Mitigation:**
- The minimum evidence count of 2 episodes is the floor, not a guarantee of quality. The extraction prompt instructs: "A pattern must be clearly demonstrated across the cited episodes. Coincidental co-occurrence is not a pattern."
- The confidence thresholds (0.7 for facts, 0.6 for patterns) filter out low-confidence extractions. An LLM that is unsure about a pattern will rate it below threshold.
- Each fact/pattern stores its `evidence_episode_ids`. An audit tool (future work) can replay the cited episodes to verify that the extraction is warranted. For Phase 7, the `consolidation_log` provides enough traceability for manual review.
- Over time, reinforcement only occurs when future episodes independently support the same fact/pattern. A spurious pattern that is never reinforced again stays at its initial confidence, making it a prime candidate for pruning when capacity limits are reached.

### (c) Incomplete Sleep Cycle

**Concern:** If the sleep cycle is interrupted (emergency wake, system crash, timeout) during deep consolidation, the cycle might be only partially complete -- semantic extraction succeeded but procedural extraction did not, or the consolidation_log entry was never written.

**Mitigation:**
- Each extraction step (semantic, procedural) is independently committed to SQLite. If the cycle is interrupted after semantic extraction completes, those facts are persisted even if procedural extraction never runs.
- The `consolidation_log` entry is written as the last step of the cycle. If it is never written, the next cycle will see that the `last_consolidation_at` timestamp is stale and will re-process the same episodes. This is safe because the idempotent dedup check (cosine > 0.9) prevents duplicate facts from being created.
- The existing emergency wake mechanism (scheduler.py:292-313) saves a checkpoint dict. For Phase 7, this checkpoint is extended to include `consolidation_progress`: which extraction steps completed. On the next sleep cycle, the scheduler can resume from where it left off rather than starting over.
- The 30-second per-call timeout ensures that a single hung LLM call does not block the entire cycle. If both extraction calls timeout, the cycle completes with 0 new extractions but still writes a `consolidation_log` entry recording the timeouts. This prevents the same stuck state from recurring on every sleep cycle.

---

## 10. Integration Points

### 10.1 Sleep Scheduler Integration

The `_run_deep_consolidation()` method (scheduler.py:190-220) is modified to call `ConsolidationEngine.consolidate_cycle()` instead of the current `_job_memory_consolidation()` stub. The scheduler passes its `self.memory` reference to the engine.

The `_job_memory_consolidation()` method (scheduler.py:222-236) is removed. Its logging is replaced by the consolidation engine's own logging.

### 10.2 Memory Architecture Integration

The `MemoryArchitecture` class (architecture.py:101-589) gains three new methods:

1. `fetch_consolidation_candidates(since: float) -> list[dict]` -- Retrieves episodic memories created after `since` timestamp, ordered by `created_at`.
2. `add_consolidation_weight(memory_ids: list[str], bump: float)` -- Increments `consolidation_weight` for the given memory IDs.
3. `decay_unconsolidated_episodes(cycle_count_threshold: int, factor: float)` -- Multiplies `importance` by `factor` for episodic memories with `consolidation_weight` below a threshold that have been through enough consolidation cycles.

The existing `store()` method (architecture.py:206-294) is extended to also insert into the `semantic_memory` and `procedural_memory` ChromaDB collections when a memory type of `semantic` or `procedural` is passed.

### 10.3 Cognitive Core Integration (Post-Consolidation Retrieval)

The `_assemble_prompt()` method (cognitive_core.py:339-409) currently injects episodic memory (lines 368-391). Post-consolidation, it should also inject semantic and procedural knowledge:

```python
# After episodic memory block (line 391)
# Semantic knowledge block (if available)
if self.memory and not is_daydream:
    semantic_facts = await self.memory.retrieve(
        query=input_text,
        memory_types=[MemoryType.SEMANTIC],
        limit=5,
    )
    if semantic_facts:
        fact_lines = [f"- [{f['confidence']:.1f}] {f['statement']}" for f in semantic_facts]
        blocks.append("=== SEMANTIC KNOWLEDGE ===\n" + "\n".join(fact_lines))

# Procedural knowledge block (if available)
if self.memory and not is_daydream:
    procedural_patterns = await self.memory.retrieve(
        query=input_text,
        memory_types=[MemoryType.PROCEDURAL],
        limit=3,
    )
    if procedural_patterns:
        pattern_lines = [f"- [{p['confidence']:.1f}] {p['description']}" for p in procedural_patterns]
        blocks.append("=== LEARNED PATTERNS ===\n" + "\n".join(pattern_lines))
```

This is a Phase 7 deliverable (D5) that runs AFTER the consolidation engine is wired in. The retrieval path reuses the existing `MemoryArchitecture.retrieve()` method with `memory_types` filtering.

### 10.4 Inference Gateway Configuration

Two new model labels are added to `config/inference_gateway.yaml`:

```yaml
  # === Semantic extraction during sleep (large context) ===
  consolidation-semantic:
    primary:
      provider: "ollama"
      model: "kimi-k2.5:cloud"
      base_url: "http://localhost:11434"
      max_tokens: 1024
      temperature: 0.1
    fallback:
      - provider: "ollama"
        model: "glm-5.1:cloud"
        base_url: "http://localhost:11434"
        max_tokens: 1024
        temperature: 0.1

  # === Procedural extraction during sleep (deep reasoning) ===
  consolidation-procedural:
    primary:
      provider: "ollama"
      model: "glm-5.1:cloud"
      base_url: "http://localhost:11434"
      max_tokens: 1024
      temperature: 0.1
    fallback:
      - provider: "ollama"
        model: "kimi-k2.5:cloud"
        base_url: "http://localhost:11434"
        max_tokens: 1024
        temperature: 0.1
```

The existing `consolidation` label (lines 108-120) is retained for backward compatibility but is superseded by the two specific labels.

### 10.5 Event Bus Events

New events published by the ConsolidationEngine:

| Event | Payload | When |
|-------|---------|------|
| `sleep.consolidation.cycle_start` | `{cycle_id, episode_count}` | At the start of a consolidation cycle |
| `sleep.consolidation.semantic_complete` | `{facts_extracted, facts_reinforced, timed_out}` | After semantic extraction completes or times out |
| `sleep.consolidation.procedural_complete` | `{patterns_extracted, patterns_reinforced, timed_out}` | After procedural extraction completes or times out |
| `sleep.consolidation.cycle_complete` | `{cycle_id, facts_extracted, patterns_extracted, duration_seconds}` | After the full cycle finishes |
| `sleep.consolidation.skipped` | `{reason}` | When consolidation is disabled or insufficient episodes |

These events allow other modules (e.g., the PersonaManager which already subscribes to `sleep.consolidation.developmental` per identity_manager.py:78) to react to consolidation outcomes.

---

## 11. ConsolidationEngine Class Skeleton

```python
class ConsolidationEngine:
    """Extracts semantic facts and procedural patterns from episodic memories
    during the DEEP_CONSOLIDATION sleep stage."""

    def __init__(
        self,
        config: dict[str, Any],
        memory: MemoryArchitecture,
        gateway: InferenceGateway,
        event_bus: EventBus,
    ) -> None: ...

    async def consolidate_cycle(self) -> ConsolidationResult:
        """Run one full consolidation cycle.

        1. Check trigger conditions (enough new episodes, enabled).
        2. Fetch candidate episodes since last consolidation.
        3. Run semantic extraction (with timeout).
        4. Run procedural extraction (with timeout).
        5. Post-validate and store results.
        6. Update consolidation weights on source episodes.
        7. Log results to consolidation_log.
        """

    async def _extract_semantic(self, episodes: list[dict]) -> list[SemanticFact]:
        """Call LLM to extract semantic facts from episodes."""

    async def _extract_procedural(self, episodes: list[dict]) -> list[ProceduralPattern]:
        """Call LLM to extract procedural patterns from episodes."""

    def _post_validate_semantic(self, facts: list[SemanticFact]) -> list[SemanticFact]:
        """Drop facts with evidence_count < 2 or confidence < threshold."""

    def _post_validate_procedural(self, patterns: list[ProceduralPattern]) -> list[ProceduralPattern]:
        """Drop patterns with evidence_count < 2 or confidence < threshold."""

    async def _store_semantic_facts(self, facts: list[SemanticFact]) -> tuple[int, int]:
        """Store new facts and reinforce existing similar ones.
        Returns (new_count, reinforced_count)."""

    async def _store_procedural_patterns(self, patterns: list[ProceduralPattern]) -> tuple[int, int]:
        """Store new patterns and reinforce existing similar ones.
        Returns (new_count, reinforced_count)."""

    async def _bump_consolidation_weights(self, episode_ids: list[str]) -> None:
        """Increment consolidation_weight for episodes that contributed evidence."""

    async def _decay_unconsolidated(self) -> None:
        """Decay importance for episodes not referenced in any consolidated memory."""

    async def _prune_if_at_capacity(self) -> None:
        """Soft-delete lowest-confidence facts/patterns if at capacity limits."""

    async def _log_consolidation_result(self, result: ConsolidationResult) -> None:
        """Write a row to consolidation_log with cycle statistics."""
```

---

## 12. Deliverable Breakdown

| ID | Deliverable | Gate | Description |
|----|-------------|------|-------------|
| D1 | Consolidation Architecture Design | YELLOW | This document |
| D2 | Schema & Storage Layer | GREEN | Add tables, alter `memories`, add ChromaDB collections, add retrieval methods |
| D3 | Consolidation Engine | GREEN | Implement `ConsolidationEngine` class with extraction, validation, storage, weighting |
| D4 | Sleep Scheduler Integration | YELLOW | Wire engine into `_run_deep_consolidation()`, add config, add events |
| D5 | Post-Consolidation Retrieval in Cognitive Core | YELLOW | Inject semantic/procedural knowledge into `_assemble_prompt()` |
| D6 | Consolidation Wetware Test | GREEN | End-to-end test: create episodes, trigger consolidation, verify facts extracted |
| D7 | Close-Out Checkpoint | GREEN | Phase report, doc audit, merge prep |

---

## 13. File Impact Summary

| File | Change Type | Description |
|------|------------|-------------|
| `src/sentient/memory/architecture.py` | Modify | Add `semantic_memory`/`procedural_memory` tables, add `consolidation_weight` column, add retrieval methods |
| `src/sentient/memory/consolidation.py` | **New** | `ConsolidationEngine` class |
| `src/sentient/memory/schemas.py` | **New** | `SemanticFact`, `ProceduralPattern`, `ConsolidationResult` Pydantic models |
| `src/sentient/sleep/scheduler.py` | Modify | Replace `_job_memory_consolidation()` stub with `ConsolidationEngine` call |
| `src/sentient/prajna/frontal/cognitive_core.py` | Modify | Add semantic/procedural blocks to `_assemble_prompt()` |
| `config/system.yaml` | Modify | Add `sleep.consolidation.*` configuration |
| `config/inference_gateway.yaml` | Modify | Add `consolidation-semantic` and `consolidation-procedural` model labels |
| `tests/unit/memory/test_consolidation.py` | **New** | Unit tests for extraction, validation, storage |
| `tests/integration/test_consolidation_flow.py` | **New** | Integration test for full cycle |
| `tests/wetware/test_consolidation.py` | **New** | End-to-end test with real LLM calls |

---

## 14. References

- `src/sentient/sleep/scheduler.py:25-30` -- `SleepStage` enum definition
- `src/sentient/sleep/scheduler.py:190-236` -- `_run_deep_consolidation()` and `_job_memory_consolidation()` stubs
- `src/sentient/memory/architecture.py:34-98` -- Existing SQLite schema including `consolidation_log`
- `src/sentient/memory/architecture.py:101-589` -- `MemoryArchitecture` class with `store()`, `retrieve()`, `_reinforce()`
- `src/sentient/prajna/frontal/cognitive_core.py:339-409` -- `_assemble_prompt()` where semantic/procedural blocks will be injected
- `src/sentient/core/inference_gateway.py:48-58` -- `InferenceRequest` dataclass with `response_format` and `timeout_seconds`
- `src/sentient/core/event_bus.py:22-51` -- Event types docstring showing existing events
- `config/inference_gateway.yaml:108-120` -- Existing `consolidation` model label
- `config/system.yaml:117-133` -- Existing sleep configuration structure
- `src/sentient/prajna/frontal/schemas.py:31-35` -- `MemoryCandidate` with `type` Literal including `semantic` and `procedural`
- `src/sentient/memory/gatekeeper.py:1-134` -- `MemoryGatekeeper` class with `_possible_contradiction()` heuristic
- `src/sentient/persona/identity_manager.py:78` -- Subscription to `sleep.consolidation.developmental` event
