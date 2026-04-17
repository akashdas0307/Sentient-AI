# Documentation Audit Report — Phase 4c

**Audit Date:** 2026-04-17  
**Auditor:** Documentation Auditor (Phase 4c deliverable)  
**Scope:** README.md, SETUP.md, HANDOFF.md, SEASON_LOG.md, CLAUDE.md vs. actual code

---

## Executive Summary

| Document | Stale Claims Found | Severity |
|----------|-------------------|----------|
| README.md | 5 | Medium |
| SETUP.md | 4 | High |
| docs/HANDOFF.md | 3 | Medium |
| docs/SEASON_LOG.md | 1 | Low |
| CLAUDE.md | 2 | Medium |

**Critical Issue:** SETUP.md provides incorrect Ollama model instructions that will cause the system to fail on first boot.

---

## Detailed Findings

### 1. README.md

| Location | Current (Stale) | Actual (Truth) | Impact |
|----------|-----------------|------------------|--------|
| Line 10-13 | References `PRD.md`, `ARCHITECTURE.md`, etc. in root | Files are in `doc/` subdirectory (not `docs/`) | User confusion |
| Line 41 | "Connect a real agent harness (Claw Code or Claude Code)" | Typo: "Claw Code" should be "Claude Code" | Minor embarrassment |
| Line 33 | "Configure your specific LLM providers in `config/inference_gateway.yaml`" | Config now uses Ollama cloud models, not user-specific endpoints | Misleading |
| Phase Checklist (lines 95-170) | Shows many items as incomplete [ ] or partial [~] | Many are now complete per Phase 4a/4b | Outdated perception |

**Specific stale checklist items:**
- Line 105: "Inference Gateway with real LLM calls (litellm integration)" — `[ ]` should be `[x]` (litellm is in pyproject.toml)
- Line 116: "Local LLM classifier (Layer 2)" — `[ ]` but `inference_gateway.yaml` has `thalamus-classifier` configured
- Lines 127, 130, 135, 139: Several `[~]` items likely complete after Phase 4a

---

### 2. SETUP.md

| Location | Current (Stale) | Actual (Truth) | Impact |
|----------|-----------------|------------------|--------|
| Lines 46-56 | Instructs to pull `llama3.2:3b` and `qwen2.5:7b` | System now requires `glm-5.1:cloud`, `minimax-m2.7:cloud`, `kimi-k2.5:cloud` | **HIGH: System will fail** |
| Lines 75-77 | "Only Anthropic is required for MVS" | No cloud API keys required; uses Ollama cloud models | User may unnecessarily purchase API keys |
| Line 100 | `python -m sentient.scripts.init_db` | Correct path exists (`src/sentient/scripts/init_db.py`) | Works, but verify instructions match |
| Lines 136-141 | "For now, open gui/index.html in a browser" | `gui/index.html` is a placeholder per README line 39 | Misleading user expectations |

**Critical Fix Needed:** The Ollama model instructions must be updated to match `config/inference_gateway.yaml`:

```bash
# OLD (in SETUP.md)
ollama pull llama3.2:3b
ollama pull qwen2.5:7b

# NEW (should be)
ollama pull glm-5.1:cloud
ollama pull minimax-m2.7:cloud
ollama pull kimi-k2.5:cloud
```

---

### 3. docs/HANDOFF.md

| Location | Current (Stale) | Actual (Truth) | Impact |
|----------|-----------------|------------------|--------|
| Line 1, 5 | "Phase 4a Substrate Coverage" | Current branch is `auto/phase-4c-recovery` | Misleading about current phase |
| Line 6 | "Branch: `auto/phase-4a-substrate` (active)" | Branch is `auto/phase-4c-recovery` | Stale branch reference |
| Lines 23-33 | Lists Phase 4b goals | Phase 4b is complete (per `PHASE_4b_PROGRESS.md` in docs/phases/) | Outdated planning |

**Note:** There are TWO HANDOFF files:
- `/home/akashdas/Desktop/Sentient-AI/docs/HANDOFF.md` (stale, reviewed above)
- `/home/akashdas/Desktop/Sentient-AI/HANDOFF.md` (root, contains Phase 2 content)

Risk of confusion between these files.

---

### 4. docs/SEASON_LOG.md

| Location | Current (Stale) | Actual (Truth) | Impact |
|----------|-----------------|------------------|--------|
| Lines 33-35 | Phase 4a is "most recent phase" | Phase 4c is active (branch `auto/phase-4c-recovery`) | Chronology incorrect |
| Line 39 | "Last updated: 2026-04-16" | Audit date is 2026-04-17 | Needs update for Phase 4c entry |

Missing: Phase 4b completion entry and Phase 4c start entry.

---

### 5. CLAUDE.md

| Location | Current (Stale) | Actual (Truth) | Impact |
|----------|-----------------|------------------|--------|
| Model Routing Table | "GLM-4.6", "MiniMax-M2", "Kimi K2" | Inference gateway uses "glm-5.1:cloud", "minimax-m2.7:cloud", "kimi-k2.5:cloud" | Model labels don't match config |
| RESOURCE AND PROCESS RULES reference | README line 178 references this section | CLAUDE.md loaded in context but section doesn't exist as named | Documentation cross-ref broken |

**Model Label Mapping Discrepancy:**

| Abstract Label | CLAUDE.md Claims | inference_gateway.yaml Uses |
|----------------|------------------|-------------------------------|
| cognitive-core | GLM-4.6 | glm-5.1:cloud |
| world-model | (not specified) | minimax-m2.7:cloud |
| thalamus-classifier | Kimi K2 | kimi-k2.5:cloud |

---

## Scripts Documentation Gap

The following scripts exist but are NOT documented anywhere:

| Script | Purpose | Where Should Be Documented |
|--------|---------|---------------------------|
| `scripts/run_tests_safe.sh` | Resource-constrained test runner | SETUP.md or new TESTING.md |
| `scripts/check_lazy_imports.sh` | Lazy import verification | SETUP.md (dev section) |
| `scripts/coverage_per_module.sh` | Per-module coverage measurement | SETUP.md (dev section) |
| `scripts/setup-dev.sh` | Developer environment setup | SETUP.md |
| `scripts/install_hooks.sh` | Git hooks installation | SETUP.md |
| `scripts/safe_push.sh` | Safe push with CI monitoring | SETUP.md |

---

## File Path Issues

| Stale Reference | Actual Location | Affected Document |
|-----------------|-----------------|-------------------|
| `PRD.md` (root) | `doc/PRD.md` | README.md line 10 |
| `ARCHITECTURE.md` (root) | `doc/ARCHITECTURE.md` | README.md line 11 |
| `DESIGN_DECISIONS.md` (root) | `doc/DESIGN_DECISIONS.md` | README.md line 12 |
| `CONVERSATION_SUMMARY.md` (root) | `doc/CONVERSATION_SUMMARY.md` | README.md line 13 |

---

## Recommended Fixes Summary

### Immediate (Before Phase 4c Merge)

1. **SETUP.md lines 46-56**: Update Ollama model instructions to use cloud model names
2. **SETUP.md lines 75-77**: Remove "Only Anthropic is required" — clarify Ollama cloud is primary
3. **README.md line 10-13**: Change paths from `X.md` to `doc/X.md`
4. **README.md line 41**: Fix "Claw Code" typo to "Claude Code"

### Before Phase 5

5. **HANDOFF.md**: Consolidate root and docs/ versions; update for Phase 4c
6. **SEASON_LOG.md**: Add Phase 4b completion and Phase 4c start entries
7. **CLAUDE.md**: Update model routing table to match inference_gateway.yaml labels
8. **README.md**: Update Phase 1 checklist based on Phase 4a/4b completions
9. **SETUP.md**: Document scripts (or create TESTING.md)
10. **SETUP.md**: Clarify gui/index.html placeholder status

---

## Verification Checklist

- [ ] SETUP.md Ollama models match inference_gateway.yaml
- [ ] README.md paths point to correct `doc/` subdirectory
- [ ] HANDOFF.md reflects current phase (4c) and branch
- [ ] SEASON_LOG.md includes Phase 4b completion
- [ ] CLAUDE.md model labels match inference_gateway.yaml
- [ ] No "Claw Code" typo remains in any document
- [ ] Scripts are documented

---

## Appendix: Truth Source of Truth

The following files were audited as "source of truth":

| File | Lines | Purpose |
|------|-------|---------|
| `pyproject.toml` | 71 | Dependencies, extras, scripts |
| `src/sentient/main.py` | 227 | Startup sequence, imports |
| `config/inference_gateway.yaml` | 140 | Model labels, endpoints |
| `config/system.yaml` | 163 | Configurable parameters |
| `scripts/run_tests_safe.sh` | 169 | Test runner behavior |
| `scripts/check_lazy_imports.sh` | 72 | Import verification |

All paths verified as absolute paths from `/home/akashdas/Desktop/Sentient-AI/`.
