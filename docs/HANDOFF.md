# Handoff: Phase 6 Preparation

## Current State

- **Phase 5 COMPLETE** — First boot achieved, real conversation works
- **Branch:** `auto/phase-5-first-boot` (ready for merge)
- **Commits:** 8 on this branch
- **Total tests:** 365 unit + 2 wetware = 367 passing (4 pre-existing test_main.py failures from heavy async tests)
- **Ruff:** 0 errors
- **main.py coverage:** 97% (up from 41%)

## Phase 5 Achievements

- System had its **first real conversation** via GLM-5.1:cloud, MiniMax-M2.7:cloud, Kimi-K2.5:cloud
- Wetware smoke tests **GREEN** (D3)
- Performance baseline measured (D6): 1.4s startup, 31.6s response, 186 MB RSS
- 2 CRITICAL bugs fixed: fixture H0 (missing initialize), Brainstem response extraction

## Known Issues for Phase 6

1. **World Model `revision_requested` dead-ends decisions** — When the model returns this verdict, the decision is neither approved nor re-processed. Need a re-submission loop or fallback to `approved` after N revision attempts.
2. **Episodic memory not populated between turns** — Follow-up conversations don't reference previous exchanges. MemoryArchitecture is not wired into the pipeline.
3. **GLM-5.1:cloud JSON key variance** — Model uses unpredictable key names in `parameters` (text, content, message, content_type, style). Brainstem heuristic (longest string) works but is fragile. Prompt engineering with few-shot example recommended.
4. **4 pre-existing test_main.py failures** — Heavy async tests timeout; new test_main_coverage.py covers same paths at 97% without the issues.
5. **sentence_transformers first-download** — Not tested; could add 30-120s to cold startup on fresh machines.
6. **CLAUDE.md model routing table** — Still references "GLM-4.6" instead of "GLM-5.1:cloud". RED gate — needs creator authorization to update.

## Phase 6 Suggested Focus

| Focus Area | Target | Approach |
|-----------|--------|----------|
| Decision re-submission | Loop on revision_requested | Add max-revision count in World Model handler |
| Memory integration | Episodic memory between turns | Wire MemoryArchitecture into CognitiveCore context |
| Prompt engineering | Stable JSON output from GLM | Add few-shot example to Cognitive Core prompt |
| Full-system startup | Test with Memory + API server | Wetware test with all 12 modules |
| CLAUDE.md model update | Fix routing table | Creator authorization required |

## Repository Status

- **Branch:** `auto/phase-5-first-boot` (active, ready for merge)
- **GitHub auth:** Configured
- **CI:** Uses `scripts/run_tests_safe.sh --cov` for per-directory isolation
- **Pre-push hook:** `scripts/install_hooks.sh`