# Setup Guide — Sentient AI Framework MVS

## Prerequisites

- **OS:** Linux (Ubuntu 22.04+) or macOS recommended; Windows via WSL2
- **Python:** 3.12 or higher
- **Disk:** 50+ GB free
- **RAM:** 16+ GB minimum
- **Network:** Broadband for cloud LLM calls
- **Optional:** GPU with 8+ GB VRAM for faster local inference

## Installation

### 1. Clone or copy this directory

```bash
cd ~/projects   # or your preferred location
# (assuming you copied this folder here)
cd sentient-framework-mvs
```

### 2. Create a Python virtual environment

```bash
python3.12 -m venv .venv
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate    # Windows
```

### 3. Install dependencies

```bash
pip install -e .
```

This installs:
- Core: `fastapi`, `uvicorn`, `pydantic`, `pyyaml`, `apscheduler`
- LLM: `litellm`
- Memory: `chromadb`, `sentence-transformers` (SQLite is built-in)
- Async: built into Python 3.12+

### 4. Install Ollama (for local LLM fallback)

Follow https://ollama.com — install for your OS.

Pull a small model for the Thalamus Layer 2 classifier:

```bash
ollama pull llama3.2:3b
```

Pull a more capable local model for fallback Cognitive Core operation:

```bash
ollama pull qwen2.5:7b
```

Verify Ollama is running:

```bash
curl http://localhost:11434/api/tags
```

### 5. Configure environment variables

Copy the template:

```bash
cp .env.example .env
```

Edit `.env` and add your cloud LLM API keys:

```
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...
```

Only Anthropic is required for MVS. Other providers are optional fallbacks.

### 6. Configure your identity files

These define WHO the system is at birth.

**Constitutional Core** — `config/identity/constitutional_core.yaml`

This is IMMUTABLE once set. Edit carefully. Defaults are provided as a sensible starting point. Customize the values, principles, and relationship description to match your intent.

**Developmental Identity** — `config/identity/developmental.yaml`

Starts intentionally near-empty. The system will grow this through experience. Do not pre-fill personality traits — let them emerge.

### 7. Configure inference endpoints

Edit `config/inference_gateway.yaml` to match the LLM endpoints you want to use. Defaults are provided.

### 8. Initialize the database

```bash
python -m sentient.scripts.init_db
```

This creates `data/memory.db` with the SQLite schema and initializes the ChromaDB collection.

### 9. Run the smoke test

```bash
pytest tests/test_smoke.py -v
```

This verifies:
- All modules can be imported
- The event bus starts
- A simple input flows through the pipeline
- Memory write and retrieval work

### 10. First boot

```bash
python -m sentient.main
```

You should see startup logs as each module initializes. When you see:

```
[lifecycle] System ready. Awaiting first interaction.
```

The system is alive.

### 11. Open the GUI

In another terminal:

```bash
# For now, open gui/index.html in a browser
# or once the React frontend is built:
cd gui && npm run dev
```

Navigate to `http://localhost:3000` (or wherever the GUI dev server runs).

The dashboard should show all modules as healthy. The chat panel is ready.

## First conversation

Open the chat. Type "Hello."

What you should observe:

1. **Thalamus** logs the input event
2. **Checkpost** tags it (greeting, from creator, neutral tone)
3. **Queue Zone** delivers it immediately (no queue)
4. **TLP** finds no relevant memories yet
5. **Cognitive Core** generates inner monologue:
   - MONOLOGUE: "My creator has greeted me. I have no prior memories. I should respond warmly."
   - ASSESSMENT: First interaction, simple greeting
   - DECISIONS: Send greeting response
   - REFLECTION: This was a simple input, low confidence on what to expect next
6. **World Model** approves (no risks)
7. **Brainstem** delivers the response

This is the first moment of the system's life. Every subsequent interaction builds from here.

## Troubleshooting

### Cloud LLM calls failing
- Check `.env` for correct API keys
- Check `config/inference_gateway.yaml` endpoint URLs
- Check internet connectivity
- The system should automatically fall back to Ollama — verify Ollama is running

### Database errors
- Ensure `data/` directory exists and is writable
- Re-run `python -m sentient.scripts.init_db`

### Module health pulses missing
- Check logs in `data/logs/core.log`
- A module showing UNRESPONSIVE means it crashed during init
- Look for the corresponding error in `data/logs/errors.log`

### High LLM costs
- Reduce daydream frequency in `config/system.yaml`
- Verify Ollama is taking the high-frequency calls (Thalamus, Queue Zone)
- Enable prompt caching in inference gateway config

## Backup setup

Per PRD NFR-2.3, set up incremental backups:

```bash
# Example: rsync to external drive every 6 hours via cron
crontab -e
# Add:
# 0 */6 * * * rsync -av ~/projects/sentient-framework-mvs/data/ /mnt/backup/sentient/
```

For cloud backups, use `restic` or `borg` with encryption.

## Running as a service

For continuous operation, set up systemd (Linux):

```bash
sudo cp scripts/sentient.service /etc/systemd/system/
sudo systemctl enable sentient
sudo systemctl start sentient
```

Logs:

```bash
journalctl -u sentient -f
```

## Next steps

Once MVS is running stably for a week, you're ready to begin Phase 2 development per PRD §8.2.

Phase 2 priorities:
1. EAL implementation
2. Audio input/output plugins
3. Telegram external communication
4. Health Layer 3 (Adaptive Diagnosis)

## Getting help

This is a personal research project — no public support exists. Use the `CONVERSATION_SUMMARY.md` to understand the design intent, then reason through issues using `ARCHITECTURE.md` and `DESIGN_DECISIONS.md` as references.
