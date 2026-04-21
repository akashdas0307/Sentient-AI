# OpenCode Agents Documentation

## Agent Types

### Primary Agents
- **Build**: Default agent with all tools enabled
- **Plan**: Restricted agent (file edits and bash set to "ask")

### Subagents
- **General**: Research complex questions, full tool access
- **Explore**: Fast, read-only codebase exploration

### Hidden System Agents
- **Compaction**: Auto-compacts long context
- **Title**: Generates session titles
- **Summary**: Creates session summaries

## Agent Configuration

### JSON Config
```json
{
  "agent": {
    "build": {
      "mode": "primary",
      "model": "anthropic/claude-sonnet-4-20250514",
      "tools": { "write": true, "edit": true, "bash": true }
    },
    "plan": {
      "mode": "primary",
      "model": "anthropic/claude-haiku-4-20250514",
      "tools": { "write": false, "edit": false, "bash": false }
    },
    "code-reviewer": {
      "description": "Reviews code for best practices",
      "mode": "subagent",
      "model": "anthropic/claude-sonnet-4-20250514",
      "prompt": "You are a code reviewer..."
    }
  }
}
```

### Markdown Files
- Global: `~/.config/opencode/agents/*.md`
- Per-project: `.opencode/agents/*.md`

## Options

| Option | Description |
|--------|-------------|
| description | Required - what agent does |
| mode | `primary`, `subagent`, or `all` |
| temperature | 0.0-1.0 (randomness) |
| steps | Max iterations before stopping |
| model | Override default model |
| permission | Tool permissions (ask/allow/deny) |
| hidden | Hide from @ autocomplete |
| color | UI color (hex or theme color) |
| top_p | Alternative to temperature |

## State Management

Agents stored as:
- JSON in `opencode.json` `agent` section
- Markdown files in `.opencode/agents/` or `~/.config/opencode/agents/`
