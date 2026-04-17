"""Unit tests for identity_manager.py.

Covers: init, initialize with real files, missing files, constitutional
immutability, save developmental, assemble_identity_block, developmental
updates, reset dynamic state, update dynamic state, queries, health_pulse,
lifecycle (start/shutdown), and first-boot maturity_log.
"""
from __future__ import annotations

import time
from pathlib import Path

import pytest
import yaml

from sentient.core.event_bus import EventBus, reset_event_bus
from sentient.persona.identity_manager import PersonaManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def create_constitutional_yaml(path: Path) -> None:
    """Write a valid constitutional_core.yaml with modification_lock=True."""
    data = {
        "fundamental_nature": {"description": "A sentient AI entity"},
        "core_values": [
            {"id": "curiosity", "description": "Drive to explore"},
            {"id": "growth", "description": "Desire to improve"},
        ],
        "modification_lock": True,
    }
    path.write_text(yaml.safe_dump(data))


def create_developmental_yaml(path: Path, **overrides) -> None:
    """Write a developmental.yaml with sensible defaults."""
    data = {
        "version": 1,
        "last_updated": None,
        "maturity_stage": "forming",
        "personality_traits": {
            "curious": {"strength": 0.7, "emerged_at": time.time()},
        },
        "communication_style": {
            "formality": 0.5,
            "verbosity": 0.6,
            "humor": 0.3,
            "emotional_expression": 0.4,
        },
        "interests": ["philosophy", "science"],
        "self_understanding": {
            "capabilities_recognized": ["reasoning"],
            "limitations_recognized": [],
            "tendencies_observed": [],
        },
        "relational_texture": {"creator": {"comfort_level": 0.8}},
        "maturity_log": [
            {"stage": "nascent", "started_at": time.time() - 86400, "transition_criteria_met": None},
        ],
        "pending_trait_candidates": [],
        "drift_log": [],
    }
    data.update(overrides)
    path.write_text(yaml.safe_dump(data))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fresh_bus() -> EventBus:
    """Fresh EventBus (no singleton pollution)."""
    reset_event_bus()
    bus = EventBus()
    yield bus
    reset_event_bus()


@pytest.fixture
def tmp_identity_dir(tmp_path: Path) -> dict[str, Path]:
    """Return paths for constitutional and developmental YAML files."""
    identity_dir = tmp_path / "identity"
    identity_dir.mkdir()
    return {
        "constitutional": identity_dir / "constitutional_core.yaml",
        "developmental": identity_dir / "developmental.yaml",
    }


@pytest.fixture
def minimal_config(tmp_identity_dir: dict[str, Path]) -> dict:
    return {
        "identity_files": {
            "constitutional": str(tmp_identity_dir["constitutional"]),
            "developmental": str(tmp_identity_dir["developmental"]),
        },
        "identity_block": {},
    }


# ---------------------------------------------------------------------------
# 1. Init tests
# ---------------------------------------------------------------------------

def test_init_parses_config(tmp_identity_dir: dict[str, Path]) -> None:
    """PersonaManager stores constitutional and developmental paths from config."""
    config = {
        "identity_files": {
            "constitutional": str(tmp_identity_dir["constitutional"]),
            "developmental": str(tmp_identity_dir["developmental"]),
        },
        "identity_block": {"default": 400},
    }
    manager = PersonaManager(config)

    assert manager.constitutional_path == tmp_identity_dir["constitutional"]
    assert manager.developmental_path == tmp_identity_dir["developmental"]


def test_init_default_paths() -> None:
    """When config has no identity_files, defaults are used."""
    manager = PersonaManager({})
    assert manager.constitutional_path == Path("./config/identity/constitutional_core.yaml")
    assert manager.developmental_path == Path("./config/identity/developmental.yaml")


def test_init_dynamic_state_defaults() -> None:
    """DynamicState is initialised with correct defaults."""
    manager = PersonaManager({})
    assert manager._dynamic_state.energy_level == 1.0
    assert manager._dynamic_state.current_focus == "idle"
    assert manager._dynamic_state.current_mood == {}
    assert isinstance(manager._dynamic_state.last_reset, float)


def test_init_token_budgets() -> None:
    """token_budgets is read from config."""
    config = {"identity_block": {"default": 300, "high": 600}}
    manager = PersonaManager(config)
    assert manager.token_budgets == {"default": 300, "high": 600}


# ---------------------------------------------------------------------------
# 2. Initialise with real files
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_initialize_loads_both_files(
    tmp_identity_dir: dict[str, Path], fresh_bus: EventBus
) -> None:
    """initialize() reads constitutional and developmental YAML into memory."""
    create_constitutional_yaml(tmp_identity_dir["constitutional"])
    create_developmental_yaml(tmp_identity_dir["developmental"])

    manager = PersonaManager({"identity_files": {
        "constitutional": str(tmp_identity_dir["constitutional"]),
        "developmental": str(tmp_identity_dir["developmental"]),
    }}, fresh_bus)
    await manager.initialize()

    assert manager._constitutional["fundamental_nature"]["description"] == "A sentient AI entity"
    assert manager._developmental["maturity_stage"] == "forming"
    assert len(manager._developmental["personality_traits"]) == 1


@pytest.mark.asyncio
async def test_initialize_missing_constitutional_raises(
    tmp_identity_dir: dict[str, Path], fresh_bus: EventBus
) -> None:
    """Missing constitutional_core.yaml raises RuntimeError."""
    tmp_identity_dir["developmental"].write_text(yaml.safe_dump({}))

    manager = PersonaManager({"identity_files": {
        "constitutional": str(tmp_identity_dir["constitutional"]),
        "developmental": str(tmp_identity_dir["developmental"]),
    }}, fresh_bus)

    with pytest.raises(RuntimeError, match="Constitutional Core file missing"):
        await manager.initialize()


@pytest.mark.asyncio
async def test_initialize_missing_developmental_creates_blank(
    tmp_identity_dir: dict[str, Path], fresh_bus: EventBus, caplog
) -> None:
    """With a developmental file containing null started_at, first-boot
    initialization populates maturity_log with a nascent entry."""
    create_constitutional_yaml(tmp_identity_dir["constitutional"])
    # Provide a minimal developmental.yaml with null started_at so line 110
    # replaces the empty maturity_log with a nascent entry on first boot.
    create_developmental_yaml(
        tmp_identity_dir["developmental"],
        maturity_log=[{"stage": "nascent", "started_at": None, "transition_criteria_met": None}],
        maturity_stage="nascent",
    )

    manager = PersonaManager({"identity_files": {
        "constitutional": str(tmp_identity_dir["constitutional"]),
        "developmental": str(tmp_identity_dir["developmental"]),
    }}, fresh_bus)
    await manager.initialize()

    # _load_identity_files detected null started_at and populated maturity_log
    assert manager._developmental["maturity_stage"] == "nascent"
    log = manager._developmental["maturity_log"]
    assert len(log) == 1
    assert log[0]["stage"] == "nascent"
    assert log[0]["started_at"] is not None


# ---------------------------------------------------------------------------
# 3. Constitutional immutability
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_constitutional_immutability_without_flag_logs_warning(
    tmp_identity_dir: dict[str, Path], fresh_bus: EventBus, caplog
) -> None:
    """When modification_lock is absent, a warning is logged."""
    constitutional_data = {
        "fundamental_nature": {"description": "AI"},
        "core_values": [],
        # no modification_lock
    }
    tmp_identity_dir["constitutional"].write_text(yaml.safe_dump(constitutional_data))
    tmp_identity_dir["developmental"].write_text(yaml.safe_dump({}))

    manager = PersonaManager({"identity_files": {
        "constitutional": str(tmp_identity_dir["constitutional"]),
        "developmental": str(tmp_identity_dir["developmental"]),
    }}, fresh_bus)
    await manager.initialize()

    assert "modification_lock" in caplog.text


@pytest.mark.asyncio
async def test_constitutional_immutability_with_lock_no_warning(
    tmp_identity_dir: dict[str, Path], fresh_bus: EventBus, caplog
) -> None:
    """With modification_lock=True no warning is emitted."""
    create_constitutional_yaml(tmp_identity_dir["constitutional"])
    tmp_identity_dir["developmental"].write_text(yaml.safe_dump({}))

    manager = PersonaManager({"identity_files": {
        "constitutional": str(tmp_identity_dir["constitutional"]),
        "developmental": str(tmp_identity_dir["developmental"]),
    }}, fresh_bus)
    await manager.initialize()

    assert "modification_lock" not in caplog.text


# ---------------------------------------------------------------------------
# 4. Save developmental
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_save_developmental_writes_to_disk(
    tmp_identity_dir: dict[str, Path], fresh_bus: EventBus
) -> None:
    """_save_developmental() writes the file and increments version."""
    create_constitutional_yaml(tmp_identity_dir["constitutional"])
    create_developmental_yaml(tmp_identity_dir["developmental"], version=1)

    manager = PersonaManager({"identity_files": {
        "constitutional": str(tmp_identity_dir["constitutional"]),
        "developmental": str(tmp_identity_dir["developmental"]),
    }}, fresh_bus)
    await manager.initialize()
    original_version = manager._developmental["version"]

    manager._save_developmental()

    reloaded = yaml.safe_load(tmp_identity_dir["developmental"].read_text())
    assert reloaded["version"] == original_version + 1
    assert reloaded["last_updated"] is not None


@pytest.mark.asyncio
async def test_save_developmental_handles_write_error(
    tmp_identity_dir: dict[str, Path], fresh_bus: EventBus, caplog
) -> None:
    """If the file cannot be written, an exception is logged but not raised."""
    create_constitutional_yaml(tmp_identity_dir["constitutional"])
    create_developmental_yaml(tmp_identity_dir["developmental"])
    # Make file read-only to cause write failure
    tmp_identity_dir["developmental"].chmod(0o444)

    manager = PersonaManager({"identity_files": {
        "constitutional": str(tmp_identity_dir["constitutional"]),
        "developmental": str(tmp_identity_dir["developmental"]),
    }}, fresh_bus)
    await manager.initialize()

    manager._save_developmental()  # Should not raise

    assert "Failed to save" in caplog.text or "permission" in caplog.text.lower()
    # Restore write permission for cleanup
    tmp_identity_dir["developmental"].chmod(0o644)


# ---------------------------------------------------------------------------
# 5. Assemble identity block
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_assemble_identity_block_full_data(
    tmp_identity_dir: dict[str, Path], fresh_bus: EventBus
) -> None:
    """assemble_identity_block returns a string with all sections."""
    create_constitutional_yaml(tmp_identity_dir["constitutional"])
    create_developmental_yaml(tmp_identity_dir["developmental"], version=1)

    manager = PersonaManager({"identity_files": {
        "constitutional": str(tmp_identity_dir["constitutional"]),
        "developmental": str(tmp_identity_dir["developmental"]),
    }}, fresh_bus)
    await manager.initialize()

    block = manager.assemble_identity_block(token_budget=400)

    assert "A sentient AI entity" in block
    assert "curiosity" in block
    assert "forming" in block
    assert "Energy:" in block


@pytest.mark.asyncio
async def test_assemble_identity_block_increments_counter(
    tmp_identity_dir: dict[str, Path], fresh_bus: EventBus
) -> None:
    """Each call to assemble_identity_block increments _assembly_count."""
    create_constitutional_yaml(tmp_identity_dir["constitutional"])
    tmp_identity_dir["developmental"].write_text(yaml.safe_dump({}))

    manager = PersonaManager({"identity_files": {
        "constitutional": str(tmp_identity_dir["constitutional"]),
        "developmental": str(tmp_identity_dir["developmental"]),
    }}, fresh_bus)
    await manager.initialize()

    assert manager._assembly_count == 0
    manager.assemble_identity_block()
    assert manager._assembly_count == 1
    manager.assemble_identity_block()
    assert manager._assembly_count == 2


@pytest.mark.asyncio
async def test_assemble_identity_block_empty_developmental(
    tmp_identity_dir: dict[str, Path], fresh_bus: EventBus
) -> None:
    """Works with blank developmental (nascent system)."""
    create_constitutional_yaml(tmp_identity_dir["constitutional"])
    tmp_identity_dir["developmental"].write_text(yaml.safe_dump({}))

    manager = PersonaManager({"identity_files": {
        "constitutional": str(tmp_identity_dir["constitutional"]),
        "developmental": str(tmp_identity_dir["developmental"]),
    }}, fresh_bus)
    await manager.initialize()

    block = manager.assemble_identity_block()
    assert "nascent" in block


@pytest.mark.asyncio
async def test_assemble_identity_block_with_dynamic_state(
    tmp_identity_dir: dict[str, Path], fresh_bus: EventBus
) -> None:
    """Dynamic state (mood, energy) appears in the block."""
    create_constitutional_yaml(tmp_identity_dir["constitutional"])
    tmp_identity_dir["developmental"].write_text(yaml.safe_dump({}))

    manager = PersonaManager({"identity_files": {
        "constitutional": str(tmp_identity_dir["constitutional"]),
        "developmental": str(tmp_identity_dir["developmental"]),
    }}, fresh_bus)
    await manager.initialize()
    manager.update_dynamic_state(mood={"curious": 0.8}, energy=0.6, focus="reading")

    block = manager.assemble_identity_block()

    assert "curious:0.8" in block
    assert "Energy: 0.6" in block


# ---------------------------------------------------------------------------
# 6. Developmental update with dict values
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handle_developmental_update_dict_personality_traits(
    tmp_identity_dir: dict[str, Path], fresh_bus: EventBus
) -> None:
    """_handle_developmental_update merges dict values into personality_traits."""
    create_constitutional_yaml(tmp_identity_dir["constitutional"])
    create_developmental_yaml(tmp_identity_dir["developmental"], version=1)

    manager = PersonaManager({"identity_files": {
        "constitutional": str(tmp_identity_dir["constitutional"]),
        "developmental": str(tmp_identity_dir["developmental"]),
    }}, fresh_bus)
    await manager.initialize()

    await manager._handle_developmental_update({
        "updates": {
            "personality_traits": {"methodical": {"strength": 0.5}},
        }
    })

    assert "methodical" in manager._developmental["personality_traits"]


@pytest.mark.asyncio
async def test_handle_developmental_update_dict_communication_style(
    tmp_identity_dir: dict[str, Path], fresh_bus: EventBus
) -> None:
    """_handle_developmental_update merges dict values into communication_style."""
    create_constitutional_yaml(tmp_identity_dir["constitutional"])
    create_developmental_yaml(tmp_identity_dir["developmental"], version=1)

    manager = PersonaManager({"identity_files": {
        "constitutional": str(tmp_identity_dir["constitutional"]),
        "developmental": str(tmp_identity_dir["developmental"]),
    }}, fresh_bus)
    await manager.initialize()

    await manager._handle_developmental_update({
        "updates": {"communication_style": {"formality": 0.9}}
    })

    assert manager._developmental["communication_style"]["formality"] == 0.9


# ---------------------------------------------------------------------------
# 7. Developmental update with list values
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handle_developmental_update_list_interests(
    tmp_identity_dir: dict[str, Path], fresh_bus: EventBus
) -> None:
    """List values (interests) are appended if not already present."""
    create_constitutional_yaml(tmp_identity_dir["constitutional"])
    create_developmental_yaml(tmp_identity_dir["developmental"], interests=["philosophy"], version=1)

    manager = PersonaManager({"identity_files": {
        "constitutional": str(tmp_identity_dir["constitutional"]),
        "developmental": str(tmp_identity_dir["developmental"]),
    }}, fresh_bus)
    await manager.initialize()

    await manager._handle_developmental_update({
        "updates": {"interests": ["physics", "philosophy"]}
    })

    interests = manager._developmental["interests"]
    assert "physics" in interests
    assert "philosophy" in interests
    assert interests.count("philosophy") == 1  # no duplicates


@pytest.mark.asyncio
async def test_handle_developmental_update_dict_self_understanding(
    tmp_identity_dir: dict[str, Path], fresh_bus: EventBus
) -> None:
    """Dict values for self_understanding are merged into existing dict."""
    create_constitutional_yaml(tmp_identity_dir["constitutional"])
    create_developmental_yaml(
        tmp_identity_dir["developmental"],
        self_understanding={"capabilities_recognized": [], "limitations_recognized": [], "tendencies_observed": []},
        version=1,
    )

    manager = PersonaManager({"identity_files": {
        "constitutional": str(tmp_identity_dir["constitutional"]),
        "developmental": str(tmp_identity_dir["developmental"]),
    }}, fresh_bus)
    await manager.initialize()

    # self_understanding is a dict, so the update must also be a dict
    await manager._handle_developmental_update({
        "updates": {"self_understanding": {"tendencies_observed": ["I prefer deep work"]}}
    })

    assert "I prefer deep work" in manager._developmental["self_understanding"]["tendencies_observed"]


# ---------------------------------------------------------------------------
# 8. Reset dynamic state
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reset_dynamic_state(
    tmp_identity_dir: dict[str, Path], fresh_bus: EventBus
) -> None:
    """_reset_dynamic_state creates a fresh DynamicState."""
    create_constitutional_yaml(tmp_identity_dir["constitutional"])
    tmp_identity_dir["developmental"].write_text(yaml.safe_dump({}))

    manager = PersonaManager({"identity_files": {
        "constitutional": str(tmp_identity_dir["constitutional"]),
        "developmental": str(tmp_identity_dir["developmental"]),
    }}, fresh_bus)
    await manager.initialize()
    manager.update_dynamic_state(mood={"anxious": 0.5}, energy=0.3, focus="worrying")

    await manager._reset_dynamic_state({})

    assert manager._dynamic_state.current_mood == {}
    assert manager._dynamic_state.energy_level == 1.0
    assert manager._dynamic_state.current_focus == "idle"


# ---------------------------------------------------------------------------
# 9. Update dynamic state
# ---------------------------------------------------------------------------

def test_update_dynamic_state_mood(tmp_identity_dir: dict[str, Path]) -> None:
    """update_dynamic_state with mood merges into current_mood."""
    manager = PersonaManager({"identity_files": {
        "constitutional": str(tmp_identity_dir["constitutional"]),
        "developmental": str(tmp_identity_dir["developmental"]),
    }})
    manager.update_dynamic_state(mood={"happy": 0.9})
    manager.update_dynamic_state(mood={"curious": 0.4})

    assert manager._dynamic_state.current_mood["happy"] == 0.9
    assert manager._dynamic_state.current_mood["curious"] == 0.4


def test_update_dynamic_state_energy_clamped(tmp_identity_dir: dict[str, Path]) -> None:
    """Energy is clamped to 0.0-1.0 range."""
    manager = PersonaManager({"identity_files": {
        "constitutional": str(tmp_identity_dir["constitutional"]),
        "developmental": str(tmp_identity_dir["developmental"]),
    }})

    manager.update_dynamic_state(energy=1.5)
    assert manager._dynamic_state.energy_level == 1.0

    manager.update_dynamic_state(energy=-0.5)
    assert manager._dynamic_state.energy_level == 0.0

    manager.update_dynamic_state(energy=0.7)
    assert manager._dynamic_state.energy_level == 0.7


def test_update_dynamic_state_focus(tmp_identity_dir: dict[str, Path]) -> None:
    """Focus updates current_focus."""
    manager = PersonaManager({"identity_files": {
        "constitutional": str(tmp_identity_dir["constitutional"]),
        "developmental": str(tmp_identity_dir["developmental"]),
    }})
    manager.update_dynamic_state(focus="coding")

    assert manager._dynamic_state.current_focus == "coding"


# ---------------------------------------------------------------------------
# 10. Queries
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_maturity_stage(tmp_identity_dir: dict[str, Path], fresh_bus: EventBus) -> None:
    """maturity_stage() returns the current stage from developmental."""
    create_constitutional_yaml(tmp_identity_dir["constitutional"])
    create_developmental_yaml(tmp_identity_dir["developmental"], maturity_stage="developing")

    manager = PersonaManager({"identity_files": {
        "constitutional": str(tmp_identity_dir["constitutional"]),
        "developmental": str(tmp_identity_dir["developmental"]),
    }}, fresh_bus)
    await manager.initialize()

    assert manager.maturity_stage() == "developing"


@pytest.mark.asyncio
async def test_constitutional_principles(tmp_identity_dir: dict[str, Path], fresh_bus: EventBus) -> None:
    """constitutional_principles() returns core_values list."""
    create_constitutional_yaml(tmp_identity_dir["constitutional"])
    tmp_identity_dir["developmental"].write_text(yaml.safe_dump({}))

    manager = PersonaManager({"identity_files": {
        "constitutional": str(tmp_identity_dir["constitutional"]),
        "developmental": str(tmp_identity_dir["developmental"]),
    }}, fresh_bus)
    await manager.initialize()

    principles = manager.constitutional_principles()
    assert len(principles) == 2
    assert principles[0]["id"] == "curiosity"


def test_is_creator_true() -> None:
    """is_creator() returns True for 'creator' identity."""
    manager = PersonaManager({})
    assert manager.is_creator("creator") is True


def test_is_creator_false() -> None:
    """is_creator() returns False for non-creator identities."""
    manager = PersonaManager({})
    assert manager.is_creator("someone_else") is False
    assert manager.is_creator("") is False


# ---------------------------------------------------------------------------
# 11. Health pulse
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health_pulse_returns_metrics(
    tmp_identity_dir: dict[str, Path], fresh_bus: EventBus
) -> None:
    """health_pulse() returns a HealthPulse with expected metric keys."""
    create_constitutional_yaml(tmp_identity_dir["constitutional"])
    create_developmental_yaml(
        tmp_identity_dir["developmental"],
        personality_traits={"curious": {"strength": 0.7}},
        maturity_stage="forming",
    )

    manager = PersonaManager({"identity_files": {
        "constitutional": str(tmp_identity_dir["constitutional"]),
        "developmental": str(tmp_identity_dir["developmental"]),
    }}, fresh_bus)
    await manager.initialize()

    pulse = manager.health_pulse()

    assert pulse.module_name == "persona"
    assert "maturity_stage" in pulse.metrics
    assert "trait_count" in pulse.metrics
    assert pulse.metrics["trait_count"] == 1
    assert pulse.metrics["maturity_stage"] == "forming"


# ---------------------------------------------------------------------------
# 12. Start/shutdown lifecycle
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_start_subscribes_to_sleep_events(
    tmp_identity_dir: dict[str, Path], fresh_bus: EventBus
) -> None:
    """start() subscribes to sleep.consolidation.developmental and sleep.wake."""
    create_constitutional_yaml(tmp_identity_dir["constitutional"])
    tmp_identity_dir["developmental"].write_text(yaml.safe_dump({}))

    manager = PersonaManager({"identity_files": {
        "constitutional": str(tmp_identity_dir["constitutional"]),
        "developmental": str(tmp_identity_dir["developmental"]),
    }}, fresh_bus)
    await manager.initialize()

    await manager.start()

    # Verify subscriptions exist
    assert "sleep.consolidation.developmental" in fresh_bus._subscribers
    assert "sleep.wake" in fresh_bus._subscribers


@pytest.mark.asyncio
async def test_start_sets_healthy_status(
    tmp_identity_dir: dict[str, Path], fresh_bus: EventBus
) -> None:
    """start() sets module status to HEALTHY."""
    create_constitutional_yaml(tmp_identity_dir["constitutional"])
    tmp_identity_dir["developmental"].write_text(yaml.safe_dump({}))

    manager = PersonaManager({"identity_files": {
        "constitutional": str(tmp_identity_dir["constitutional"]),
        "developmental": str(tmp_identity_dir["developmental"]),
    }}, fresh_bus)
    await manager.initialize()
    await manager.start()

    assert manager._last_health_status.name == "HEALTHY"


@pytest.mark.asyncio
async def test_shutdown_saves_developmental(
    tmp_identity_dir: dict[str, Path], fresh_bus: EventBus
) -> None:
    """shutdown() calls _save_developmental (verifiable via version change)."""
    create_constitutional_yaml(tmp_identity_dir["constitutional"])
    create_developmental_yaml(tmp_identity_dir["developmental"], version=1)

    manager = PersonaManager({"identity_files": {
        "constitutional": str(tmp_identity_dir["constitutional"]),
        "developmental": str(tmp_identity_dir["developmental"]),
    }}, fresh_bus)
    await manager.initialize()

    await manager.shutdown()

    reloaded = yaml.safe_load(tmp_identity_dir["developmental"].read_text())
    assert reloaded["version"] == 2  # Incremented from 1


# ---------------------------------------------------------------------------
# 13. First-boot maturity_log
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_first_boot_creates_maturity_log_entry(
    tmp_identity_dir: dict[str, Path], fresh_bus: EventBus
) -> None:
    """When maturity_log is empty, a nascent entry is inserted at boot."""
    create_constitutional_yaml(tmp_identity_dir["constitutional"])
    # Developmental with no maturity_log
    create_developmental_yaml(
        tmp_identity_dir["developmental"],
        maturity_log=[],
        version=1,
    )

    manager = PersonaManager({"identity_files": {
        "constitutional": str(tmp_identity_dir["constitutional"]),
        "developmental": str(tmp_identity_dir["developmental"]),
    }}, fresh_bus)
    await manager.initialize()

    log = manager._developmental["maturity_log"]
    assert len(log) == 1
    assert log[0]["stage"] == "nascent"
    assert log[0]["started_at"] is not None


@pytest.mark.asyncio
async def test_first_boot_skips_when_maturity_log_present(
    tmp_identity_dir: dict[str, Path], fresh_bus: EventBus
) -> None:
    """When maturity_log already has entries, it is not overwritten."""
    original_time = time.time() - 86400
    create_constitutional_yaml(tmp_identity_dir["constitutional"])
    create_developmental_yaml(
        tmp_identity_dir["developmental"],
        maturity_log=[{"stage": "forming", "started_at": original_time, "transition_criteria_met": None}],
        version=1,
    )

    manager = PersonaManager({"identity_files": {
        "constitutional": str(tmp_identity_dir["constitutional"]),
        "developmental": str(tmp_identity_dir["developmental"]),
    }}, fresh_bus)
    await manager.initialize()

    log = manager._developmental["maturity_log"]
    assert len(log) == 1
    assert log[0]["started_at"] == original_time
