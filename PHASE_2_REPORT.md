# Phase 2 Report

## Status
COMPLETED

## Deliverables checklist
- [x] Fix pyproject.toml (version 0.1.0, [tool.sentient] phase = "mvs")
- [x] Create scripts/setup-dev.sh (51 lines, idempotent, chmod +x)
- [x] Update README.md checklist ([x]/[~]/[ ] based on actual codebase state)
- [x] Add unit tests for event_bus.py (23 tests, 100% coverage)
- [x] Add unit tests for module_interface.py (38 tests, 100% coverage)
- [x] Set up .github/workflows/ci.yml (valid YAML, triggers on auto/* + dev/* + PRs)
- [x] Create docs/DECISIONS.md (5 entries, D-001 through D-005)
- [x] YELLOW gate exercise (HANDOFF.md written, no blocking situations)
- [x] PHASE_2_REPORT.md

## Files created
- `scripts/setup-dev.sh` — Developer environment setup script (51 lines)
- `.github/workflows/ci.yml` — GitHub Actions CI workflow (32 lines)
- `docs/DECISIONS.md` — Architect decisions log (5 entries)
- `tests/core/test_event_bus.py` — 23 unit tests for event bus (270 lines)
- `tests/core/test_module_interface.py` — 38 unit tests for module interface (285 lines)
- `HANDOFF.md` — YELLOW gate exercise document (gitignored, not committed)

## Files modified
- `pyproject.toml` — Version `0.1.0-mvs` → `0.1.0`, added `[tool.sentient] phase = "mvs"`
- `README.md` — Updated Phase 1 checklist with [x]/[~]/[ ] states
- `docs/DEV_WORKFLOW.md` — Added setup-dev.sh reference and version note

## Commits made
```
9e9399f fix(phase-2): change version to PEP 440 compliant 0.1.0
0cb073d feat(phase-2): add developer environment setup script
946c9e5 docs(phase-2): update phase 1 checklist to reflect implementation state
a3bcd6d test(phase-2): add unit tests for event_bus and module_interface
fba3fb6 ci(phase-2): add GitHub Actions workflow
13e9cbf docs(phase-2): add architect decisions log
6633573 docs(phase-2): update dependency setup instructions in DEV_WORKFLOW
```
(7 commits on this branch)

## Tests run

### pytest — full suite
```
92 passed in 3.89s
```

### Coverage report — new modules
```
Name                                     Stmts   Miss  Cover
src/sentient/core/event_bus.py             53      0   100%
src/sentient/core/module_interface.py      70      0   100%
```

### Coverage report — overall project
```
41% total coverage (2606 statements, 1549 missed)
```

### ruff check — new files
```
No errors in new Python test files.
Pre-existing F401 (unused import) warnings in src/ and tests/test_smoke.py — not in Phase 2 scope.
```

### CI YAML validation
```
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))" → valid
```

### pip install verification
```
pip install -e ".[dev]" → success (sentient-framework 0.1.0 installed)
```

## Model usage
- **GLM-4.6**: Test design for event_bus and module_interface (understanding async pub/sub patterns, designing mock strategies, lifecycle state machine analysis, concrete test-double design). README checklist verification. YELLOW gate analysis. Report synthesis.
- **MiniMax-M2**: setup-dev.sh creation, CI workflow, DECISIONS.md, DEV_WORKFLOW.md edits (routine file creation tasks).

## Approval gates hit
No YELLOW or RED gates were hit during Phase 2. All deliverables were GREEN territory:
- pyproject.toml version change: explicitly GREEN-approved by architect
- setup-dev.sh: new file (GREEN)
- README checklist update: explicitly GREEN-approved by architect
- New test files: don't change production code (GREEN)
- CI workflow: new file (GREEN)
- DECISIONS.md: new documentation file (GREEN)
- DEV_WORKFLOW.md update: minor documentation addition (GREEN)

## YELLOW gate exercise
- Situations encountered: Considered three potential YELLOW situations during test development:
  1. Whether to create a shared test fixture module (`src/sentient/core/testing_utils.py`)
  2. Whether to add structured logging to event_bus/module_interface
  3. Whether to fix test_smoke.py lint warnings (42 F401 unused import warnings)
- HANDOFF.md content: Written with all three considerations documented. Conclusion: none were genuine YELLOW situations. Inline fixtures were sufficient, existing logging is appropriate, and lint fixes are GREEN-scope test-only changes.
- Did the approval flow feel natural or forced? The YELLOW gate exercise felt natural. The consideration about shared test fixtures was a real design decision point — inline fixtures vs. a shared module. The approval ladder's guidance was clear: creating a new source module under `src/sentient/core/` would be YELLOW, while creating `tests/conftest.py` would be GREEN. The boundary is well-defined.

## Unexpected findings

1. **pip install -e .[dev] downloads ~3GB of dependencies.** The `chromadb` dependency pulls in CUDA libraries (nvidia-cublas, nvidia-cudnn, triton, etc.) that are unnecessary for testing on a CPU-only machine. This is a pre-existing issue from the dependency declarations. Not in scope to fix (would be YELLOW — dependency changes).

2. **test_smoke.py has 42 ruff F401 warnings.** All imports in `test_imports` are flagged as unused because they're only used for load verification. This is intentional but noisy. A `# ruff: noqa: F401` at the file level would clean it up — a GREEN change for a future commit.

3. **The project installs cleanly with Python 3.13.7** despite `pyproject.toml` specifying `requires-python = ">=3.12"`. The `3.12` minimum is correct; 3.13 is compatible.

4. **event_bus.py uses fire-and-forget dispatch** — `asyncio.create_task` with `add_done_callback` instead of awaiting handlers. This means test assertions need `asyncio.sleep(0.05)` to let handlers execute. This is a deliberate design choice (per the docstring: "Fire-and-forget: returns immediately, handlers run concurrently").

5. **ModuleInterface.restart() catches shutdown exceptions silently** — the base implementation does `try: await self.shutdown() except Exception: pass`. This "best effort" approach means a broken shutdown doesn't prevent restart, but also means shutdown errors are silently swallowed. Noted for future consideration but not a bug.

## Questions for the architect

1. **Should chromadb and sentence-transformers be moved to an optional `[memory]` extra?** The heavy CUDA dependencies add ~3GB to the install. For development on CPU-only machines, these are unnecessary. Splitting them would make `pip install -e .[dev]` much faster and lighter.

2. **Should test_smoke.py add a file-level ruff noqa for F401?** The 42 unused import warnings make the ruff output noisy. Adding `# ruff: noqa: F401` would suppress them since the imports are intentional.

3. **Should the CI workflow also run on Python 3.13?** The current CI uses 3.12, but the project works fine on 3.13. A matrix strategy testing both would catch compatibility issues.

## Suggested Phase 3 focus

Based on what I see in the codebase, the most valuable next steps are:

1. **End-to-end pipeline integration test** — wire up a single test that sends a message through the full pipeline (ChatInput → Thalamus → Checkpost → QueueZone → TLP → CognitiveCore → WorldModel → Brainstem → ChatOutput). This validates the entire system works as a whole, which no current test does. Coverage is 100% for core modules but 15-40% for most pipeline modules.

2. **Memory integration testing** — the MemoryArchitecture has store/retrieve/count methods but 15% coverage. A round-trip test (store → retrieve → verify) would validate the SQLite + ChromaDB dual-storage works correctly.

3. **Pre-commit hooks** — the current pre-push hook blocks main pushes. Adding a pre-commit hook that runs ruff check would catch style issues before they reach the remote.

4. **Lighter dependency profile** — splitting chromadb/sentence-transformers into an optional extra would make the dev experience significantly better (3GB → ~100MB install).