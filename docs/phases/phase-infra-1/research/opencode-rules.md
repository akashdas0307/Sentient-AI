# OpenCode Rules Documentation

## Overview

Custom instructions via `AGENTS.md` files (similar to Cursor's rules).

## File Locations

### Project Rules
- `AGENTS.md` in project root
- `CLAUDE.md` (Claude Code fallback)

### Global Rules
- `~/.config/opencode/AGENTS.md`
- `~/.claude/CLAUDE.md` (Claude Code fallback)

## Precedence

1. Local `AGENTS.md` (from current directory traversing up)
2. Global `~/.config/opencode/AGENTS.md`
3. Claude Code `~/.claude/CLAUDE.md` (unless disabled)

## Initialize Command

`/init` scans repo, asks targeted questions, creates/updates `AGENTS.md`

## Custom Instructions

In `opencode.json`:
```json
{
  "instructions": ["CONTRIBUTING.md", "docs/guidelines.md", ".cursor/rules/*.md"]
}
```

Remote URLs supported (5s timeout).

## Disabling Claude Code Compatibility

```bash
export OPENCODE_DISABLE_CLAUDE_CODE=1        # Disable all .claude support
export OPENCODE_DISABLE_CLAUDE_CODE_PROMPT=1 # Disable only ~/.claude/CLAUDE.md
export OPENCODE_DISABLE_CLAUDE_CODE_SKILLS=1 # Disable only .claude/skills
```

## Referencing External Files

Use `@filename` syntax in AGENTS.md with explicit instructions:
```
CRITICAL: When you encounter a file reference (e.g., @rules/general.md), 
use your Read tool to load it on a need-to-know basis.
```

## State Management

Rules stored as:
- `AGENTS.md` files (markdown)
- `opencode.json` `instructions` array
- Claude Code compatible: `CLAUDE.md` files
