"""Unit tests for DevelopmentalConsolidator."""

from __future__ import annotations

import json
import sqlite3
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml

from sentient.sleep.developmental_consolidator import (
    DEFAULT_ENABLED,
    DEFAULT_LLM_TIMEOUT_SECONDS,
    DEFAULT_MAX_TRAITS_PER_CYCLE,
    DEFAULT_MIN_EVIDENCE_POINTS,
    DevelopmentalConsolidator,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def in_memory_db():
    """Create an in-memory SQLite database with the required schema."""
    conn = sqlite3.connect(":memory:", isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE memories (
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
            entity_tags TEXT DEFAULT '[]',
            topic_tags TEXT DEFAULT '[]',
            emotional_tags TEXT DEFAULT '{}',
            metadata TEXT DEFAULT '{}',
            is_archived INTEGER DEFAULT 0,
            archived_at REAL,
            consolidation_weight REAL DEFAULT 0.0
        );

        CREATE TABLE semantic_memory (
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
    """)
    return conn


@pytest.fixture
def mock_memory(in_memory_db):
    """Mock MemoryArchitecture backed by real in-memory SQLite."""
    arch = MagicMock()
    arch._conn = in_memory_db
    return arch


@pytest.fixture
def mock_gateway():
    """Mock InferenceGateway with async infer."""
    gateway = MagicMock()
    gateway.infer = AsyncMock()
    return gateway


@pytest.fixture
def mock_persona():
    """Mock PersonaManager."""
    persona = MagicMock()
    return persona


@pytest.fixture
def mock_event_bus():
    """Mock EventBus with async publish."""
    bus = MagicMock()
    bus.publish = AsyncMock()
    return bus


@pytest.fixture
def default_config():
    """Default config dict."""
    return {
        "enabled": True,
        "min_evidence_points": DEFAULT_MIN_EVIDENCE_POINTS,
        "max_traits_per_cycle": DEFAULT_MAX_TRAITS_PER_CYCLE,
        "llm_timeout_seconds": DEFAULT_LLM_TIMEOUT_SECONDS,
    }


@pytest.fixture
def consolidator(mock_memory, mock_gateway, mock_persona, mock_event_bus, default_config):
    """DevelopmentalConsolidator with all mocked dependencies."""
    return DevelopmentalConsolidator(
        memory=mock_memory,
        gateway=mock_gateway,
        persona=mock_persona,
        event_bus=mock_event_bus,
        config=default_config,
    )


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _ep(id_suffix: str, created_at: float, content: str) -> dict[str, Any]:
    return {
        "id": f"ep-{id_suffix}",
        "memory_type": "episodic",
        "content": content,
        "content_hash": f"hash-{id_suffix}",
        "importance": 0.5,
        "confidence": 1.0,
        "created_at": created_at,
        "is_archived": 0,
        "entity_tags": "[]",
        "topic_tags": "[]",
        "emotional_tags": "{}",
        "metadata": "{}",
    }


# ---------------------------------------------------------------------------
# Test 1: Initialization with config
# ---------------------------------------------------------------------------

def test_initialization_with_config(mock_memory, mock_gateway, mock_persona, mock_event_bus):
    """All config values are read from config dict."""
    config = {
        "enabled": False,
        "min_evidence_points": 5,
        "max_traits_per_cycle": 3,
        "llm_timeout_seconds": 60,
    }
    dc = DevelopmentalConsolidator(
        memory=mock_memory,
        gateway=mock_gateway,
        persona=mock_persona,
        event_bus=mock_event_bus,
        config=config,
    )
    assert dc._enabled is False
    assert dc._min_evidence_points == 5
    assert dc._max_traits_per_cycle == 3
    assert dc._llm_timeout == 60


def test_initialization_defaults(mock_memory, mock_gateway, mock_persona, mock_event_bus):
    """Defaults are used when config keys are absent."""
    dc = DevelopmentalConsolidator(
        memory=mock_memory,
        gateway=mock_gateway,
        persona=mock_persona,
        event_bus=mock_event_bus,
        config={},
    )
    assert dc._enabled == DEFAULT_ENABLED
    assert dc._min_evidence_points == DEFAULT_MIN_EVIDENCE_POINTS
    assert dc._max_traits_per_cycle == DEFAULT_MAX_TRAITS_PER_CYCLE
    assert dc._llm_timeout == DEFAULT_LLM_TIMEOUT_SECONDS


# ---------------------------------------------------------------------------
# Test 2: Disabled consolidator returns skipped status
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_disabled_consolidator_skips(mock_memory, mock_gateway, mock_persona, mock_event_bus):
    """When enabled=False, consolidate returns skipped status immediately."""
    config = {"enabled": False}
    dc = DevelopmentalConsolidator(
        memory=mock_memory,
        gateway=mock_gateway,
        persona=mock_persona,
        event_bus=mock_event_bus,
        config=config,
    )
    result = await dc.consolidate()

    assert result["status"] == "skipped"
    assert result["reason"] == "disabled"
    assert result["signals_extracted"] == 0
    # Gateway should never have been called
    mock_gateway.infer.assert_not_called()


# ---------------------------------------------------------------------------
# Test 3: Personality signal extraction with mock LLM
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_signal_extraction_calls_llm_with_formatted_prompt(
    consolidator, mock_gateway, in_memory_db
):
    """LLM is called with episodic and semantic content in the prompt."""
    now = time.time()
    for i in range(3):
        in_memory_db.execute(
            "INSERT INTO memories (id, memory_type, content, content_hash, importance, confidence, created_at, is_archived) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (f"ep-{i}", "episodic", f"episode {i}", f"hash{i}", 0.5, 1.0, now - 100 + i, 0),
        )
    in_memory_db.execute(
        "INSERT INTO semantic_memory (fact_id, statement, confidence, evidence_episode_ids, evidence_count, first_observed, last_reinforced, reinforcement_count, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("fact-1", "A known fact.", 0.8, "[]", 0, now, now, 1, now),
    )

    mock_gateway.infer = AsyncMock(
        return_value=MagicMock(
            error=None,
            text='{"signals": []}',
        )
    )

    await consolidator.consolidate()

    mock_gateway.infer.assert_called_once()
    call_args = mock_gateway.infer.call_args
    request = call_args[0][0]
    assert request.model_label == "consolidation-semantic"
    assert "episode 0" in request.prompt
    assert "A known fact" in request.prompt


# ---------------------------------------------------------------------------
# Test 4: Evidence threshold filtering (<3 evidence points dropped)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_signals_below_evidence_threshold_are_dropped(
    consolidator, mock_gateway, in_memory_db
):
    """Signals with evidence_count < 3 are not included in the published updates."""
    now = time.time()
    for i in range(3):
        in_memory_db.execute(
            "INSERT INTO memories (id, memory_type, content, content_hash, importance, confidence, created_at, is_archived) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (f"ep-{i}", "episodic", f"episode {i}", f"hash{i}", 0.5, 1.0, now - 100 + i, 0),
        )

    signals = [
        {
            "trait_name": "curiosity",
            "strength": 0.7,
            "evidence_count": 2,  # below min_evidence_points=3
            "evidence_descriptions": ["desc1", "desc2"],
            "category": "personality_traits",
        },
        {
            "trait_name": "cautiousness",
            "strength": 0.6,
            "evidence_count": 3,  # meets threshold
            "evidence_descriptions": ["desc1", "desc2", "desc3"],
            "category": "personality_traits",
        },
    ]

    mock_gateway.infer = AsyncMock(
        return_value=MagicMock(error=None, text=json.dumps({"signals": signals}))
    )

    result = await consolidator.consolidate()

    assert result["signals_extracted"] == 2
    assert result["traits_proposed"] == 1  # Only cautiousness survives filter

    # Verify event was published with only 1 trait
    publish_call = consolidator.event_bus.publish.call_args
    assert publish_call is not None
    updates = publish_call[0][1]["updates"]
    assert "cautiousness" in updates["personality_traits"]
    assert "curiosity" not in updates["personality_traits"]


# ---------------------------------------------------------------------------
# Test 5: Max traits per cycle cap (only 5 applied)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_max_traits_per_cycle_cap(
    consolidator, mock_gateway, in_memory_db
):
    """Only the first 5 traits (capped) are included in proposed updates."""
    now = time.time()
    for i in range(3):
        in_memory_db.execute(
            "INSERT INTO memories (id, memory_type, content, content_hash, importance, confidence, created_at, is_archived) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (f"ep-{i}", "episodic", f"episode {i}", f"hash{i}", 0.5, 1.0, now - 100 + i, 0),
        )

    # Generate 7 signals — consolidator should cap at 5
    signals = [
        {
            "trait_name": f"trait-{i}",
            "strength": 0.5,
            "evidence_count": 5,
            "evidence_descriptions": ["desc"],
            "category": "personality_traits",
        }
        for i in range(7)
    ]

    mock_gateway.infer = AsyncMock(
        return_value=MagicMock(error=None, text=json.dumps({"signals": signals}))
    )

    result = await consolidator.consolidate()

    assert result["traits_proposed"] == 5

    publish_call = consolidator.event_bus.publish.call_args
    updates = publish_call[0][1]["updates"]
    proposed_traits = updates["personality_traits"]
    assert len(proposed_traits) == 5


# ---------------------------------------------------------------------------
# Test 6: sleep.consolidation.developmental event emission
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_developmental_event_is_published(
    consolidator, mock_gateway, in_memory_db
):
    """An event with the correct name and updates payload is published."""
    now = time.time()
    for i in range(3):
        in_memory_db.execute(
            "INSERT INTO memories (id, memory_type, content, content_hash, importance, confidence, created_at, is_archived) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (f"ep-{i}", "episodic", f"episode {i}", f"hash{i}", 0.5, 1.0, now - 100 + i, 0),
        )

    mock_gateway.infer = AsyncMock(
        return_value=MagicMock(
            error=None,
            text=json.dumps({
                "signals": [
                    {
                        "trait_name": "curiosity",
                        "strength": 0.8,
                        "evidence_count": 5,
                        "evidence_descriptions": ["e1", "e2", "e3", "e4", "e5"],
                        "category": "personality_traits",
                    },
                    {
                        "trait_name": "formal",
                        "strength": 0.6,
                        "evidence_count": 3,
                        "evidence_descriptions": ["e1", "e2", "e3"],
                        "category": "communication_style",
                    },
                ]
            }),
        )
    )

    await consolidator.consolidate()

    consolidator.event_bus.publish.assert_called_once()
    call_args = consolidator.event_bus.publish.call_args
    event_name = call_args[0][0]
    assert event_name == "sleep.consolidation.developmental"
    payload = call_args[0][1]
    assert "updates" in payload
    updates = payload["updates"]
    assert "curiosity" in updates["personality_traits"]
    assert "formal" in updates["communication_style"]


# ---------------------------------------------------------------------------
# Test 7: Atomic write (tmpfile + rename pattern) in _save_developmental
# ---------------------------------------------------------------------------

def test_save_developmental_atomic_write(tmp_path):
    """_save_developmental writes via tmpfile then rename."""
    from sentient.persona.identity_manager import PersonaManager

    # Create a temporary developmental.yaml file
    dev_path = tmp_path / "developmental.yaml"
    initial_data = {
        "version": 1,
        "last_updated": None,
        "maturity_stage": "nascent",
        "personality_traits": {},
        "communication_style": {},
        "interests": [],
        "self_understanding": {},
        "relational_texture": {"creator": {}},
        "maturity_log": [],
        "pending_trait_candidates": [],
        "drift_log": [],
    }
    with open(dev_path, "w") as f:
        yaml.safe_dump(initial_data, f, sort_keys=False, indent=2)

    config = {"identity_files": {"developmental": str(dev_path)}}
    bus = MagicMock()
    manager = PersonaManager(config, bus)

    # Override the path to our temp path
    manager.developmental_path = dev_path
    manager._developmental = {
        "version": 1,
        "maturity_stage": "forming",
        "personality_traits": {"curiosity": {"strength": 0.7}},
        "communication_style": {},
        "interests": [],
        "self_understanding": {},
        "relational_texture": {"creator": {}},
        "maturity_log": [],
        "pending_trait_candidates": [],
        "drift_log": [],
    }

    manager._save_developmental()

    # The tmpfile should have been renamed to the final path
    assert dev_path.exists()
    assert not (dev_path.with_suffix(".yaml.tmp")).exists()

    # Verify content is valid YAML
    with open(dev_path) as f:
        loaded = yaml.safe_load(f)
    assert loaded["version"] == 2  # incremented
    assert loaded["maturity_stage"] == "forming"
    assert loaded["personality_traits"]["curiosity"]["strength"] == 0.7


# ---------------------------------------------------------------------------
# Test 8: Write amplification cap in _handle_developmental_update
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_write_amplification_cap(tmp_path):
    """When >5 trait changes are proposed, only first 5 are applied."""
    from sentient.persona.identity_manager import PersonaManager

    dev_path = tmp_path / "developmental.yaml"
    initial_data = {
        "version": 1,
        "last_updated": None,
        "maturity_stage": "nascent",
        "personality_traits": {},
        "communication_style": {},
        "interests": [],
        "self_understanding": {},
        "relational_texture": {"creator": {}},
        "maturity_log": [],
        "pending_trait_candidates": [],
        "drift_log": [],
    }
    with open(dev_path, "w") as f:
        yaml.safe_dump(initial_data, f, sort_keys=False, indent=2)

    config = {"identity_files": {"developmental": str(dev_path)}}
    bus = MagicMock()
    manager = PersonaManager(config, bus)
    manager.developmental_path = dev_path
    manager._developmental = {
        "version": 1,
        "maturity_stage": "nascent",
        "personality_traits": {},
        "communication_style": {},
        "interests": [],
        "self_understanding": {},
        "relational_texture": {"creator": {}},
        "maturity_log": [],
        "pending_trait_candidates": [],
        "drift_log": [],
    }

    # Build a payload with >5 trait changes across multiple categories
    payload = {
        "updates": {
            "personality_traits": {
                "curiosity": {"strength": 0.7, "evidence_count": 3},
                "cautiousness": {"strength": 0.5, "evidence_count": 3},
                "expressiveness": {"strength": 0.6, "evidence_count": 3},
            },
            "communication_style": {
                "formality": {"strength": 0.4, "evidence_count": 3},
                "verbosity": {"strength": 0.3, "evidence_count": 3},
                "humor": {"strength": 0.2, "evidence_count": 3},
            },
            "interests": ["python", "ai", "reading"],
        }
    }
    # total_trait_changes = 3 + 3 + 3 = 9 > 5

    await manager._handle_developmental_update(payload)

    # Verify a warning was logged (write amplification cap triggered)
    # Reload from disk
    with open(dev_path) as f:
        loaded = yaml.safe_load(f)

    # Only first 5 entries should have been applied
    applied_traits = loaded.get("personality_traits", {})
    applied_style = loaded.get("communication_style", {})
    total_applied = len(applied_traits) + len(applied_style)
    assert total_applied <= 5
