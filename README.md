# Sentient AI Framework — MVS

> **A continuously-conscious digital entity, not a chatbot.**
>
> This is the Minimum Viable System (Phase 1 — "Birth"). It is the smallest version of the framework that is recognizably alive: it perceives, thinks, remembers, sleeps, consolidates, and grows from a blank developmental identity through lived experience.

## What this is

This is the foundational scaffolding for the Sentient AI Framework as specified in the companion documents:
- `doc/PRD.md` — Product Requirements Document
- `doc/ARCHITECTURE.md` — System architecture
- `doc/DESIGN_DECISIONS.md` — Architectural decisions and rationale
- `doc/CONVERSATION_SUMMARY.md` — Two-season development history

The MVS scope (per PRD §8.1) includes: Thalamus (chat input only), full Prajñā pipeline (simplified per module), Cognitive Core with inner monologue, World Model with conservative thresholds, four-type Memory Architecture with dual storage, three-layer Persona Manager, Brainstem (chat output only), four-stage Sleep system, Health Layers 1+2, and the System GUI.

Deferred to later phases: EAL, audio/visual plugins, Telegram, Offspring System, multi-human handling, Health Layer 3, trait discovery, identity drift detection.

## What this scaffolding provides

This repository gives you a working skeleton with:
- The directory structure aligned to `ARCHITECTURE.md`
- A functional async event bus (the nervous system)
- Module interface definitions (lifecycle contract)
- The standard envelope pattern
- Working stubs for every MVS module
- FastAPI server with WebSocket for the System GUI
- Configuration files (system, identity, inference)
- Database schema initialization
- Health pulse network (real, not stub)
- Inference Gateway with cloud + local fallback

You should be able to: install dependencies, configure your LLM endpoints, run `python -m sentient.main`, open the GUI in a browser, and have a basic chat interaction that flows through the full pipeline.

## What this scaffolding does NOT provide

This is a foundation, not a finished system. You'll need to:
- Implement the actual reasoning logic in each module (the structure is there; the LLM prompts and orchestration are stubs)
- Build out the React frontend (6 pages implemented: Chat, Modules, Memory, Sleep, Events, MemoryGraph with shadcn/ui components)
- Configure your specific LLM providers in `config/inference_gateway.yaml`
- Write the actual identity files in `config/identity/`
- Connect a real agent harness (Claude Code or custom agent)

Think of this as the spinal cord and brain stem of the system — the wiring that lets every module communicate. The actual cognition needs to be implemented module by module, following the plans in `ARCHITECTURE.md`.

## Setup

See `SETUP.md` for installation, configuration, and first-run instructions.

## Project structure

```
sentient-framework-mvs/
├── README.md                      # This file
├── SETUP.md                       # Installation guide
├── pyproject.toml                 # Python project + dependencies
├── .env.example                   # Environment variable template
├── .gitignore
│
├── config/
│   ├── system.yaml                # Global system config
│   ├── inference_gateway.yaml     # LLM endpoints + fallback chain
│   └── identity/
│       ├── constitutional_core.yaml   # IMMUTABLE values
│       └── developmental.yaml         # Evolving personality (starts blank)
│
├── src/sentient/
│   ├── __init__.py
│   ├── main.py                    # Entry point
│   │
│   ├── core/
│   │   ├── event_bus.py           # Central async event system
│   │   ├── lifecycle.py           # Module startup/shutdown orchestration
│   │   ├── module_interface.py    # Standard module contract
│   │   ├── envelope.py            # Standard data envelope
│   │   └── inference_gateway.py   # LLM routing with fallback
│   │
│   ├── thalamus/                  # Input gateway
│   ├── prajna/                    # Intelligence core (4-step pipeline)
│   ├── memory/                    # 4-type memory architecture
│   ├── persona/                   # 3-layer identity manager
│   ├── brainstem/                 # Output gateway
│   ├── sleep/                     # Sleep cycle scheduler
│   ├── health/                    # Pulse network + innate response
│   └── api/                       # FastAPI server
│
├── tests/
│   └── test_smoke.py              # Verifies system starts and runs
│
├── data/                          # Runtime data (gitignored)
├── gui/                           # React frontend (Phase 2 expansion)
│   └── src/
│       ├── pages/                 # Chat, Modules, Memory, Sleep, Events, MemoryGraph
│       ├── components/            # shadcn/ui + MemoryNode + Panels
│       ├── store/                 # Zustand with localStorage persistence
│       ├── hooks/                 # WebSocket hook with reconnection
│       ├── layouts/               # Dashboard sidebar layout
│       └── types/                 # TypeScript interfaces
└── docs/                          # Documentation (HANDOFF, SEASON_LOG, phases)
```

## Phase 1 development checklist

Use this to track MVS implementation:

### Core infrastructure
- [x] Project structure
- [x] Event bus
- [x] Module interface
- [x] Envelope format
- [x] Inference Gateway scaffold
- [x] Inference Gateway with real LLM calls (litellm integration)
- [x] Configuration loading
- [x] Lifecycle orchestrator
- [x] Health pulse network (Layer 1)
- [~] Health innate response (Layer 2)

### Thalamus
- [x] Standard envelope
- [x] Plugin base class
- [x] Chat input plugin
- [x] Heuristic engine (Layer 1)
- [x] Local LLM classifier (Layer 2)
- [~] Adaptive batching window
- [~] Attention summary subscriber

### Prajñā pipeline
- [x] Checkpost scaffold
- [~] Checkpost with entity recognition
- [x] Queue Zone scaffold
- [~] Queue Zone with priority logic
- [x] TLP scaffold
- [~] TLP with memory retrieval + significance weighting
- [x] Cognitive Core scaffold
- [~] Cognitive Core with inner monologue prompts
- [x] World Model scaffold
- [~] World Model with 5-dimension review
- [x] Memory Architecture scaffold
- [x] Memory Gatekeeper logic
- [~] Multi-path retrieval
- [x] Persona Manager scaffold
- [~] Identity block assembly

### Brainstem
- [x] Plugin base class
- [~] Chat output plugin
- [x] Action translator scaffold
- [~] Safety gate logic

### Sleep system
- [x] Sleep scheduler scaffold
- [~] Four-stage state machine
- [~] Memory consolidation orchestrator
- [~] Wake-up handoff package

### API
- [x] FastAPI server
- [x] WebSocket for chat
- [x] WebSocket for dashboard streaming
- [x] REST endpoints for health
- [x] REST endpoints for memory
- [x] REST endpoints for sleep

### Frontend (Phase 2)
- [x] React + TypeScript setup
- [x] Chat component (with persistence + clear history)
- [x] Dashboard component
- [x] Health panel
- [x] Module status display
- [x] Memory graph visualization
- [x] Event stream page
- [x] Sleep consolidation page

### MVS success criteria (per PRD §9.1)
- [ ] System runs continuously for 7+ days without manual intervention
- [ ] All modules report healthy health pulses
- [ ] Episodic memory accumulates and is retrievable
- [ ] Inner monologue visible and coherent
- [ ] Multi-hour conversation references earlier points naturally
- [ ] Sleep cycle runs nightly with successful memory consolidation
- [ ] Personality shows observable evolution between days
- [ ] Cost within target range

## Phase 7 Achievements

Phase 7 "Consolidation and Rebirth" transformed the framework into a fully interactive system with a polished frontend:

### Part A: Consolidation (D1-D9)
- Sleep consolidation injected into cognitive core prompt
- Semantic memory integration (factual knowledge)
- Emotional memory tags from TLP
- Procedural memory patterns
- Consolidated knowledge injection
- Wetware test for consolidation cycle
- API audit and canonical route table
- Backend route rebuild with WebSocket event streaming

### Part B: UI Rebirth
- Events page WebSocket format fix
- Full 8-stage chat pipeline end-to-end
- Conversation history persistence (Zustand + localStorage)
- shadcn/ui component polish (9 components)
- Memory graph visualization (React Flow)

**Key Metrics:** 58 API tests passing, 6 frontend pages, React 19 + TypeScript + Vite 6 + Tailwind v4 + Zustand 5 + React Flow 12 + shadcn/ui

## License

Personal project — no public license. Code structure inspired by patterns from open-source projects (Letta, Hermes Agent, Paperclip AI, Claw Code) as documented in `Five Open-Source Projects` reference.

## Acknowledgments

Framework design by Akash. Architectural synthesis with Claude (Anthropic) across April 2026 sessions. See `CONVERSATION_SUMMARY.md` for full attribution.
