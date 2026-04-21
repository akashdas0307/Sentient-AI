# OpenCode Config Documentation

## Config Locations & Precedence

1. Remote config (`.well-known/opencode`) - organizational defaults
2. Global config (`~/.config/opencode/opencode.json`)
3. Custom config (`OPENCODE_CONFIG` env var)
4. Project config (`opencode.json` in project)
5. `.opencode` directories (agents, commands, plugins)
6. Inline config (`OPENCODE_CONFIG_CONTENT` env var)
7. Managed config files (macOS: `/Library/Application Support/opencode/`)
8. macOS MDM (`.mobileconfig`) - highest priority

## Format

- JSON or JSONC (JSON with Comments)
- Schema: `https://opencode.ai/config.json`

## Key Schema Options

### Models
```json
{
  "model": "anthropic/claude-sonnet-4-5",
  "small_model": "anthropic/claude-haiku-4-5"
}
```

### Server
```json
{
  "server": {
    "port": 4096,
    "hostname": "0.0.0.0",
    "mdns": true,
    "cors": ["http://localhost:5173"]
  }
}
```

### Agents
```json
{
  "agent": {
    "code-reviewer": {
      "description": "Reviews code for best practices",
      "model": "anthropic/claude-sonnet-4-5",
      "prompt": "You are a code reviewer...",
      "permission": { "edit": "ask" }
    }
  }
}
```

### MCP Servers
```json
{
  "mcp": {}
}
```

### Plugins
```json
{
  "plugin": ["oh-my-opencode"]
}
```

### Instructions
```json
{
  "instructions": ["CONTRIBUTING.md", "docs/guidelines.md"]
}
```

### Permissions
```json
{
  "permission": {
    "edit": "ask",
    "bash": "ask"
  }
}
```

### Experimental
```json
{
  "experimental": {}
}
```

## Variables

- `{env:VARIABLE_NAME}` - environment variables
- `{file:path/to/file}` - file contents

## State Management

Config files are MERGED (not replaced). Later configs override earlier ones for conflicting keys.
