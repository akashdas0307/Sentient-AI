#!/usr/bin/env bash
# Install git hooks for development
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cp "$SCRIPT_DIR/pre-push" "$REPO_ROOT/.git/hooks/pre-push"
chmod +x "$REPO_ROOT/.git/hooks/pre-push"
echo "Installed pre-push hook to .git/hooks/pre-push"
