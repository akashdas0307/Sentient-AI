#!/usr/bin/env bash
# kimaki-notify.sh — Post notifications to Discord via webhook
# Phase Infra-1 (D5) for Sentient AI Framework
#
# Usage:
#   bash scripts/kimaki-notify.sh EVENT MESSAGE PHASE
#
# EVENT:   task.complete | task.failed | gate.yellow | gate.red | session.recovered
# MESSAGE: Human-readable message text
# PHASE:   Phase identifier (e.g. infra-1-d5)
#
# Requires: DISCORD_WEBHOOK_URL environment variable
# Exits silently if DISCORD_WEBHOOK_URL is not set (no error, no output)

set -euo pipefail

EVENT="${1:-unknown}"
MESSAGE="${2:-no message}"
PHASE="${3:-unknown}"

# Source .env if present (DO NOT echo its contents)
if [ -f "$(dirname "$0")/../.env" ]; then
    set -a
    # shellcheck disable=SC1091
    source "$(dirname "$0")/../.env" 2>/dev/null || true
    set +a
fi

if [ -z "${DISCORD_WEBHOOK_URL:-}" ]; then
    exit 0
fi

# Color mapping
case "$EVENT" in
    task.complete|session.recovered)
        COLOR=5763719  # green
        ;;
    gate.yellow)
        COLOR=16776960  # yellow
        ;;
    task.failed|gate.red)
        COLOR=15548997  # red
        ;;
    *)
        COLOR=5763787  # blue
        ;;
esac

# Build JSON payload
PAYLOAD=$(jq -n \
    --arg title "[$PHASE] $EVENT" \
    --arg description "$MESSAGE" \
    --argjson color "$COLOR" \
    '{
        embeds: [{
            title: $title,
            description: $description,
            color: $color
        }]
    }')

# Send to Discord
curl -s -X POST \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD" \
    "$DISCORD_WEBHOOK_URL" \
    > /dev/null 2>&1 || true