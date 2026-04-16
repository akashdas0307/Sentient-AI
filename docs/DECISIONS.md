# Architect Decisions Log

## D-001 (Phase 2): README checklist should reflect reality
**Date:** 2026-04-16
**Question from Phase 1 Report #1**
**Decision:** Update the Phase 1 development checklist in README.md to reflect actual implementation state.
**Rationale:** A misleading checklist causes future contributors to redo work or assume things are missing. Marking items with `[x]` (implemented + tested), `[~]` (implemented but untested), or `[ ]` (not implemented) gives an accurate picture.

## D-002 (Phase 2): pyproject.toml version → 0.1.0
**Date:** 2026-04-16
**Question from Phase 1 Report #2**
**Decision:** Change version from `0.1.0-mvs` to `0.1.0` (PEP 440 compliant). Preserve MVS label as `[tool.sentient] phase = "mvs"`.
**Rationale:** Non-PEP-440 version prevents `pip install -e .[dev]` from working. The `-mvs` suffix is not a valid local version identifier. Keeping the phase label in a custom tool section preserves the information without breaking packaging.

## D-003 (Phase 2): doc/ vs docs/ split confirmed
**Date:** 2026-04-16
**Question from Phase 1 Report #3**
**Decision:** Both directories coexist. `doc/` is authoritative design docs (PRD, ARCHITECTURE, DESIGN_DECISIONS). `docs/` is developer artifacts (workflow, templates, inventory).
**Rationale:** The two directories serve different audiences and purposes. Merging would risk conflating immutable design documents with mutable developer guides.

## D-004 (Phase 2): inference_gateway.yaml model names deferred
**Date:** 2026-04-16
**Question from Phase 1 Report #5**
**Decision:** Do not modify inference_gateway.yaml. Add a single-line comment near the models section noting placeholder status. Resolve in a dedicated routing-redesign phase.
**Rationale:** Model names are configuration, not code. Changing them without a broader routing strategy review could create inconsistencies. The current placeholder approach is intentional forward-compatibility.

## D-005 (Phase 2): scripts/setup-dev.sh approved
**Date:** 2026-04-16
**Question from Phase 1 Report #4**
**Decision:** Create `scripts/setup-dev.sh` for consistent developer environment setup.
**Rationale:** The project lacks a standard setup mechanism. A small idempotent script removes the "works on my machine" problem and makes CI configuration straightforward.