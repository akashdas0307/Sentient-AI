# USAGE.md — Sentient AI Framework Discord & Agent Guide

## Quick Reference: Discord Commands

| Command | Effect | Backend |
|---------|--------|---------|
| `<natural language>` | Default routing to OMOA Sisyphus | OpenCode (GLM-5.1) |
| `ulw` or `ultrawork` | Deep execution mode | OpenCode (GLM-5.1) |
| `@claude-code-worker <task>` | Delegate to Claude Code via OMC | Claude CLI (Sonnet 4.6) |
| `@gemini-worker <task>` | Delegate to Gemini for research/review | Gemini CLI (2.5 Pro) |
| `@codex-worker <task>` | Delegate to Codex for code generation | Codex CLI |
| `@oracle <question>` | Architecture consultation | GLM-5.1 (ultrabrain) |
| `/queue` | Queue follow-up messages in Kimaki | Kimaki |
| Send as file | Bypass Discord character limits | All |

## Decision Tree: Which Backend?

```
Need to edit src/sentient/**, tests/**, or frontend/src/** ?
  → @claude-code-worker (only backend with edit access)

Need research/review of docs or code?
  → @gemini-worker

Need code generation or quick function?
  → @codex-worker (or "quick" category)

Need architecture decision or complex logic?
  → @oracle (ultrabrain)

Need planning or gap analysis?
  → @metis (deep) → @momus (ultrabrain review)

Need boilerplate, shell commands, trivial edits?
  → "quick" category → MiniMax-M2.7

Need documentation or cross-module analysis?
  → "writing" category → Kimi K2.5
```

## State Tree Architecture

```
.agent-state/
├── omc/          ← OMC state (OMC_STATE_DIR points here)
│   ├── plans/    ← Phase execution plans
│   ├── state/    ← Checkpoints, mission state
│   ├── sessions/ ← 93+ session JSONs
│   └── artifacts/← omc ask outputs
├── omoa/         ← OMOA session artifacts
│   └── logs/     ← Per-session logs
└── shared/       ← Cross-backend shared state
    ├── plans/    ← Unified plans (mirrored from OMC)
    ├── notepad/  ← priority.md + working.md
    ├── memory.md ← Symlinked to MEMORY.md at root
    ├── claims/   ← File-lock claims (10 min TTL)
    └── results/  ← Worker result JSON
```

## RED Gate

You NEVER directly edit `src/sentient/**`, `tests/**`, or `frontend/src/**`. These are frozen for this phase:

1. All 8 frontend routes (Chat, Modules, Memory, Graph, Sleep, Events, Gateway, Identity)
2. The `/ws` WebSocket contract
3. `src/sentient/api/server.py`

If you need code changes, delegate to `@claude-code-worker`.

## Troubleshooting

### Tunnel Down
Kimaki not responding → restart: `npx -y kimaki@latest`
Check logs: `~/.kimaki/kimaki.log`

### Session Stuck
Bot responds to other threads but not yours → kill stale OpenCode process; Kimaki auto-restarts

### Tokens Exhausted
Empty/truncated responses → check Ollama: `curl localhost:11434/api/tags`

### Agent Loop
AI repeating → send "stop" or "cancel" to interrupt current session

### Stale Claim
Worker reports "file locked" → claims auto-expire after 10 min, or `rm .agent-state/shared/claims/*.claim`

## Files You Should Know

| File | When to Check |
|------|---------------|
| `CLAUDE.md` | OMC rules (auto-read by compat layer) |
| `AGENTS.md` | OpenCode-native rules (you are here!) |
| `MEMORY.md` | Kimaki auto-load context (phase state, arch, RED gate) |
| `config/inference_gateway.yaml` | Ollama model label mapping |
| `.agent-state/shared/` | Cross-backend shared state |
| `docs/phases/phase-infra-1/` | Infra-1 phase documentation |