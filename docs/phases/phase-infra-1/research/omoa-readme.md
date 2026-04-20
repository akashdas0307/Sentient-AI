# Oh My OpenAgent (OMOA) README

> **Security warning: impersonation site**
> **ohmyopencode.com is NOT affiliated with this project.**

## Overview

Oh My OpenCode is a plugin for OpenCode that provides multi-model orchestration, background agents, and advanced agent capabilities.

### Key Features

- **Agents**: Sisyphus (main orchestrator), Prometheus (planner), Oracle (architecture/debugging), Librarian (docs/code search), Explore (fast codebase grep), Multimodal Looker
- **Background Agents**: Run multiple agents in parallel like a real dev team
- **LSP & AST Tools**: Refactoring, rename, diagnostics, AST-aware code search
- **Claude Code Compatibility**: Full hook system, commands, skills, agents, MCPs
- **Built-in MCPs**: websearch (Exa), context7 (docs), grep_app (GitHub search)
- **Session Tools**: List, read, search, and analyze session history
- **Productivity Features**: Ralph Loop, Todo Enforcer, Comment Checker, Think Mode

## Installation

### For Humans

```
Install and configure oh-my-opencode by following the instructions here:
https://raw.githubusercontent.com/code-yeongyu/oh-my-opencode/refs/heads/master/docs/guide/installation.md
```

### For LLM Agents

```bash
curl -s https://raw.githubusercontent.com/code-yeongyu/oh-my-opencode/refs/heads/master/docs/guide/installation.md
```

## Configuration

**Config Locations**: 
- Project: `.opencode/oh-my-opencode.json`
- User: `~/.config/opencode/oh-my-opencode.json`

**JSONC Support**: Comments and trailing commas supported

**Key Config Options**:
- `agents`: Override models, temperatures, prompts, and permissions
- `categories`: Domain-specific task delegation
- `background_task`: Concurrency limits per provider/model
- `disabled_hooks`: Configure which hooks to disable
- `mcp`: Built-in MCP configuration

## Agent Categories

| Category | When Used | Model Chain |
|----------|-----------|-------------|
| `visual-engineering` | Frontend, UI, CSS, design | Gemini 3.1 Pro |
| `ultrabrain` | Maximum reasoning | GPT-5.4 xhigh |
| `deep` | Deep coding, complex logic | GPT-5.4 medium |
| `artistry` | Creative approaches | Gemini 3.1 Pro |
| `quick` | Simple, fast tasks | GPT-5-nano |
| `unspecified-high` | General complex work | Claude Opus 4.7 max |
| `unspecified-low` | General standard work | Claude Sonnet 4.6 |
| `writing` | Text, docs, prose | Gemini 3 Flash |

## State Management

- Config-based state in `opencode.json`
- Agent state via `.opencode/agents/` markdown files
- Skill state via `.opencode/skills/*/SKILL.md`
- Session state managed by OpenCode core

## Compatibility with OMC

OMOA provides feature parity with OMC (oh-my-claudecode) for users migrating from Claude Code to OpenCode:
- Skill system (SKILL.md format)
- Agent definitions (markdown format)
- Hook system compatibility
- Rules/AGENTS.md support
- CLAUDE.md fallback compatibility
