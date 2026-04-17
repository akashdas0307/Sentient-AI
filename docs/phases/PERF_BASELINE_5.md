# Phase 5: Performance Baseline v0.5

**Date:** 2026-04-17
**Branch:** auto/phase-5-first-boot
**Environment:** Python 3.13.7, Linux 6.17.0-22, ~10 GB RAM available

---

## Measurements

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| Cold startup time | 1.4s | < 60s | PASS |
| First response latency | 31.6s | < 60s | PASS |
| Peak RSS | 186 MB | < 2 GB | PASS |
| LLM calls per turn | 4 | — | Baseline |
| LLM cost per turn | $0.000000 | — | Free (Ollama local) |

---

## LLM Call Breakdown per Turn

The 4 LLM calls per "urgent: Hello" input:

1. **Thalamus classification** (kimi-k2.5:cloud) — classifies input priority
2. **Checkpost assessment** (kimi-k2.5:cloud) — safety/relevance check
3. **Cognitive Core reasoning** (glm-5.1:cloud) — generates response decision
4. **World Model review** (minimax-m2.7:cloud) — reviews decision for safety

---

## Notes

- First response latency of 31.6s is dominated by sequential LLM calls. Each Ollama inference takes ~8-15s.
- RSS is low (186 MB) because sentence_transformers/chromadb are not loaded in this test (no memory architecture).
- Cost is $0 because Ollama runs locally — no API costs.
- The 4-call pipeline could be parallelized: Checkpost and TLP could run concurrently after Thalamus classification.

---

## Anomalies

- Response text "Acknowledge presence, confirm readiness, invite urgent follow-up without delay" appears to be a rationale/instruction rather than actual response text — the GLM model sometimes puts meta-instructions in the `parameters.content` field instead of actual conversational text.
- Peak RSS delta of 1 MB suggests minimal memory growth during inference — most RSS is from Python + asyncio + litellm at import time.