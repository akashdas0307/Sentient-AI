# OMC Reference Documentation

Complete reference for oh-my-claudecode.

## Agents (29 Total)

| Domain | LOW (Haiku) | MEDIUM (Sonnet) | HIGH (Opus) |
|--------|-------------|-----------------|-------------|
| Analysis | architect-low | architect-medium | architect |
| Execution | executor-low | executor | executor-high |
| Search | explore | - | explore-high |
| Research | - | document-specialist | - |
| Frontend | designer-low | designer | designer-high |
| Docs | writer | - | - |
| Visual | - | vision | - |
| Planning | - | - | planner |
| Critique | - | - | critic |
| Pre-Planning | - | - | analyst |
| Testing | - | qa-tester | - |
| Tracing | - | tracer | - |
| Security | security-reviewer-low | - | security-reviewer |
| Build | - | debugger | - |
| TDD | - | test-engineer | - |
| Code Review | - | - | code-reviewer |
| Data Science | - | scientist | scientist-high |
| Git | - | git-master | - |
| Simplification | - | - | code-simplifier |

## Skills (35 Total)

Key skills: ai-slop-cleaner, ask, autoresearch, autopilot, cancel, ccg, deep-dive, deep-interview, deepinit, external-context, hud, ralph, team, trace, ultraqa, ultrawork, visual-verdict, wiki

## Hooks System

20 hook scripts across 11 Claude Code lifecycle events:
- UserPromptSubmit, SessionStart, PreToolUse, PermissionRequest, PostToolUse, PostToolUseFailure, SubagentStart, SubagentStop, PreCompact, Stop, SessionEnd

## State Management

- Default: `{worktree}/.omc/`
- Centralized: `$OMC_STATE_DIR/{project-id}/`

## CLI Commands

- `omc ask claude|codex|gemini <prompt>`
- `omc team N:agent <task>`
- `omc session search <query>`

## Config Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| OMC_STATE_DIR | unset | Centralized state directory |
| OMC_PARALLEL_EXECUTION | true | Parallel agent execution |
| DISABLE_OMC | unset | Disable all OMC hooks |
| OMC_SKIP_HOOKS | unset | Skip specific hooks |
