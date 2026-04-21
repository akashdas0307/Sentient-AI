# OpenCode Skills Documentation

## Skill Discovery

Skills are defined via `SKILL.md` files in skill folders.

## File Locations

- Project: `.opencode/skills/<name>/SKILL.md`
- Global: `~/.config/opencode/skills/<name>/SKILL.md`
- Claude Code compatible: `.claude/skills/<name>/SKILL.md`
- Agent compatible: `.agents/skills/<name>/SKILL.md`

## Frontmatter Fields

Required:
- `name`: 1-64 chars, lowercase alphanumeric with hyphens
- `description`: 1-1024 chars

Optional:
- `license`
- `compatibility`
- `metadata` (string-to-string map)

## Example SKILL.md

```markdown
---
name: git-release
description: Create consistent releases and changelogs
license: MIT
compatibility: opencode
metadata:
  audience: maintainers
  workflow: github
---

## What I do
- Draft release notes from merged PRs
- Propose a version bump

## When to use me
Use this when preparing a tagged release.
```

## Tool Integration

Agents see skills via `skill` tool:
```
<available_skills>
  <skill>
    <name>git-release</name>
    <description>Create consistent releases and changelogs</description>
  </skill>
</available_skills>
```

Load with: `skill({ name: "git-release" })`

## Permissions

```json
{
  "permission": {
    "skill": {
      "*": "allow",
      "pr-review": "allow",
      "internal-*": "deny",
      "experimental-*": "ask"
    }
  }
}
```

## State Management

Skills stored as markdown files in skill directories:
- `.opencode/skills/*/SKILL.md`
- `~/.config/opencode/skills/*/SKILL.md`
- Claude Code compatible: `.claude/skills/*/SKILL.md`
