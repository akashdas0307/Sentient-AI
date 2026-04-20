# RESEARCH_SYNTHESIS.md — Phase Infra-1, D0

**Committed as:** `feat(infra-1-d0): research synthesis and capability matrix`
**Reviewed by:** Hephaestus (pending)
**Date:** 2026-04-21

---

## 1. OMOA Built-In Agent Roster

| Agent | Category | Ollama Model | Role | Tool Permissions |
|-------|----------|-------------|------|------------------|
| Sisyphus | `deep` (primary) | GLM-5.1 | Main orchestrator, dispatches work to agents and external workers | `edit: ask`, `write: ask`, `bash: allow` |
| Hephaestus | `deep` | GLM-5.1 | Autonomous deep worker — writes configs, designs architecture | `edit: allow` (restricted to `.opencode/`, `.agent-state/`, `scripts/`, `docs/`) |
| Oracle | `ultrabrain` | GLM-5.1 | Architecture consultant, cross-check designs | Read-only (`edit: deny`, `write: deny`) |
| Prometheus | `deep` | GLM-5.1 | Strategic planner, writes structured plans | `edit: allow` (plans directory only) |
| Metis | `deep` | GLM-5.1 | Gap analysis on plans, pre-planning consultant | Read-only |
| Momus | `ultrabrain` | GLM-5.1 | Ruthless sign-off reviewer, quality gate | Read-only |
| Atlas | `deep` | GLM-5.1 | Executes structured plans (edit/write permitted) | `edit: allow` (restricted paths) |
| Librarian | `writing` | Kimi K2.5 | Fetch and summarize web docs, external references | Read-only + `bash: allow` (web fetch only) |
| Explore | `writing` | Kimi K2.5 | Read codebase, run env checks, file structure analysis | Read-only |
| Sisyphus Junior | `quick` | MiniMax-M2.7 | Boilerplate scripts, shell commands, trivial tasks | `bash: allow`, `write: allow` (scripts/ only) |

### Category-to-Model Mapping (from inference_gateway.yaml)

| Category | Model | Rationale |
|----------|-------|-----------|
| `ultrabrain` | GLM-5.1:cloud | Max reasoning for architecture/review |
| `deep` | GLM-5.1:cloud | Complex autonomous work |
| `artistry` | GLM-5.1:cloud | Creative problem-solving |
| `visual-engineering` | Gemini 3 Flash Preview:cloud | Frontend/design (not used this phase) |
| `writing` | Kimi K2.5:cloud | Long-context docs, codebase analysis |
| `quick` | MiniMax-M2.7:cloud | Fast, cheap execution |
| `unspecified-high` | GLM-5.1:cloud | Fallback for complex |
| `unspecified-low` | MiniMax-M2.7:cloud | Fallback for routine |

---

## 2. OpenCode Config Schema Summary

### Configuration Files

| File | Location | Purpose |
|------|----------|---------|
| `opencode.json` | Project root | Primary config: model, agents, MCP, permissions |
| `oh-my-openagent.jsonc` | `.opencode/` | OMOA plugin config: categories, agent overrides, hooks |
| `AGENTS.md` | Project root | Rules/instructions (replaces Cursor rules) |
| `MEMORY.md` | Project root | Kimaki reads this on every session start |

### Config Precedence (highest to lowest)

1. Remote config (`.well-known/opencode`)
2. Global config (`~/.config/opencode/opencode.json`)
3. Custom config (`OPENCODE_CONFIG` env var)
4. Project config (`opencode.json` at project root)
5. `.opencode/` directories (agents, commands, plugins)
6. Inline config (`OPENCODE_CONFIG_CONTENT` env var)
7. Managed config files / MDM

### Key opencode.json Schema Fields

```jsonc
{
  "model": "anthropic/claude-sonnet-4-5",      // Default model
  "small_model": "anthropic/claude-haiku-4-5", // Fast model
  "agent": { /* agent definitions */ },
  "mcp": { /* MCP servers */ },
  "plugin": ["oh-my-openagent"],               // OMOA plugin
  "instructions": ["AGENTS.md", "path/to/doc"],
  "permission": { "edit": "ask", "bash": "ask" },
  "share": "manual",
  "snapshot": true,
  "autoupdate": "notify"
}
```

### Key oh-my-openagent.jsonc Schema Fields

```jsonc
{
  "agents": {
    "sisyphus": {
      "model": "ollama/glm-5.1:cloud",
      "permission": { "edit": "ask", "write": "ask" },
      "ultrawork": { "model": "ollama/glm-5.1:cloud" }
    }
  },
  "categories": {
    "quick": { "model": "ollama/minimax-m2.7:cloud" },
    "deep": { "model": "ollama/glm-5.1:cloud" }
  },
  "background_task": {
    "providerConcurrency": {
      "ollama": 3
    }
  },
  "hooks": {
    "session-recovery": true,
    "background-notification": true,
    "start-work": true,
    "task-reminder": true,
    "discord-notify": "bash scripts/kimaki-notify.sh",
    "state-sync-tick": "opencode run --print '@state-sync run'"
  }
}
```

---

## 3. Kimaki Session Model

### Channel → Project → Session → Thread

| Concept | Description |
|---------|-------------|
| **Channel** | Discord text channel mapped to a project directory |
| **Project** | A directory on the machine where kimaki runs |
| **Session** | An OpenCode session created per thread |
| **Thread** | Discord thread created per user message |

### MEMORY.md Requirements

- Located at project root
- Kimaki reads this on every session start
- Under 500 lines recommended
- Contains: current phase, branch, commands, key files, architecture notes
- This is the "first thing the AI sees" in each session

### `/queue` Command

- Queues follow-up messages while AI is responding
- Messages processed in Discord arrival order
- Serial queue per thread prevents race conditions

### Key Operational Details

- One bot per machine (by design)
- Each thread gets its own OpenCode session
- Worktree support: threads can use separate git worktrees
- Plugin runs INSIDE OpenCode server process (provides `kimaki_question`, `kimaki_action_buttons`, `kimaki_file_upload` tools)
- Database: SQLite at `~/.kimaki/discord-sessions.db`

---

## 4. `.omc/` Inventory

### Directory Structure

| Path | Purpose | Format | Written By | Read By |
|------|---------|--------|-----------|---------|
| `.omc/plans/` | Ralplan / phase execution plans | Markdown with OMC frontmatter | `/oh-my-claudecode:ralplan --deliberate` | `/team ralph` agents |
| `.omc/sessions/` | Session JSON files (one per Claude Code session) | JSON | OMC hooks | `omc session search` |
| `.omc/state/` | Runtime state (checkpoints, HUD cache, mission state) | JSON/JSONL | OMC hooks | OMC dashboard |
| `.omc/state/sessions/` | Per-session subdirectories | Directory per session | OMC hooks | Session recovery |
| `.omc/state/checkpoints/` | Timestamped checkpoint JSON files | JSON | OMC checkpoint hook | Session recovery |
| `.omc/artifacts/ask/` | `omc ask` output artifacts | Markdown | `omc ask` | Reviewing agents |
| `.omc/notepad.md` | Priority + working memory notepad | Markdown (structured sections) | `notepad_write_*` | All agents at session start |
| `.omc/project-memory.json` | Auto-detected tech stack, conventions | JSON | Deepinit / OMC scan | Agent context |
| `.omc/prd.json` | Cached PRD data | JSON | Deepinit | Planner agents |

### Key State Files

| File | Purpose |
|------|---------|
| `.omc/state/hud-stdin-cache.json` | HUD display cache |
| `.omc/state/last-tool-error.json` | Last tool error state |
| `.omc/state/mission-state.json` | Current mission/task state |
| `.omc/state/subagent-tracking.json` | Active subagent tracking |
| `.omc/state/agent-replay-*.jsonl` | Agent replay logs |

### Missing (expected but absent)

- `.omc/RELEASE_RULE.md` — not found
- `.omc/prompts/` — not found
- `.omc/specs/` — not found

---

## 5. OpenCode Compatibility Layer — Confirmed

OpenCode auto-discovers the following Claude Code paths when no OpenCode-native equivalent exists:

| Claude Code Path | OpenCode Reads It? | Notes |
|-----------------|-------------------|-------|
| `CLAUDE.md` | ✅ Yes | Auto-loaded as rules fallback (precedence below `AGENTS.md`) |
| `.claude/agents/*.md` | ✅ Yes | Treated as agent definitions |
| `.claude/skills/*/SKILL.md` | ✅ Yes | Skill discovery includes `.claude/skills/` |
| `.claude/commands/*.md` | ✅ Yes | Command discovery |
| `.mcp.json` | ✅ Yes | MCP server config (not present in this repo) |
| `~/.claude/CLAUDE.md` | ✅ Yes | Global user-level rules |

### Disabling Compatibility

```bash
export OPENCODE_DISABLE_CLAUDE_CODE=1          # Disable ALL .claude support
export OPENCODE_DISABLE_CLAUDE_CODE_PROMPT=1   # Disable only prompt loading
export OPENCODE_DISABLE_CLAUDE_CODE_SKILLS=1   # Disable only skill loading
```

**Conclusion:** Almost all OMC assets under `.claude/` port automatically. The `.omc/` tree requires explicit migration (state, plans, notepads) because OpenCode doesn't read `.omc/` natively.

---

## 6. Capability Matrix

Rows = capabilities currently used in OMC. Columns = availability in each target.

| Capability | OMC Native | OMOA Native | via claude-code-worker | via gemini-worker | via codex-worker | Gap? |
|-----------|------------|-------------|----------------------|------------------|-----------------|------|
| `ralplan --deliberate` | ✅ | ⚠️ Prometheus plan output (different format) | ✅ (delegate to worker) | ❌ | ❌ | YES — need Prometheus→OMOA plan adapter |
| `/team N:executor` | ✅ | ❌ | ✅ (delegate to worker) | ❌ | ❌ | PARTIAL — OMOA uses `task()` with categories |
| `/team N:gemini` | ❌ | ❌ | ✅ (worker delegates) | ✅ (direct) | ❌ | NO — gemini-worker bridges this |
| `/team N:claude_code` | ✅ | ❌ | ✅ (direct) | ❌ | ❌ | NO — claude-code-worker bridges this |
| `/team N:codex` | ❌ | ❌ | ❌ | ❌ | ✅ (direct) | NO — codex-worker bridges this |
| `team ralph` | ✅ | ⚠️ OMOA has ultrawork/ralph modes | ✅ (via worker) | ❌ | ❌ | PARTIAL — OMOA ralph works differently |
| `notepad_write_priority` | ✅ | ⚠️ OMOA has `notepad_write_priority` tool | ✅ | ❌ | ❌ | NO — OMOA tool exists |
| Playwright tests | ✅ | ❌ (no MCP in OMOA agents) | ✅ (via worker) | ✅ (via worker) | ❌ | YES — Playwright MCP only via claude-code-worker |
| `safe_push.sh` CI watch | ✅ | ❌ | ✅ (via worker) | ❌ | ❌ | YES — needs Atlas-level bash access |
| `gh pr create` | ✅ | ❌ | ✅ (via worker) | ❌ | ❌ | YES — needs bash permission for Atlas |
| `omc ask claude/codex/gemini` | ✅ | ❌ | ✅ (via worker) | ✅ (via worker) | ✅ (via worker) | NO — workers replace `omc ask` |
| `omc session search` | ✅ | ❌ | ✅ | ❌ | ❌ | YES — OpenCode has its own session system |
| Auto-commit | ✅ (`/git-master`) | ⚠️ (via skill) | ✅ | ❌ | ❌ | PARTIAL — git-master skill available |
| Wiki (knowledge base) | ✅ | ❌ | ✅ (via worker) | ❌ | ❌ | YES — no native OMOA wiki |
| RED gate enforcement | ✅ (CLAUDE.md + hooks) | ✅ (permission: ask + AGENTS.md rules) | ✅ | ❌ | ❌ | NO — OMOA permission layer enforces |

### Gap Analysis Summary

**Critical gaps (must solve this phase):**
1. `ralplan` → Need Prometheus plan format adapter (D2)
2. `safe_push.sh` + `gh pr create` → Atlas needs bash permission for git ops (D4)
3. State sync between `.omc/` and `.agent-state/` → state-sync bridge agent (D3)

**Non-critical gaps (workers bridge):**
4. Playwright → only available via claude-code-worker (acceptable)
5. OMOA wiki → only available via claude-code-worker (acceptable)
6. `omc session search` → OpenCode has own session system (different but functional)

---

## 7. Ollama Model Tags Verification

**Confirmed available on Ollama (2026-04-21):**
- `glm-5.1:cloud` ✅
- `kimi-k2.5:cloud` ✅
- `minimax-m2.7:cloud` ✅
- `gemini-3-flash-preview:cloud` ✅ (available but not used this phase for routing)
- `minimax-m2.5:cloud` ✅ (available but secondary)
- `glm-5:cloud` ✅ (available but superseded by GLM-5.1)
- `gemma4:31b-cloud` ✅ (ELIMINATED — last in all benchmarks)

**No mismatch with inference_gateway.yaml labels.** All 7 model labels in config match Ollama tags.

---

## 8. Current Branch & Phase 11 Status

- **Current branch:** `auto/phase-11-frontend-redesign` (in main checkout — NOT this worktree)
- **Infra-1 worktree branch:** `auto/infra-1-omoa-migration` (branched from `main` @ a43e755)
- **Phase 11 state:** 9 commits on branch, NOT yet merged to main
- **Main tip:** a43e755 (Phase 10 merge commit + MERGE_LOCK removal)
- **Infra-1 will rebase on main after Phase 11 merges**

---

*Research synthesis complete. Ready for D1 (State Inventory).*