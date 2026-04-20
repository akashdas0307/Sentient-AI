# AGENTS.md — OpenCode-Native Rules for Sentient AI Framework

This file provides OpenCode-native project rules. It supplements `CLAUDE.md` (auto-read via Claude Code compatibility layer).

## Orchestrator Identity

The primary orchestrator is **OMOA Sisyphus** running on OpenCode via Kimaki (Discord bridge). OMC (oh-my-claudecode on Claude Code) is preserved as a delegated worker backend.

## Worker Backends

| Backend | Agent Name | CLI | Best For |
|---------|-----------|-----|----------|
| OMC (Claude Code) | `@claude-code-worker` | `claude --dangerously-skip-permissions` | Code changes via team-ralph, Playwright tests, CI |
| Gemini | `@gemini-worker` | `gemini --prompt` | Research, review, architecture analysis |
| Codex | `@codex-worker` | `codex` | Code generation, function synthesis |
| OMOA-native | various | `task()` categories | Planning, design, review, exploration |

## Model Routing (Ollama Cloud)

| Category | Model | Use For |
|----------|-------|---------|
| `ultrabrain` | GLM-5.1:cloud | Architecture, debugging, review |
| `deep` | GLM-5.1:cloud | Complex config design, state architecture |
| `writing` | Kimi K2.5:cloud | Documentation, research, codebase analysis |
| `quick` | MiniMax-M2.7:cloud | Trivial tasks, boilerplate, shell |
| `visual-engineering` | Gemini 3 Flash:cloud | Frontend, UI (not used this phase) |

## State Tree

All cross-backend state lives in `.agent-state/`:

```
.agent-state/
├── omc/          ← OMC state (OMC_STATE_DIR points here)
├── omoa/         ← OMOA session artifacts
└── shared/       ← Cross-backend shared state
    ├── plans/    ← Unified plans
    ├── notepad/  ← priority.md + working.md
    ├── memory.md ← Symlinked to MEMORY.md at root
    ├── claims/   ← File-lock claims
    └── results/   ← Worker result JSON
```

## RED Gate (Inherited from 11 Phases of History)

You NEVER directly edit `src/sentient/**`, `tests/**`, or `frontend/src/**`. For code changes, delegate to `@claude-code-worker`, `@gemini-worker`, or `@codex-worker`. The 8 frontend routes (Chat, Modules, Memory, Graph, Sleep, Events, Gateway, Identity) and the `/ws` WebSocket contract are frozen — the Phase 11 preservation contract still applies.

### Permission Enforcement

Sisyphus and Atlas have `edit: ask` and `write: ask` in the OMOA config. This means any attempt to edit/write triggers an approval prompt. Do NOT bypass this — it enforces the RED gate at the tool layer.

## Approval Ladder

- **GREEN**: New files in `.opencode/`, `.agent-state/`, `scripts/`, `docs/`; typo fixes; docstring additions
- **YELLOW**: New dependencies; config schema changes; cross-module refactors; anything touching `inference_gateway.py`
- **RED**: Changes to `src/sentient/**`, `tests/**`, `frontend/src/**` (delegate to workers); changes to `CLAUDE.md`, `PRD.md`, `DESIGN_DECISIONS.md`; `.env` secrets; `git push` to main

## PASS/BLOCKED Discord Pattern

After each sub-phase deliverable, post to Discord:
- `D(N) COMPLETE · <summary> · Awaiting PASS` — signals completion, waits for Akash
- `YELLOW GATE · <reason>` — consult Akash before proceeding
- `RED GATE · <reason>` — stop immediately

## Key Files

| File | Purpose |
|------|---------|
| `CLAUDE.md` | OMC session instructions (auto-read by compat layer) |
| `AGENTS.md` | This file — OpenCode-native rules |
| `MEMORY.md` | Kimaki auto-loaded project context |
| `config/inference_gateway.yaml` | Ollama model label mapping |
| `.agent-state/shared/` | Cross-backend shared state |
| `docs/phases/phase-infra-1/` | Infra-1 phase documentation |

## Common Workflows

1. **Code change needed**: `@claude-code-worker <task>` → delegate to OMC
2. **Research/review**: `@gemini-worker <task>` → delegate to Gemini
3. **Code generation**: `@codex-worker <task>` → delegate to Codex
4. **Architecture question**: `@oracle <question>` → consult Oracle (GLM-5.1)
5. **Plan review**: Pass to Momus for sign-off
6. **State sync**: `@state-sync` runs automatically on hooks