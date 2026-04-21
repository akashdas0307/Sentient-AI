# Agent-Model Matching Guide (OMOA)

## Core Insight: Models Are Developers

Each model has different strengths. OMOA assigns each agent a model that matches its working style.

## Agent Categories

### Communicators → Claude / Kimi / GLM
- Sisyphus (main orchestrator): Claude Opus 4.7 or Kimi K2.5
- Metis (plan gap analyzer): Claude Opus 4.7 → GPT-5.4

### Dual-Prompt Agents → Claude preferred, GPT supported
- Prometheus (strategic planner): auto-detects model at runtime
- Atlas (todo orchestrator): auto-switches prompts

### Deep Specialists → GPT
- Hephaestus: GPT-5.4 (autonomous deep worker)
- Oracle: GPT-5.4 high (architecture consultant)
- Momus: GPT-5.4 xhigh (ruthless reviewer)

### Utility Runners → Speed over Intelligence
- Explore: Grok Code Fast 1 (fastest, cheapest)
- Librarian: MiniMax M2.7
- Multimodal Looker: GPT-5.4 medium

## Task Categories

| Category | When Used | Default Model |
|----------|-----------|--------------|
| visual-engineering | Frontend, UI | Gemini 3.1 Pro |
| ultrabrain | Max reasoning | GPT-5.4 xhigh |
| deep | Complex logic | GPT-5.4 medium |
| artistry | Creative | Gemini 3.1 Pro |
| quick | Simple tasks | GPT-5-nano |
| unspecified-high | Complex work | Claude Opus 4.7 max |
| unspecified-low | Standard work | Claude Sonnet 4.6 |
| writing | Text, docs | Gemini 3 Flash |

## Config Schema

```jsonc
{
  "agents": {
    "sisyphus": {
      "model": "kimi-for-coding/k2p5",
      "ultrawork": { "model": "anthropic/claude-opus-4-7", "variant": "max" },
    },
    "librarian": { "model": "google/gemini-3-flash" },
    "explore": { "model": "github-copilot/grok-code-fast-1" },
  },
  "categories": {
    "quick": { "model": "opencode/gpt-5-nano" },
    "unspecified-high": { "model": "anthropic/claude-opus-4-7", "variant": "max" },
  },
  "background_task": {
    "providerConcurrency": {
      "anthropic": 3,
      "openai": 3,
      "opencode": 10,
    }
  }
}
```

## State Management

- Agent configs in `.opencode/agents/*.md`
- Category configs in `opencode.json` `categories` section
- Model fallback chains in `src/shared/model-requirements.ts`
