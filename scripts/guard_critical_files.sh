#!/usr/bin/env bash
# guard_critical_files.sh — pre-commit hook to prevent deletion of protected files
# Protected paths: config/**, src/sentient/**, frontend/src/**, pyproject.toml,
# README.md, SETUP.md, CLAUDE.md, docs/phases/**, data/

set -euo pipefail

# Get list of files staged for deletion
deleted_files=$(git diff --diff-filter=D --name-only --cached)

if [ -z "$deleted_files" ]; then
    exit 0
fi

# Protected path patterns
protected_patterns=(
    "config/"
    "src/sentient/"
    "frontend/src/"
    "pyproject.toml"
    "README.md"
    "SETUP.md"
    "CLAUDE.md"
    "docs/phases/"
    "data/"
)

# Check each deleted file against protected patterns
violations=()
for file in $deleted_files; do
    for pattern in "${protected_patterns[@]}"; do
        case "$file" in
            "$pattern"*)
                violations+=("$file")
                break
                ;;
        esac
    done
done

if [ ${#violations[@]} -gt 0 ]; then
    echo "ERROR: Attempting to delete protected files:" >&2
    for v in "${violations[@]}"; do
        echo "  - $v" >&2
    done
    echo "" >&2
    echo "Deletion of protected files is not allowed." >&2
    echo "Use --no-verify only with explicit creator authorization." >&2
    exit 1
fi

exit 0
