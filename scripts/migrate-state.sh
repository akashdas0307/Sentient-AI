#!/usr/bin/env bash
# migrate-state.sh — Migrate OMC state to unified .agent-state/ tree
# Phase Infra-1 (D2) for Sentient AI Framework
#
# Usage:
#   bash scripts/migrate-state.sh            # Run migration
#   bash scripts/migrate-state.sh --dry-run  # Preview without changes
#   bash scripts/migrate-state.sh --help     # Show help
#
# Requirements:
#   - Idempotent (second run is a no-op)
#   - Copies only (never moves or deletes originals)
#   - Backs up .omc/ before any changes
#   - Creates .agent-state/ tree with omc/, omoa/, shared/ subdirs
#   - Sets OMC_STATE_DIR in .env
#   - Symlinks MEMORY.md → .agent-state/shared/memory.md
#   - Logs everything to .agent-state/migration-{timestamp}.log

set -euo pipefail

# ─── Configuration ───────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
OMC_DIR="$PROJECT_ROOT/.omc"
AGENT_STATE_DIR="$PROJECT_ROOT/.agent-state"
ENV_FILE="$PROJECT_ROOT/.env"
ENV_EXAMPLE="$PROJECT_ROOT/.env.example"
MEMORY_MD="$PROJECT_ROOT/MEMORY.md"
DRY_RUN=false
TIMESTAMP="$(date -u +"%Y%m%dT%H%M%SZ")"
LOG_FILE="$AGENT_STATE_DIR/migration-${TIMESTAMP}.log"

# ─── Colors ──────────────────────────────────────────────────────────────────

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ─── Functions ────────────────────────────────────────────────────────────────

usage() {
    cat <<'EOF'
migrate-state.sh — Migrate OMC state to unified .agent-state/ tree

Usage:
  bash scripts/migrate-state.sh            # Run migration
  bash scripts/migrate-state.sh --dry-run  # Preview without changes
  bash scripts/migrate-state.sh --help     # Show this help

What it does:
  1. Creates .agent-state/ directory tree (omc/, omoa/, shared/)
  2. Copies .omc/ contents to .agent-state/omc/ (originals preserved)
  3. Mirrors plans/ and notepad to .agent-state/shared/
  4. Creates MEMORY.md symlink at project root
  5. Appends OMC_STATE_DIR to .env
  6. Logs everything to .agent-state/migration-{timestamp}.log

Safety:
  --dry-run shows what would happen without making changes
  Idempotent: second run is a no-op
  Never deletes or moves original .omc/ files
  Backs up .omc/ to .omc.backup-{timestamp}/ before changes
EOF
}

log() {
    local level="$1"
    shift
    local msg="$*"
    local ts
    ts="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    echo -e "${level} [${ts}] ${msg}"
    if [ -f "$LOG_FILE" ] || [ "$DRY_RUN" = false ]; then
        mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || true
        echo "${level} [${ts}] ${msg}" >> "$LOG_FILE" 2>/dev/null || true
    fi
}

log_info()  { log "${GREEN}[INFO]" "$@"; }
log_warn()  { log "${YELLOW}[WARN]" "$@"; }
log_error() { log "${RED}[ERROR]" "$@"; }
log_dry()   { log "${BLUE}[DRY]" "$@"; }

check_idempotent() {
    # Check if migration has already been run
    if [ -f "$AGENT_STATE_DIR/.migrated" ]; then
        local prev_ts
        prev_ts="$(cat "$AGENT_STATE_DIR/.migrated")"
        log_info "Migration already completed at ${prev_ts}. Skipping."
        log_info "To re-run, delete .agent-state/.migrated and .agent-state/ first."
        return 0
    fi
    return 1
}

mark_migrated() {
    echo "$TIMESTAMP" > "$AGENT_STATE_DIR/.migrated"
}

create_directory_tree() {
    log_info "Creating .agent-state/ directory tree..."
    mkdir -p "$AGENT_STATE_DIR/omc/plans"
    mkdir -p "$AGENT_STATE_DIR/omc/prompts"
    mkdir -p "$AGENT_STATE_DIR/omc/artifacts"
    mkdir -p "$AGENT_STATE_DIR/omc/specs"
    mkdir -p "$AGENT_STATE_DIR/omc/state"
    mkdir -p "$AGENT_STATE_DIR/omc/sessions"
    mkdir -p "$AGENT_STATE_DIR/omc/notepads"
    mkdir -p "$AGENT_STATE_DIR/omoa"
    mkdir -p "$AGENT_STATE_DIR/shared/plans"
    mkdir -p "$AGENT_STATE_DIR/shared/notepad"
    mkdir -p "$AGENT_STATE_DIR/shared/messages/broadcast"
    mkdir -p "$AGENT_STATE_DIR/shared/claims"
    mkdir -p "$AGENT_STATE_DIR/shared/results"
    log_info "Directory tree created."
}

backup_omc() {
    local backup_dir="$PROJECT_ROOT/.omc.backup-${TIMESTAMP}"
    log_info "Backing up .omc/ to ${backup_dir}..."
    cp -r "$OMC_DIR" "$backup_dir"
    log_info "Backup complete."
}

copy_omc_to_agent_state() {
    # Copy plans
    if [ -d "$OMC_DIR/plans" ]; then
        log_info "Copying .omc/plans/ → .agent-state/omc/plans/"
        cp -r "$OMC_DIR/plans/"* "$AGENT_STATE_DIR/omc/plans/" 2>/dev/null || true
        log_info "Mirroring plans/ → .agent-state/shared/plans/"
        cp -r "$OMC_DIR/plans/"* "$AGENT_STATE_DIR/shared/plans/" 2>/dev/null || true
    else
        log_warn ".omc/plans/ not found, skipping."
    fi

    # Copy state
    if [ -d "$OMC_DIR/state" ]; then
        log_info "Copying .omc/state/ → .agent-state/omc/state/"
        cp -r "$OMC_DIR/state/"* "$AGENT_STATE_DIR/omc/state/" 2>/dev/null || true
    else
        log_warn ".omc/state/ not found, skipping."
    fi

    # Copy sessions
    if [ -d "$OMC_DIR/sessions" ]; then
        log_info "Copying .omc/sessions/ → .agent-state/omc/sessions/"
        cp -r "$OMC_DIR/sessions/"* "$AGENT_STATE_DIR/omc/sessions/" 2>/dev/null || true
    else
        log_warn ".omc/sessions/ not found, skipping."
    fi

    # Copy artifacts
    if [ -d "$OMC_DIR/artifacts" ]; then
        log_info "Copying .omc/artifacts/ → .agent-state/omc/artifacts/"
        cp -r "$OMC_DIR/artifacts/"* "$AGENT_STATE_DIR/omc/artifacts/" 2>/dev/null || true
    else
        log_warn ".omc/artifacts/ not found, skipping."
    fi

    # Copy and split notepad
    if [ -f "$OMC_DIR/notepad.md" ]; then
        log_info "Splitting .omc/notepad.md → .agent-state/shared/notepad/"
        # Extract Priority Context section
        sed -n '/^## Priority Context/,/^## /{ /^## Working/p; /^## Priority Context/d; p }' "$OMC_DIR/notepad.md" \
            > "$AGENT_STATE_DIR/shared/notepad/priority.md" 2>/dev/null || true
        # Extract Working Memory section
        sed -n '/^## Working Memory/,/^## /{ /^## Manual/p; /^## Working Memory/d; p }' "$OMC_DIR/notepad.md" \
            > "$AGENT_STATE_DIR/shared/notepad/working.md" 2>/dev/null || true
        # If sed didn't split well, just copy the whole thing
        if [ ! -s "$AGENT_STATE_DIR/shared/notepad/priority.md" ]; then
            cp "$OMC_DIR/notepad.md" "$AGENT_STATE_DIR/shared/notepad/priority.md"
            cp "$OMC_DIR/notepad.md" "$AGENT_STATE_DIR/shared/notepad/working.md"
        fi
        # Also copy full notepad to omc for compatibility
        cp "$OMC_DIR/notepad.md" "$AGENT_STATE_DIR/omc/notepads/notepad.md"
    else
        log_warn ".omc/notepad.md not found, creating empty notepad files."
        echo "# Priority Context" > "$AGENT_STATE_DIR/shared/notepad/priority.md"
        echo "<!-- Auto-managed. Keep under 500 chars. -->" >> "$AGENT_STATE_DIR/shared/notepad/priority.md"
        echo "# Working Memory" > "$AGENT_STATE_DIR/shared/notepad/working.md"
        echo "<!-- Session notes. Auto-pruned after 7 days. -->" >> "$AGENT_STATE_DIR/shared/notepad/working.md"
    fi

    # Archive project-memory.json
    if [ -f "$OMC_DIR/project-memory.json" ]; then
        log_info "Archiving .omc/project-memory.json → .agent-state/omc/"
        cp "$OMC_DIR/project-memory.json" "$AGENT_STATE_DIR/omc/project-memory.json"
    fi

    # Archive prd.json
    if [ -f "$OMC_DIR/prd.json" ]; then
        log_info "Archiving .omc/prd.json → .agent-state/omc/"
        cp "$OMC_DIR/prd.json" "$AGENT_STATE_DIR/omc/prd.json"
    fi
}

setup_memory_md() {
    # Create initial memory.md content
    if [ ! -f "$AGENT_STATE_DIR/shared/memory.md" ]; then
        log_info "Creating .agent-state/shared/memory.md..."
        cat > "$AGENT_STATE_DIR/shared/memory.md" << 'MEMORYEOF'
# MEMORY.md — Sentient AI Framework (Kimaki Auto-Load)

## Current Phase
- Phase 10: COMPLETE (Aliveness Audit)
- Phase 11: Frontend Redesign (in progress or merged)
- Infra-1: OMOA Migration (this phase)

## Architecture Summary
Thalamus → Prajñā (Checkpost → Queue Zone → TLP → Cognitive Core → World Model) → Brainstem
8 frontend routes: Chat, Modules, Memory, Graph, Sleep, Events, Gateway, Identity
WebSocket at `/ws` for real-time events

## Key Files
- `CLAUDE.md` — OMC session instructions (auto-read by compat layer)
- `AGENTS.md` — OpenCode-native rules
- `config/inference_gateway.yaml` — Ollama model label mapping
- `.agent-state/shared/` — Cross-backend shared state
- `frontend/src/` — React 19 + HeroUI v3 + Zustand 5
- `src/sentient/api/server.py` — Backend API surface (DO NOT MODIFY this phase)

## RED Gate Rule
NEVER edit `src/sentient/**`, `tests/**`, or `frontend/src/**` directly.
Delegate code changes to `@claude-code-worker`, `@gemini-worker`, or `@codex-worker`.

## Common Commands
- `ulw` — ultrawork mode (deep execution)
- `@claude-code-worker` — delegate to Claude Code via OMC
- `@gemini-worker` — delegate to Gemini CLI
- `@codex-worker` — delegate to Codex CLI
- `@oracle` — architecture consultation
- `/queue` — queue follow-up messages in Kimaki

## Tests
- `bash scripts/run_tests_safe.sh` — safe test runner (checks RAM first)
- `bash scripts/safe_push.sh` — push with CI watch
- `ruff check src/ tests/` — lint
MEMORYEOF
    fi

    # Create symlink MEMORY.md → .agent-state/shared/memory.md
    if [ -L "$MEMORY_MD" ]; then
        log_info "MEMORY.md symlink already exists, skipping."
    elif [ -f "$MEMORY_MD" ]; then
        log_warn "MEMORY.md exists but is not a symlink. Backing up and replacing."
        mv "$MEMORY_MD" "${MEMORY_MD}.backup-${TIMESTAMP}"
        ln -s "$AGENT_STATE_DIR/shared/memory.md" "$MEMORY_MD"
        log_info "Symlink created: MEMORY.md → .agent-state/shared/memory.md"
    else
        ln -s "$AGENT_STATE_DIR/shared/memory.md" "$MEMORY_MD"
        log_info "Symlink created: MEMORY.md → .agent-state/shared/memory.md"
    fi
}

setup_env() {
    local omc_state_dir_line="OMC_STATE_DIR=\"${PROJECT_ROOT}/.agent-state/omc\""

    if [ -f "$ENV_FILE" ]; then
        # .env exists — append if not already there
        if grep -qF "OMC_STATE_DIR" "$ENV_FILE"; then
            log_info "OMC_STATE_DIR already in .env, skipping."
        else
            log_info "Appending OMC_STATE_DIR to .env..."
            echo "" >> "$ENV_FILE"
            echo "# OMC State Directory (set by migrate-state.sh)" >> "$ENV_FILE"
            echo "$omc_state_dir_line" >> "$ENV_FILE"
        fi
    elif [ -f "$ENV_EXAMPLE" ]; then
        # .env doesn't exist but .env.example does — copy and append
        log_info "Creating .env from .env.example and appending OMC_STATE_DIR..."
        cp "$ENV_EXAMPLE" "$ENV_FILE"
        echo "" >> "$ENV_FILE"
        echo "# OMC State Directory (set by migrate-state.sh)" >> "$ENV_FILE"
        echo "$omc_state_dir_line" >> "$ENV_FILE"
    else
        # Neither exists — create minimal .env
        log_warn "Neither .env nor .env.example found. Creating .env with OMC_STATE_DIR only."
        echo "# OMC State Directory (set by migrate-state.sh)" > "$ENV_FILE"
        echo "$omc_state_dir_line" >> "$ENV_FILE"
    fi
}

# ─── Dry-run mode ────────────────────────────────────────────────────────────

dry_run() {
    log_dry "=== DRY RUN MODE ==="
    log_dry "Would create directory tree:"
    log_dry "  .agent-state/omc/plans/"
    log_dry "  .agent-state/omc/prompts/"
    log_dry "  .agent-state/omc/artifacts/"
    log_dry "  .agent-state/omc/specs/"
    log_dry "  .agent-state/omc/state/"
    log_dry "  .agent-state/omc/sessions/"
    log_dry "  .agent-state/omc/notepads/"
    log_dry "  .agent-state/omoa/"
    log_dry "  .agent-state/shared/plans/"
    log_dry "  .agent-state/shared/notepad/"
    log_dry "  .agent-state/shared/memory.md"
    log_dry "  .agent-state/shared/messages/broadcast/"
    log_dry "  .agent-state/shared/claims/"
    log_dry "  .agent-state/shared/results/"

    if [ -d "$OMC_DIR" ]; then
        local file_count
        file_count="$(find "$OMC_DIR" -type f 2>/dev/null | wc -l || echo "unknown")"
        log_dry "Would copy ${file_count} files from .omc/ to .agent-state/omc/"
        log_dry "Would mirror plans/ to .agent-state/shared/plans/"
        log_dry "Would split notepad.md into priority.md + working.md"
        log_dry "Would backup .omc/ to .omc.backup-${TIMESTAMP}/"
    else
        log_dry ".omc/ directory not found — nothing to copy"
    fi

    if [ -L "$MEMORY_MD" ]; then
        log_dry "MEMORY.md symlink already exists"
    else
        log_dry "Would create symlink: MEMORY.md → .agent-state/shared/memory.md"
    fi

    if [ -f "$ENV_FILE" ]; then
        if grep -qF "OMC_STATE_DIR" "$ENV_FILE" 2>/dev/null; then
            log_dry "OMC_STATE_DIR already in .env"
        else
            log_dry "Would append OMC_STATE_DIR to .env"
        fi
    elif [ -f "$ENV_EXAMPLE" ]; then
        log_dry "Would create .env from .env.example and append OMC_STATE_DIR"
    else
        log_dry "Would create .env with OMC_STATE_DIR only"
    fi

    log_dry "Would create .agent-state/.migrated marker file"
    log_dry "=== DRY RUN COMPLETE ==="
}

# ─── Main ────────────────────────────────────────────────────────────────────

main() {
    # Parse arguments
    case "${1:-}" in
        --dry-run)
            DRY_RUN=true
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        "")
            DRY_RUN=false
            ;;
        *)
            echo "Unknown argument: $1"
            usage
            exit 1
            ;;
    esac

    echo "=========================================="
    echo " migrate-state.sh — OMC → .agent-state/"
    echo " Phase Infra-1 (D2)"
    echo "=========================================="
    echo ""

    if [ "$DRY_RUN" = true ]; then
        dry_run
        exit 0
    fi

    # Check for existing migration
    if check_idempotent; then
        exit 0
    fi

    # Verify .omc directory exists
    if [ ! -d "$OMC_DIR" ]; then
        log_error ".omc/ directory not found at $OMC_DIR"
        log_error "Cannot migrate — no source state exists."
        exit 1
    fi

    # Create directory tree
    create_directory_tree

    # Backup .omc
    backup_omc

    # Copy files
    copy_omc_to_agent_state

    # Set up MEMORY.md
    setup_memory_md

    # Set up .env
    setup_env

    # Mark migration as complete
    mark_migrated

    log_info "=========================================="
    log_info " Migration complete!"
    log_info "=========================================="
    log_info ""
    log_info "Directory tree: .agent-state/"
    log_info "  ├── omc/          (OMC state copy)"
    log_info "  ├── omoa/         (OMOA session artifacts)"
    log_info "  └── shared/       (cross-backend state)"
    log_info "      ├── plans/    (mirrored from OMC)"
    log_info "      ├── notepad/  (priority.md + working.md)"
    log_info "      ├── memory.md (→ MEMORY.md at root)"
    log_info "      ├── messages/broadcast/"
    log_info "      ├── claims/"
    log_info "      └── results/"
    log_info ""
    log_info "Symlink: MEMORY.md → .agent-state/shared/memory.md"
    log_info "OMC_STATE_DIR set in .env"
    log_info "Log: .agent-state/migration-${TIMESTAMP}.log"
    log_info "Backup: .omc.backup-${TIMESTAMP}/"
    echo ""
    echo "Run 'bash scripts/migrate-state.sh --dry-run' again to verify idempotency."
}

main "$@"