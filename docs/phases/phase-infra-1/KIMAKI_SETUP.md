# KIMAKI_SETUP.md — Phase Infra-1, D5

**Committed as:** `feat(infra-1-d5): MEMORY.md + Discord notification script`
**Lead:** Sisyphus Junior · **Review:** Hephaestus
**Date:** 2026-04-21

---

## 1. Channel → Project → Session Model

```
Discord #sentient-ai-framework
         │
         ▼
Kimaki bridge (npx -y kimaki@latest — already live)
         │
         ▼
OpenCode server (per-project, dynamic port)
         │
         ▼
Session per Discord thread (Sisyphus as default agent)
```

| Concept | Details |
|---------|---------|
| **Channel** | `#sentient-ai-framework` — mapped to `/home/akashdas/Desktop/Sentient-AI/` |
| **Project** | The project directory on the machine where Kimaki runs |
| **Session** | OpenCode session created per Discord thread; auto-resumes on follow-up |
| **Thread** | Discord thread created per user message in the channel |

---

## 2. MEMORY.md Best Practices

- Located at project root; Kimaki reads on EVERY session start
- Keep under 500 lines (context window budget)
- Include: current phase, branch, architecture summary, RED gate, common commands, key files
- Update at every sub-phase boundary (not by agents — by orchestrator only)
- This file is the AI's "first impression" — keep it accurate and concise

---

## 3. Kimaki Allowlist

Users who can send messages to the bot:

- **Server Owner** (full access)
- **Administrator** (full access)
- **Manage Server** permission (full access)
- **"Kimaki" role** (custom role for team members)

All other users are ignored by the bot.

---

## 4. `/queue` Command

- Queues follow-up messages while AI is actively responding
- Messages processed in Discord arrival order (FIFO per thread)
- Serial queue per thread prevents race conditions
- Bypass character limits by using Discord's "Send message as file" feature

---

## 5. Session Forking

- Reply to any message in a thread to continue that session
- Fork a session by sending a new top-level message in the channel (creates new thread)
- Sessions persist across bot restarts (SQLite-backed)

---

## 6. Troubleshooting

### Tunnel Down
```
Symptom: Messages in Discord but no AI response
Check: Is kimaki process running? (ps aux | grep kimaki)
Fix: Restart: npx -y kimaki@latest
Verify: Send test message, check ~/.kimaki/kimaki.log
```

### Bot Silent
```
Symptom: No response at all (not even error)
Check: Is the bot in the server? Has it been kicked?
Check: Is KIMAKI_BOT_TOKEN valid?
Fix: Re-run kimaki interactive setup to reconfigure
```

### Session Stuck
```
Symptom: Bot responds to other threads but not this one
Check: Is OpenCode server for this project running? (ps aux | grep opencode)
Fix: Kill stale OpenCode process; Kimaki will auto-restart it
Fix: Or restart kimaki entirely (kill -SIGUSR2 for graceful restart)
```

### Tokens Exhausted
```
Symptom: AI responses are empty or truncated
Check: Are Ollama cloud models responding? (curl localhost:11434/api/tags)
Fix: Restart Ollama if needed
Note: OpenCode has built-in context compaction for long sessions
```

### Agent Loop
```
Symptom: AI repeats the same action endlessly
Fix: Send "stop" or "cancel" in the thread
Fix: Kimaki's message queue handles interrupt — new message aborts current session
```

### Stale Claim
```
Symptom: Worker reports "file locked by another worker"
Check: .agent-state/shared/claims/ for old claim files
Fix: claims auto-expire after 10 minutes (state-sync prunes them)
Manual: rm .agent-state/shared/claims/*.claim
```

---

*Kimaki setup guide complete.*