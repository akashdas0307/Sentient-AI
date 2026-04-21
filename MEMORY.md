# MEMORY.md — Sentient AI Framework (Kimaki Auto-Load)

## Current Phase
- Phase 10: COMPLETE (Aliveness Audit — daydream fix, sleep debug, harness verified)
- Phase 11: Frontend Redesign (HeroUI v3, 8 routes — in progress/merging)
- **Infra-1: OMOA Migration (ACTIVE)** — OpenCode as primary orchestrator

## Branch
`auto/infra-1-omoa-migration` (branched from main @ a43e755)

## Tests
- 58+ API tests passing (unit + integration)
- CI green on main
- Wetware tests: require `pytest -m wetware` (Ollama needed)

## Architecture
Thalamus → Prajñā (Checkpost → Queue Zone → TLP → Cognitive Core → World Model) → Brainstem
8 frontend routes: Chat, Modules, Memory, Graph, Sleep, Events, Gateway, Identity
WebSocket at `/ws` for real-time events + chat
Model routing: GLM-5.1 (reasoning), Kimi K2.5 (long-context), MiniMax-M2.7 (fast)

## RED Gate
NEVER edit `src/sentient/**`, `tests/**`, or `frontend/src/**` directly.
Delegate code changes to `@claude-code-worker`, `@gemini-worker`, or `@codex-worker`.

## Common Commands
- `ulw` — ultrawork mode (deep execution)
- `@claude-code-worker` — delegate to Claude Code via OMC
- `@gemini-worker` — delegate to Gemini CLI
- `@codex-worker` — delegate to Codex CLI
- `@oracle` — architecture consultation (GLM-5.1)
- `/queue` — queue follow-up messages in Kimaki

## Key Files
- `CLAUDE.md` — OMC session instructions (auto-read by compat layer)
- `AGENTS.md` — OpenCode-native rules (worker backends, RED gate)
- `config/inference_gateway.yaml` — Ollama model label mapping (9 labels)
- `.agent-state/shared/` — Cross-backend unified state tree
- `.opencode/` — OpenCode + OMOA configuration
- `frontend/src/` — React 19 + HeroUI v3 + Zustand 5 (FROZEN this phase)
- `src/sentient/api/server.py` — Backend API (DO NOT MODIFY this phase)

## Orchestration
Default orchestrator: OMOA Sisyphus on OpenCode via Discord/Kimaki
OMC remains as `@claude-code-worker` for team-ralph pipeline work

## Safe Commands
- `bash scripts/run_tests_safe.sh` — safe test runner (checks RAM first)
- `bash scripts/safe_push.sh` — push with CI watch
- `bash scripts/migrate-state.sh` — migration script (--dry-run available)
- `bash scripts/test-bridge-agents.sh` — bridge agent smoke tests
- `ruff check src/ tests/` — lint

## Discord PASS/BLOCKED
Post after each sub-phase: `D(N) COMPLETE · <summary> · Awaiting PASS`
YELLOW: consult Akash · RED: stop immediately