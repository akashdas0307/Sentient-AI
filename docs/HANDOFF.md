# Handoff — Phase Infra-1 (OMOA Migration)

## Status
**Phase Infra-1 is COMPLETE.** Awaiting manual review and merge.

## Branch
`auto/infra-1-omoa-migration` — ready for PR review.

## Summary
Phase Infra-1 migrates orchestration authority from OMC (Claude Code) to OMOA (OpenCode). OMC remains as a delegated worker backend (`@claude-code-worker`). The unified `.agent-state/` tree is now the source of truth for cross-backend state.

## Default Orchestrator
**OMOA Sisyphus on OpenCode via Discord/Kimaki.** OMC Claude Code is now `@claude-code-worker` for team-ralph pipeline work.

## Delegation Cheat Sheet
| Discord Message | Effect |
|-----------------|--------|
| `list Python files in src/` | Explore agent (writing category) |
| `ultrabrain: analyze WorldModelVerdict risk` | Oracle (GLM-5.1) |
| `@claude-code-worker run ruff check` | Claude CLI via OMC ultrawork |
| `@gemini-worker review MEMORY.md` | Gemini CLI review |
| `@codex-worker generate a function` | Codex CLI code gen |
| `@state-sync run` | Sync .omc/ ↔ .agent-state/shared/ |

## RED Gate
Enforced at 4 layers:
1. OMOA permission config (`edit: ask`, `write: ask` for Sisyphus/Atlas)
2. OpenCode rules (`AGENTS.md`)
3. Claude Code compat rules (`CLAUDE.md`)
4. Bridge agent contracts (all 4 workers explicitly forbid editing production code)

## Key Files Created This Phase
| File | Purpose |
|------|---------|
| `.opencode/oh-my-openagent.jsonc` | OMOA agent → model routing, categories, hooks |
| `.opencode/opencode.json` | OpenCode config (default agent, MCP, instructions) |
| `.opencode/agent/claude-code-worker.md` | Claude CLI bridge subagent |
| `.opencode/agent/gemini-worker.md` | Gemini CLI bridge subagent |
| `.opencode/agent/codex-worker.md` | Codex CLI bridge subagent |
| `.opencode/agent/state-sync.md` | State sync daemon |
| `AGENTS.md` | OpenCode-native project rules |
| `MEMORY.md` | Kimaki auto-load project context |
| `scripts/migrate-state.sh` | Idempotent migration script |
| `scripts/kimaki-notify.sh` | Discord webhook notification script |
| `scripts/test-bridge-agents.sh` | Bridge agent smoke tests |
| `.agent-state/` (gitignored) | Unified state tree (omc/, omoa/, shared/) |
| `.env` (gitignored) | OMC_STATE_DIR added |
| `.gitignore` | Updated for .agent-state/, .omc.backup-* |

## Key Documentation
| File | Purpose |
|------|---------|
| `docs/phases/phase-infra-1/RESEARCH_SYNTHESIS.md` | D0: OMOA capability matrix |
| `docs/phases/phase-infra-1/STATE_INVENTORY.md` | D1: .omc/ and .claude/ inventory |
| `docs/phases/phase-infra-1/UNIFIED_STATE_TREE.md` | D2: .agent-state/ design |
| `docs/phases/phase-infra-1/KIMAKI_SETUP.md` | D5: Kimaki integration guide |
| `docs/phases/phase-infra-1/VERIFICATION_REPORT.md` | D6: 4/9 pass, 5 deferred |

## Next Steps (Phase 12)
- `WorldModelVerdict` Pydantic validation hardening
- Idle-time sleep trigger
- Long-conversation stress test
- Bundle optimization
- Mobile support investigation