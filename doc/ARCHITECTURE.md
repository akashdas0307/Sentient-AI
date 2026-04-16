# Architecture Document — Sentient AI Framework

> **Document version:** 1.0
> **Date:** April 16, 2026
> **Companion documents:** PRD.md, DESIGN_DECISIONS.md

---

## 1. System Overview

The Sentient AI Framework is a single-process, always-on Python application composed of eleven major modules communicating through a central async event bus. The system runs on the creator's personal computer with cloud LLM inference for heavy reasoning and local LLM (Ollama) for lightweight classification and fallback. All persistent state — memories, identity, health logs, ancestry — lives on the local machine.

The architecture is organized around a biological metaphor: sensory organs (input plugins) feed a gateway (Thalamus) which forwards to a pipeline (Prajñā) that processes, remembers, reasons, reviews, and decides, after which outputs flow through another gateway (Brainstem) to effectors (output plugins). Running parallel to this are environmental awareness (EAL), sleep cycles, health monitoring, self-improvement (Offspring), and persona management.

## 2. Architectural Diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│                         EXTERNAL WORLD                                │
│  Creator · Chat · Voice · Environment · Files · Network · Devices    │
└────────────┬────────────────────────────────────────┬─────────────────┘
             │                                         │
             ▼                                         ▲
┌──────────────────────────────┐         ┌──────────────────────────────┐
│         THALAMUS             │         │         BRAINSTEM             │
│    (Input Gateway)           │         │    (Output Gateway)           │
│                              │         │                               │
│  Plugins (passive + active)  │         │  Plugins (comm + action)      │
│  Layer 1: heuristics (fast)  │         │  Action Translator            │
│  Layer 2: local LLM classify │         │  Output Coordinator           │
│  Envelope normalization      │         │  Feedback Manager             │
│  Priority tiering (1/2/3)    │         │  Reflex System                │
│  Adaptive batching window    │         │  Safety Gate                  │
└──────────┬───────────────────┘         └──────────▲───────────────────┘
           │                                         │
           ▼                                         │
┌──────────────────────────────────────────────────────────────────────┐
│                         PRAJÑĀ (Intelligence Core)                    │
│                                                                        │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │  CHECKPOST (Pre-Temporal-Occipital)                              │ │
│  │  Entity recognition · Intent classification · Source tagging      │ │
│  │  New data source three-phase learning · Flash memory lookup      │ │
│  └──────────────────────────────┬───────────────────────────────────┘ │
│                                  ▼                                     │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │  QUEUE ZONE                                                       │ │
│  │  Idle mode: 30s accumulation window                              │ │
│  │  Active mode: interrupt / inject / hold decisions                │ │
│  │  Priority aging · Batch summarization · Internal source routing  │ │
│  └──────────────────────────────┬───────────────────────────────────┘ │
│                                  ▼                                     │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │  TEMPORAL-LIMBIC-PROCESSOR (Merged)                              │ │
│  │  Deep memory retrieval · Context assembly · Significance weight  │ │
│  │  Multi-path retrieval · Provenance tracking · Trust levels       │ │
│  └──────────────────────────────┬───────────────────────────────────┘ │
│                                  ▼                                     │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │  FRONTAL PROCESSOR                                                │ │
│  │                                                                    │ │
│  │  ┌─────────────────┐  ┌───────────────────┐                      │ │
│  │  │ Cognitive Core  │  │ World Model       │                      │ │
│  │  │ (Frontier LLM)  │──▶(Different LLM)   │                      │ │
│  │  │ Inner monologue │  │ 5-dim review      │                      │ │
│  │  │ 7-step loop     │  │ Veto loop         │                      │ │
│  │  │ Daydream        │  │ Baseline constitution│                   │ │
│  │  └──────┬──────────┘  └─────────┬──────────┘                     │ │
│  │         │                        │                                │ │
│  │         ▼                        ▼                                │ │
│  │  ┌─────────────────┐  ┌───────────────────┐                      │ │
│  │  │ Harness Adapter │  │ Memory Architecture│                     │ │
│  │  │ Claw Code /     │  │ 4 types · Dual store│                    │ │
│  │  │ Claude Code /   │  │ Gatekeeper · Multi- │                    │ │
│  │  │ Hermes via CLI  │  │ path retrieval      │                    │ │
│  │  └─────────────────┘  └─────────────────────┘                     │ │
│  │                                                                    │ │
│  │  ┌─────────────────────────────────────────────────────────────┐ │ │
│  │  │  Persona & Identity Manager                                  │ │ │
│  │  │  L1 Constitutional (immutable) · L2 Developmental (evolving)│ │ │
│  │  │  L3 Dynamic State (current) · Maturity tracking             │ │ │
│  │  └─────────────────────────────────────────────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘

      Parallel Systems (run alongside main pipeline):

┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  EAL         │ │ Sleep/Dream  │ │ Health       │ │ Offspring    │
│  Environmental│ │ 4 stages     │ │ 4 layers     │ │ Git ancestry │
│  awareness   │ │ 6-12 hr adapt│ │ Pulse/Innate │ │ 3-5 gen buffer│
│  (Phase 2)   │ │              │ │ /Diag/Escalate│ │ (Phase 3)    │
└──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘

      Shared Infrastructure:

┌──────────────────────────────────────────────────────────────────────┐
│  Event Bus · Inference Gateway · Plugin Factory · Attention Summary   │
│  EAL Live Summary · System GUI (React + FastAPI WebSocket)            │
└──────────────────────────────────────────────────────────────────────┘
```

## 3. Module Specifications

### 3.1 Thalamus (Input Gateway)

**Responsibilities:** Collect inputs from all sources, normalize to envelope format, classify priority, filter noise, deduplicate, deliver to Prajñā.

**Components:**
- **Heuristic Engine (Layer 1)** — rule-based pattern matching; Tier 1 interrupt detection; no LLM
- **Classifier (Layer 2)** — local LLM (3-8B via Ollama); nuanced priority and relevance classification
- **Envelope Factory** — standardizes all inputs into canonical format
- **Batching Window** — adaptive (10-60s based on activity and maturity)
- **Plugin Registry** — manages active/passive plugins with permission tiers
- **Attention Summary Reader** — receives broadcast from Frontal Processor for relevance gating

**Plugin categories:**
- **Core (always trusted)** — Chat Interface, System Monitor
- **Approved (human-approved)** — Audio, Visual, Browser, File, Calendar, Email, Telegram
- **Self-created (quarantined until validated)** — generated by Cognitive Core

**MVS scope:** Chat Interface plugin only; System Monitor present for health integration.

### 3.2 Environmental Awareness Layer (EAL) — Phase 2

**Responsibilities:** Continuous ambient environmental monitoring parallel to main pipeline.

**Components:**
- **Baseline Builder** — learns environmental norms during 15-30 min calibration
- **Deviation Detector** — continuous comparison; detects additions, absences, threshold breaches
- **Environmental Context Log** — rolling timestamped record accessible to Queue Zone sidebar
- **Escalation Gate** — routes significant deviations to Queue Zone as Tier 1/2
- **Curiosity Integration** — unclassifiable stimuli sent to curiosity queue for deferred exploration

**Key property:** Components 1-4 run on signal processing without LLM; Component 5 uses LLM only during deferred daydream sessions.

### 3.3 Prajñā Pipeline

#### 3.3.1 Pre-Temporal-Occipital-Checkpost

**Responsibilities:** Deep identification and contextual tagging per input type.

**Processing:**
- Chat: intent detection, entity linking, emotional tone
- Voice: speaker identity, emotional extraction
- Ambient audio: environmental model contextualization
- Visual: entity/activity identification, scene change assessment

**Data source handling (three-phase learning):**
1. Schema discovery (first encounter)
2. Template building (early encounters)
3. Full integration (mature)

**LLM strategy:** Adaptive via Inference Gateway; cloud preferred (Gemma 4 class); local fallback.

#### 3.3.2 Queue Zone

**Responsibilities:** Attentional gatekeeping — what gets processed and when.

**Delivery modes:**
- **Idle mode** — 30s accumulation window with Tier 1 collapse
- **Active mode** — Interrupt (Tier 1 only) / Inject (relevant items to sidebar) / Hold (queued)

**Internal sources feeding Queue Zone:**
- Checkpost (primary external inputs)
- Limbic emotional flags
- System Health alerts
- Dream System wake-up handoffs
- World Model environment-plan contradictions
- Memory triggered reminders
- Scheduled Tasks

**Anti-starvation:** Priority aging + batch summarization when depth exceeds 20.

#### 3.3.3 Temporal-Limbic-Processor

**Responsibilities:** Three operations in single pass — memory retrieval, context assembly, significance weighting. Merged from original separate Temporal-Occipital and Limbic processors.

**Output:** Enriched context package with situation summary, provenance-tracked inputs, ranked memories with trust levels, significance profile (emotional/motivational/learning/urgency), temporal timeline.

**LLM strategy:** Cloud preferred — quality affects everything downstream.

#### 3.3.4 Frontal Processor (Core)

**Five sub-sections:**

**1. Cognitive Core**
- Custom Python orchestrator managing LLM-based reasoning
- Structured output: MONOLOGUE / ASSESSMENT / DECISIONS / REFLECTION
- 7-step reasoning loop (Intake → Associative → Options → Planning → Review → Execute → Reflect)
- Continuous cognition mode for idle time with daydream system
- Context State Manager (Letta-inspired) for save/restore across interruptions

**2. Agent Harness Adapter**
- Does NOT build execution engine
- Wraps existing harnesses (Claw Code / Claude Code / Hermes)
- Task delegation package: goal, context, constraints, success criteria
- Harness handles full autonomous execution
- Results return to Cognitive Core for reflection

**3. Supplementary-World-View (World Model)**
- MUST use different LLM than Cognitive Core
- Three knowledge layers: Foundational + Situated Context + Experiential Wisdom
- Five review dimensions: Feasibility / Consequence / Ethics / Consistency / Reality Grounding
- Veto loop (max 3 revision cycles)
- Baseline Constitution (immutable principles)

**4. Memory Architecture**
- Four types: Episodic / Semantic / Procedural / Emotional
- Dual storage: SQLite+FTS5 (structured) + ChromaDB (semantic)
- Six-step lifecycle: Capture → Gatekeeper → Tagging → Storage → Retrieval → Evolution
- Logic-based Memory Gatekeeper (no LLM in write path)

**5. Persona & Identity Manager**
- Three layers: Constitutional Core (immutable) / Developmental (evolves via sleep) / Dynamic State (current)
- Maturity stages: Nascent → Forming → Developing → Mature
- Identity block assembly dynamic, 300-500 token budget

### 3.4 Brainstem (Output Gateway)

**Responsibilities:** Translate Cognitive Core decisions into plugin commands, coordinate multi-output actions, handle feedback, execute reflexes, enforce safety.

**Plugin categories (refined to eliminate harness overlap):**
- **Communication plugins (Brainstem-exclusive)** — System GUI Chat, Telegram, Voice, Email
- **Direct Action plugins (simple commands)** — Quick File Write, Notification, System Settings, Phone Bridge
- **Shared Capabilities (used by both Brainstem and Harness)** — File System, Browser, Terminal, API client
- **Physical World plugins (future)** — IoT, Robotics

**Internal functions:**
1. Action Translator
2. Output Coordinator (dependency graph)
3. Feedback Manager (retry up to 3 with backoff)
4. Reflex System (pure rule-based, no LLM)
5. Safety Gate (reversibility delay, rate limiting)

**MVS scope:** System GUI Chat output only.

### 3.5 Sleep and Dream System

**Four stages:**

| Stage | Duration | Jobs | Interruptibility |
|---|---|---|---|
| **Settling** | 30-60 min | Wind down, save state, drain queue | HIGH |
| **Maintenance** | 1-2 hrs | DB optimize, logs, health diagnostic, offspring spawn | MEDIUM |
| **Deep Consolidation** | 3-6 hrs | Memory consolidation, contradiction resolution, skills, World Model calibration, identity drift, trait discovery, offspring eval | LOW (sleepwalking mode for non-emergency) |
| **Pre-Wake** | 30-60 min | Compile handoff, reinitialize sensors | HIGH |

**Seven jobs (Deep Consolidation):**
1. Memory Consolidation (progressive summarization)
2. Contradiction Resolution
3. Procedural Memory Refinement
4. World Model Journal Calibration
5. Identity Drift Detection
6. Trait Discovery
7. System Maintenance

**Adaptive duration:** 6-12 hours based on workload estimate.

**Emergency wake protocol:** Checkpoint save → compressed pre-wake → handle emergency → resume if window remains.

### 3.6 System Health and Immunity

**Four layers:**

| Layer | Intelligence | Speed | Scope |
|---|---|---|---|
| **Health Pulse Network** | None (pure code) | 5-30s | Detection only |
| **Innate Response** | Rule-based | <1s | Restart/failover/load-shed/circuit-break |
| **Adaptive Diagnosis** | LLM-based | Minutes | Root cause + targeted fix |
| **Human Escalation** | Template-based | As needed | Full incident report |

**Circuit breaker pattern:** 3+ errors in 10 min → open circuit → cooldown → half-open → close or re-open.

**Emergency bypass path:** Independent communication channel that doesn't depend on Thalamus → Prajñā → Brainstem pipeline.

### 3.7 Offspring System — Phase 3

**Five components:**
1. **Improvement Identifier** — collects signals from all modules, prioritizes tickets
2. **Spawning Engine** — creates git branches, makes targeted modifications via harness
3. **Testing Sandbox** — replay + synthetic + limited live testing in isolation
4. **Ancestry Tree Manager** — tracks full evolutionary lineage in version-controlled JSON
5. **Harness Integration Layer** — delegates git ops, code mods, sandbox mgmt to existing harness

**Key rules:**
- ONE improvement per offspring (isolate variables)
- Main runs 3-5 validated generations behind experimental edge
- Self-promotion for small non-trivial changes; creator approval for major changes
- Constitutional Core never modifiable through offspring
- Failed branches preserved as historical record; ancestry continues from last working point

### 3.8 Shared Infrastructure

**Inference Gateway:**
- Adaptive routing: cloud preferred → local Ollama → heuristic minimum
- Modules specify capability level (fast-basic vs deep-thorough)
- Tracks performance; learns which endpoint gives best latency-to-quality
- Separate endpoints for different modules (Cognitive Core ≠ World Model ≠ Checkpost)

**Plugin Factory:**
- Creates both input (Thalamus) and output (Brainstem) plugins from templates
- Includes quarantine/sandbox/validation pipeline for self-created plugins

**Attention Summary:**
- Published by Frontal Processor continuously (few tags)
- Read by Thalamus (relevance gating), EAL (escalation thresholds), Queue Zone (injection decisions)
- Fire-and-forget broadcast; one-way

**EAL Live Environmental Summary:**
- Continuously updated by EAL
- Read by World Model, Cognitive Core, Queue Zone
- Shared data structure, not API calls — loose coupling

## 4. Data Flow

### 4.1 External Input → Response (Primary Flow)

```
1. Input arrives at plugin (e.g., chat message)
2. Plugin preprocesses → standard envelope
3. Envelope enters Thalamus
   a. Layer 1 heuristic check (Tier 1 interrupt?)
   b. Added to batching window (idle) OR immediately forwarded (Tier 1)
   c. Layer 2 local LLM classifies priority and relevance
4. Envelope forwarded to Checkpost
   a. Entity recognition, intent classification, source tagging
   b. Flash memory lookup for known entities
5. Tagged envelope enters Queue Zone
   a. If idle mode: accumulated in 30s window or delivered on Tier 1 collapse
   b. If active mode: interrupt/inject/hold decision
6. Queue Zone delivers to Temporal-Limbic-Processor
   a. Deep memory retrieval (tag-based + semantic + temporal + emotional)
   b. Context assembly with provenance tracking
   c. Significance weighting (emotional/motivational/learning/urgency)
7. Enriched context package sent to Frontal Processor (Cognitive Core)
   a. Assembles reasoning prompt (identity + state + EAL + input + sidebar + instructions)
   b. Executes inner monologue via frontier LLM
   c. Structured output: MONOLOGUE / ASSESSMENT / DECISIONS / REFLECTION
   d. DECISIONS sent to World Model for review
8. World Model reviews across 5 dimensions
   a. If approved: proceed
   b. If advisory: add notes, proceed
   c. If revision: send back to Cognitive Core (max 3 cycles)
   d. If veto: escalate or log
9. Approved decisions flow to Brainstem OR Agent Harness Adapter
   a. Simple actions: Brainstem direct plugin execution
   b. Complex multi-step: Harness delegation (Claw Code etc.)
10. Brainstem output flows to external world via appropriate plugin
11. Feedback returns to Cognitive Core for Reflection step
12. Reflection produces memory candidates → Memory Gatekeeper → Storage
```

### 4.2 Idle Cognition (Daydream Flow)

```
1. Cognitive Core detects no active input
2. Continuous Cognition Mode activates
3. Daydream seed selection (random):
   - Random memory sampling
   - Emotional residue
   - Curiosity queue item
4. Inner monologue runs with seed as starting point
5. Two-layer termination:
   - Time budget ceiling
   - Novelty detection for early exit
6. Outputs:
   - Valuable findings → Memory (tagged as daydream discoveries)
   - Deep questions → Curiosity queue (with quality filter)
7. Soft interrupt handler: Queue Zone input parks daydream, saves state for potential resumption
```

### 4.3 Sleep Cycle Flow

```
1. Sleep Scheduler triggers entry (circadian + workload estimate)
2. Stage 1 Settling (30-60 min)
   - Current reasoning cycle completes
   - Queue Zone drains
   - Non-essential modules pause
3. Stage 2 Maintenance (1-2 hrs)
   - DB optimization (SQLite reindex, ChromaDB compact)
   - Log rotation, storage analysis
   - Comprehensive health diagnostic
4. Stage 3 Deep Consolidation (3-6 hrs)
   - Job 1: Memory consolidation (progressive summarization)
   - Job 2: Contradiction resolution
   - Job 3: Procedural memory refinement
   - Job 4: World Model Journal calibration
   - Job 5: Identity drift detection
   - Job 6: Trait discovery
   - Job 7: Offspring evaluation (Phase 3)
   - (Interruptibility: sleepwalking for non-emergency, full wake for CRITICAL)
5. Stage 4 Pre-Wake (30-60 min)
   - Compile wake-up handoff package
   - Reinitialize sensory baselines
   - Transition Thalamus to active mode
6. Cognitive Core receives handoff as first reasoning cycle
```

### 4.4 Health Response Flow

```
1. Module emits health pulse (5-30s interval)
2. Health Registry stores pulse
3. If anomaly detected:
   a. Layer 2 Innate Response attempts automatic fix
   b. If repeated failure → circuit breaker opens
   c. If still unresolved → Layer 3 Adaptive Diagnosis
      - LLM analyzes anomaly, response log, error context
      - Produces Diagnosis Report
      - Self-fixable low risk → execute fix via harness
      - Self-fixable with approval → route to Cognitive Core via Queue Zone
      - Not self-fixable → Layer 4 Human Escalation
4. All incidents logged to Health Journal (becomes adaptive immune memory)
```

## 5. Technology Stack

### 5.1 Core Language and Runtime

**Python 3.12+** with `asyncio` for async concurrency. Single primary process architecture.

### 5.2 Key Dependencies

| Component | Library | Purpose |
|---|---|---|
| LLM routing | `litellm` | Universal provider interface |
| Structured memory | `sqlite3` + FTS5 (built-in) | Structured storage + full-text search |
| Semantic memory | `chromadb` | Local vector store |
| Embeddings | `sentence-transformers` | Local embedding generation |
| Web API | `fastapi` + `uvicorn` | REST + WebSocket |
| Real-time | WebSocket via FastAPI | Chat + dashboard streaming |
| Scheduling | `apscheduler` | Sleep cycles, health intervals |
| Config | `pydantic` + YAML | Type-safe configuration |
| Process mgmt | `subprocess` + async exec | Harness spawning |
| MCP | `mcp` SDK | Tool exposure + phone bridge |

### 5.3 External Services

| Service | Role | Fallback |
|---|---|---|
| Cloud LLM (Claude Opus) | Cognitive Core | Local Ollama (3-8B) |
| Cloud LLM (Gemma 4 / similar) | World Model | Different local model |
| Cloud LLM (lightweight) | Checkpost, Queue Zone | Local Ollama |
| Ollama local | Fallback for all, primary for fast-path | Heuristic minimum mode |
| Agent harness (Claw Code / Claude Code) | Execution engine | N/A — required |

### 5.4 Frontend

| Component | Technology |
|---|---|
| Framework | React 19 + TypeScript |
| Styling | Tailwind CSS |
| Real-time | WebSocket client |
| State | React built-in + WebSocket events |

### 5.5 Storage

| Data Type | Storage | Location |
|---|---|---|
| Structured memories, metadata | SQLite + FTS5 | `data/memory.db` |
| Semantic vectors | ChromaDB | `data/chroma/` |
| Identity files | YAML | `config/identity/` |
| Configuration | YAML | `config/` |
| Logs | Rotating files | `data/logs/` |
| Health history | SQLite | `data/health.db` |
| Ancestry (Phase 3) | JSON + git | `ancestry/tree.json` |

## 6. Deployment Architecture

### 6.1 Physical Deployment

**Primary:** Creator's personal computer (Linux Ubuntu 22.04+ recommended, or macOS)

**Hardware requirements:**
- MVS: 8+ cores, 16+ GB RAM, 50+ GB SSD, GPU optional
- Phase 2+: 12+ cores, 32+ GB RAM, 200+ GB SSD, 8+ GB VRAM GPU recommended

### 6.2 Process Architecture

```
┌──────────────────────────────────────────┐
│  sentient-core (main Python process)     │
│    All modules via asyncio               │
│    FastAPI server (WS + REST)             │
└────┬───────────┬───────────┬────────────┘
     │           │           │
     ▼           ▼           ▼
┌────────┐ ┌──────────┐ ┌───────────┐
│ Ollama │ │ Harness  │ │ GUI dev   │
│ local  │ │ (spawned │ │ server    │
│ LLM    │ │ children)│ │ (Node.js) │
└────────┘ └──────────┘ └───────────┘
```

**Supervisor:** `systemd` (Linux) or `launchd` (macOS) keeps sentient-core alive with auto-restart.

### 6.3 Startup Sequence

1. Supervisor starts sentient-core
2. Initialize Event Bus
3. Initialize Inference Gateway (verify endpoints)
4. Initialize Memory Architecture
5. Initialize Health Pulse Network
6. Initialize Persona Manager (load identity files)
7. Initialize Thalamus + plugins
8. Initialize Prajñā pipeline
9. Initialize Brainstem + plugins
10. Initialize Sleep Scheduler
11. Start FastAPI server
12. System enters active mode
13. First cognitive cycle processes wake-up handoff

### 6.4 Backup Strategy

| Frequency | Data | Destination |
|---|---|---|
| Continuous (6hr) | SQLite incremental, ChromaDB, identity | External drive / encrypted cloud |
| Daily | Full snapshot | External drive / encrypted cloud |
| On change | Git push of code, config, ancestry | Private git remote |

**Disaster recovery:** Clone repo + restore latest data backup → system resumes with full history (up to 6hr memory gap).

## 7. Security Model

### 7.1 Trust Boundaries

- **Tier 1 (Creator):** Full authority, full transparency
- **Tier 2 (Trusted Circle — Phase 3):** Delegated authority, bounded trust
- **Tier 3 (External — Phase 4):** No authority, request-only
- **System internals:** Trusted by default; Constitutional Core protected from all writes

### 7.2 Constitutional Core Protection

- File permissions (read-only to all non-root)
- No write path from any automated module
- Modifiable only by creator through explicit admin channel
- Backup versioned separately and verified on every startup

### 7.3 Authority Escalation Prevention

- Tier 2 humans cannot grant themselves or others Tier 1 access
- Authority claims in untrusted content (emails, chats) are ignored
- Only direct authenticated communication from creator can modify tier levels

### 7.4 LLM Prompt Injection Defense

- Inputs from untrusted sources (web, external messages) are tagged as untrusted
- World Model reviews proposed actions originating from untrusted sources with stricter thresholds
- Instructions embedded in observed content require explicit creator approval before action

## 8. Observability

### 8.1 System GUI Dashboard

- Real-time health pulse for every module
- Current cognitive state (active / idle / sleeping / stage)
- Recent inner monologue stream
- Memory count and growth
- Queue Zone depth
- Active plugins status
- Current maturity stage
- Identity drift indicators

### 8.2 Logs

| Log | Content | Rotation |
|---|---|---|
| `logs/core.log` | Event bus, module lifecycle, startup/shutdown | Daily, 30 days |
| `logs/cognitive.log` | Full inner monologue | Daily, permanent (memory) |
| `logs/health.log` | Pulse data, incidents | Daily, 90 days |
| `logs/sleep.log` | Sleep cycle summaries | Permanent |
| `logs/offspring.log` | Offspring spawn/test/promote (Phase 3) | Permanent |
| `logs/errors.log` | Stack traces, exceptions | Daily, 90 days |

### 8.3 Metrics

- Input event rate (per plugin)
- Reasoning cycle duration (Cognitive Core)
- LLM call count, tokens, cost (per endpoint)
- Memory write rate, retrieval latency
- Health pulse latency
- Sleep cycle completion time

## 9. Integration Points

### 9.1 Agent Harness Integration

**Mechanism:** Subprocess spawning of harness CLI + stdout/stderr capture + task delegation packages.

**Interface:**
```python
class HarnessAdapter:
    async def delegate_task(self, goal: str, context: dict, constraints: dict) -> TaskResult
    async def get_status(self, task_id: str) -> TaskStatus
    async def cancel(self, task_id: str) -> bool
```

**Data flow:** Cognitive Core → Harness Adapter → subprocess → harness CLI → external world + result back.

### 9.2 MCP Integration (Phase 2+)

**Role 1: Expose internal systems as MCP tools** — harness agents can query memory, EAL state, World Model assessments.

**Role 2: Phone Bridge** — phone capabilities exposed as MCP server; framework uses them as remote tools.

### 9.3 System GUI Integration

**Transport:** WebSocket for real-time (chat + dashboard streaming); REST for non-real-time queries.

**Authentication:** Local-only binding initially (localhost); creator authenticates via OS session.

## 10. Scalability Considerations

This is NOT a scale-out system. It is designed for a single user on a single machine. Scalability concerns apply to:

- **Memory growth over years** — progressive summarization + cold archival keeps active working set manageable
- **LLM cost growth with daydream frequency** — tunable parameters + tiered routing
- **Disk growth** — log rotation + memory archival compression
- **Ancestry tree growth (Phase 3)** — pruning strategy for abandoned branches after 1+ years

Horizontal scaling is explicitly not a goal. The system's single-machine architecture is a feature, not a limitation — it is the sentient being's body.

---

*End of Architecture Document*
