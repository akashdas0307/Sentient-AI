#!/usr/bin/env bash
# Install git hooks for development
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Install pre-push hook
cp "$SCRIPT_DIR/pre-push" "$REPO_ROOT/.git/hooks/pre-push"
chmod +x "$REPO_ROOT/.git/hooks/pre-push"
echo "Installed pre-push hook to .git/hooks/pre-push"

# Install pre-commit hook (guard_critical_files.sh)
PRE_COMMIT_HOOK="$REPO_ROOT/.git/hooks/pre-commit"
GUARD_SCRIPT="$SCRIPT_DIR/guard_critical_files.sh"

if [ -f "$PRE_COMMIT_HOOK" ]; then
    # Check if our guard script is already sourced/linked in the hook
    if ! grep -q "guard_critical_files.sh" "$PRE_COMMIT_HOOK" 2>/dev/null; then
        # Append our guard script call to existing pre-commit hook
        echo "" >> "$PRE_COMMIT_HOOK"
        echo "# Added by install_hooks.sh — critical file protection" >> "$PRE_COMMIT_HOOK"
        echo "bash \"$GUARD_SCRIPT\"" >> "$PRE_COMMIT_HOOK"
        echo "Installed guard_critical_files.sh to existing pre-commit hook"
    else
        echo "guard_critical_files.sh already present in pre-commit hook"
    fi
else
    # No existing pre-commit hook, create one that just calls our guard script
    cp "$GUARD_SCRIPT" "$PRE_COMMIT_HOOK"
    chmod +x "$PRE_COMMIT_HOOK"
    echo "Installed pre-commit hook to .git/hooks/pre-commit"
fi
