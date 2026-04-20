# UNIFIED_STATE_TREE.md — Phase Infra-1, D2

**Committed as:** `feat(infra-1-d2): unified state tree design and migration script`
**Lead:** Hephaestus · **Review:** Oracle + Momus
**Date:** 2026-04-21

---

## 1. Design Goals

1. **Preserve OMC state** — `.omc/` remains untouched during transition; OMC workers continue operating
2. **Unified access** — all backends (OMC, Gemini, Codex, OMOA-native) read/write to a shared state tree
3. **Idempotent migration** — script can be re-run safely; second run is a no-op
4. **File-lock claims** — prevent cross-backend edit collisions via `.agent-state/shared/claims/`
5. **Observable** — every action logged; every sync timestamped
6. **Graceful degradation** — system works even if `.agent-state/` doesn't exist yet

---

## 2. Directory Tree

```
.agent-state/
├── .migrated                    ← idempotency marker (timestamp of last migration)
│
├── omc/                        ← OMC_STATE_DIR points here post-migration
│   ├── plans/                  ← mirrored from .omc/plans/ (ralplan outputs)
│   ├── prompts/                ← (empty, for future use)
│   ├── artifacts/              ← mirrored from .omc/artifacts/ (omc ask outputs)
│   │   └── ask/
│   ├── specs/                  ← (empty, for future use)
│   ├── state/                  ← mirrored from .omc/state/ (checkpoints, HUD, mission)
│   │   ├── checkpoints/
│   │   ├── sessions/
│   │   ├── hud-stdin-cache.json
│   │   ├── last-tool-error.json
│   │   ├── mission-state.json
│   │   └── subagent-tracking.json
│   ├── sessions/               ← mirrored from .omc/sessions/ (93 session JSONs)
│   ├── notepads/               ← mirrored from .omc/notepad.md
│   │   └── notepad.md          ← full notepad backup
│   ├── project-memory.json     ← archived from .omc/
│   └── prd.json                ← archived from .omc/
│
├── omoa/                       ← OMOA session artifacts
│   ├── boulder.json            ← session recovery state (Kimaki auto-resume)
│   └── logs/                   ← per-session agent logs
│
└── shared/                     ← cross-backend shared state
    ├── plans/                  ← mirrored from .omc/plans/ (cross-backend access)
    ├── notepad/
    │   ├── priority.md         ← auto-managed priority context (<500 chars)
    │   └── working.md          ← auto-managed working memory (7-day prune)
    ├── memory.md               ← symlinked to MEMORY.md at project root
    ├── messages/
    │   └── broadcast/          ← critical broadcast events (RED gate violations, etc.)
    ├── claims/                 ← file-lock claims (prevent cross-backend collisions)
    │   └── *.claim             ← format: {worker, timestamp, path, ttl}
    ├── results/                ← worker result JSON
    │   └── *.json              ← format: {worker, status, summary, ...}
    └── sync.log                ← state-sync timestamp log
```

---

## 3. Migration Flow

### Phase 1: Pre-flight (migrate-state.sh)

```
1. Check .agent-state/.migrated — if exists, skip (idempotent)
2. Verify .omc/ exists — fail if not
3. Create .agent-state/ directory tree (mkdir -p)
4. Backup .omc/ → .omc.backup-{timestamp}/
5. Copy .omc/plans/ → .agent-state/omc/plans/ AND .agent-state/shared/plans/
6. Copy .omc/state/ → .agent-state/omc/state/
7. Copy .omc/sessions/ → .agent-state/omc/sessions/
8. Copy .omc/artifacts/ → .agent-state/omc/artifacts/
9. Split .omc/notepad.md → shared/notepad/priority.md + working.md
10. Copy .omc/notepad.md → omc/notepads/notepad.md
11. Archive .omc/project-memory.json → omc/
12. Archive .omc/prd.json → omc/
13. Create .agent-state/shared/memory.md (initial content for Kimaki)
14. Symlink MEMORY.md → .agent-state/shared/memory.md
15. Append OMC_STATE_DIR to .env (or create from .env.example)
16. Write .agent-state/.migrated (timestamp marker)
17. Log everything to .agent-state/migration-{timestamp}.log
```

### Phase 2: Ongoing sync (state-sync agent)

The `state-sync` bridge agent runs on every invocation:

```
1. Compare timestamps: .omc/notepad.md vs .agent-state/shared/notepad/
   → Copy newer to shared if OMC version is newer
2. rsync .agent-state/omc/plans/ → .agent-state/shared/plans/ (one-way, OMC is source)
3. Drop any pending *.task.json files into .omc/state/inbox/ (if OMC workers are running)
4. Delete claims older than 10 minutes in .agent-state/shared/claims/
5. Verify MEMORY.md symlink is live (recreate if broken)
6. Append ISO timestamp to .agent-state/shared/sync.log
```

---

## 4. Claim Protocol

To prevent cross-backend edit collisions, workers use file-lock claims:

```json
// .agent-state/shared/claims/edit-src-persona-identity_manager-py.claim
{
  "worker": "claude-code-worker",
  "timestamp": "2026-04-21T15:30:00Z",
  "path": "src/sentient/persona/identity_manager.py",
  "ttl_seconds": 600,
  "description": "Fixing first-boot IndexError"
}
```

- Claims auto-expire after TTL (default 600s / 10 min)
- state-sync prunes expired claims on every invocation
- Workers check claims before editing shared files
- RED gate: no worker should ever claim `src/sentient/**`, `tests/**`, or `frontend/src/**`

---

## 5. Result Format

All worker output JSON follows this schema:

```json
{
  "worker": "claude-code-worker",
  "status": "success | failed | unavailable",
  "branch": "auto/infra-1-omoa-migration",
  "commits": ["abc1234"],
  "tests_passed": 42,
  "tests_failed": 0,
  "ci_status": "green | red | unknown",
  "summary": "What was accomplished",
  "log_path": ".agent-state/omc/logs/session-abc.log",
  "timestamp": "2026-04-21T15:30:00Z"
}
```

---

## 6. OMC_STATE_DIR

After migration, `.env` contains:
```
OMC_STATE_DIR="/path/to/project/.agent-state/omc"
```

This tells OMC to store state in `.agent-state/omc/` instead of `.omc/`. The original `.omc/` is preserved as a backup archive.

---

*State tree design complete. Migration script: `scripts/migrate-state.sh`.*