#!/usr/bin/env bash
# safe_push.sh — push with CI feedback loop
# Usage: ./scripts/safe_push.sh [remote] [branch]
# Pushes to remote, then watches CI. Returns nonzero on CI failure.

set -euo pipefail

REMOTE="${1:-origin}"
BRANCH="${2:-$(git branch --show-current)}"

echo "Pushing ${BRANCH} to ${REMOTE}..."
git push "${REMOTE}" "${BRANCH}" 2>&1

# Check if gh CLI is available
if command -v gh &>/dev/null; then
    echo "Watching CI workflow..."
    # Get the latest run for this branch
    RUN_ID=$(gh run list --branch "${BRANCH}" --limit 1 --json databaseId -q '.[0].databaseId' 2>/dev/null || echo "")
    if [ -n "$RUN_ID" ]; then
        gh run watch "$RUN_ID" --exit-status 2>&1
        echo "CI passed!"
    else
        echo "No CI run found for branch ${BRANCH}. Check manually."
    fi
else
    echo "WARNING: gh CLI not installed. Cannot monitor CI."
    echo "Install gh CLI and authenticate with 'gh auth login' for CI feedback."
    echo "Check CI status manually at your GitHub repo."
fi
