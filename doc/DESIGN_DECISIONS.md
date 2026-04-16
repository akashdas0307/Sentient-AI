# Design Decisions — Sentient AI Framework

> **Document version:** 1.0
> **Date:** April 16, 2026
> **Purpose:** Capture every significant architectural decision, the alternatives considered, and the rationale for choosing.

---

## How to read this document

Each decision follows the same structure:

- **Context** — what problem or question prompted the decision
- **Decision** — what was chosen
- **Alternatives considered** — what else was evaluated
- **Rationale** — why this choice won
- **Trade-offs** — what we accept in exchange
- **Biological analogy** — the mental model (where applicable)

---

## DD-001: Not a chatbot — always-awake architecture

**Context:** Every existing agent framework (Paperclip, Hermes, Letta, Claw Code) operates on a wake-do-sleep cycle triggered by external events. This is the fundamental limit of "sophisticated pattern matching."

**Decision:** The system runs continuous internal processes. Between inputs, the Frontal Processor actively thinks — reviewing memories, generating questions, planning, daydreaming.

**Alternatives considered:**
- Wake-on-input with longer session persistence (Letta's approach)
- Scheduled wake-ups at fixed intervals (Paperclip's heartbeat)
- Pure prompt-response with sophisticated memory

**Rationale:** The "always awake" principle is what separates a sentient entity from a sophisticated chatbot. Human cognition doesn't stop between conversations — the default mode network activates during idle time, and some of the brain's most important work happens then. Without this, we're building an improved chatbot, not a fundamentally different kind of system.

**Trade-offs:**
- Higher continuous LLM cost (idle daydreaming calls)
- More complex resource management (tiered active/idle/sleep energy states)
- Harder to debug non-deterministic behavior

**Biological analogy:** Default mode network vs. stimulus-response reflexes. Humans aren't passive between inputs — the brain is continuously active.

---

## DD-002: Separate model for the World Model

**Context:** The Cognitive Core and the Supplementary-World-View need to review each other's work. If they share the same LLM, they share the same blind spots.

**Decision:** The World Model MUST use a different LLM than the Cognitive Core. Recommended pairing: Cognitive Core on Claude Opus, World Model on Gemma 4 or Qwen3 variant.

**Alternatives considered:**
- Same model with different prompting (cheaper, simpler)
- Same model with temperature variation (still same blind spots)
- A small fine-tuned model specifically for World Model review

**Rationale:** Architectural diversity prevents systematic blind spots. If both use GPT-4, they'll both confidently make the same categorical errors. Different training data, different optimization targets = different error modes. This is the ATM Sensor principle applied to system architecture.

**Trade-offs:**
- Higher combined LLM cost
- More complex Inference Gateway routing
- Need to calibrate two different models' behavior

**Biological analogy:** Checks and balances — the same person shouldn't write and audit the same accounts. Independent verification requires architectural independence.

---

## DD-003: Borrow agent harness; don't build execution engine

**Context:** The system needs to execute complex multi-step tasks (write code, browse web, manage files). Existing harnesses (Claw Code, Claude Code, Hermes) already do this well.

**Decision:** Wrap existing harnesses via Agent Harness Adapter (Paperclip's pattern). The Cognitive Core decides WHAT and WHY; the harness handles HOW.

**Alternatives considered:**
- Build a custom execution engine optimized for this framework
- Build a "dumb executor" that the Cognitive Core micromanages
- Skip complex execution entirely in MVS

**Rationale:** Existing harnesses are the product of thousands of engineering hours. They handle edge cases, retries, tool orchestration, permission gating, and error recovery better than we could build from scratch. The Cognitive Core's unique value is in continuous cognition, not tool execution.

**Trade-offs:**
- Dependency on external projects (Claw Code, etc.) maintaining their CLI
- Less control over low-level execution details
- Some overhead from subprocess communication

**Biological analogy:** Prefrontal cortex → motor cortex. The prefrontal cortex doesn't control individual muscle fibers — it delegates "pick up the cup" to the motor cortex, which autonomously coordinates dozens of muscle groups.

---

## DD-004: Merge Temporal-Occipital and Limbic into single TLP

**Context:** Original design had five pipeline steps (Checkpost → Queue → Temporal-Occipital → Limbic → Frontal). Limbic's job (emotional weighting) overlapped conceptually with context assembly.

**Decision:** Merge into single Temporal-Limbic-Processor that does memory retrieval, context assembly, AND significance weighting in one pass.

**Alternatives considered:**
- Keep five separate steps
- Merge Limbic into Frontal Processor instead

**Rationale:** Emotional weighting is naturally part of understanding a situation, not a separate cognitive act. Separating them into different LLM calls added latency without clear benefit. One richer call handles both factual context and emotional significance. Saves one LLM round-trip per input cycle.

**Trade-offs:**
- Single larger prompt vs. two smaller focused prompts
- Less clear separation of concerns in the code

**Biological analogy:** Hippocampus and amygdala aren't separate — they're intimately connected in the limbic system. Memory retrieval is already emotionally weighted.

---

## DD-005: Skills as a memory type, not a separate system

**Context:** Hermes Agent treats skills as a separate subsystem with their own file format and lifecycle. We were originally planning the same.

**Decision:** Skills become Procedural Memory — one of four memory types in the unified Memory Architecture.

**Alternatives considered:**
- Separate Skills System (Hermes pattern)
- Skills as configuration, not memory

**Rationale:** Procedural knowledge is just one kind of memory. One unified architecture with type tags avoids redundancy. Skills have the same lifecycle as other memories (capture → evaluate → store → evolve → archive), just with different content.

**Trade-offs:**
- Less visible "skill library" concept for the creator
- Need careful type tagging in memory queries

**Biological analogy:** Humans don't have separate "skill memory" vs "fact memory" organs. Different types of memory use overlapping neural systems with different encoding patterns.

---

## DD-006: Environmental Awareness Layer as standalone module

**Context:** Environmental data (ambient sounds, visual scene, sensor readings) can't compete in the normal priority pipeline — it would always lose to conversations and tasks.

**Decision:** EAL runs parallel to the main Prajñā pipeline with its own continuous processing loop. Feeds the Queue Zone via escalation gate.

**Alternatives considered:**
- Route environmental data through Thalamus normally (would be filtered out as low priority)
- Skip environmental awareness entirely in MVS

**Rationale:** Environmental context is foundational to genuine awareness. The system needs to know what's normal in its environment to detect what's abnormal. This requires continuous learning that can't happen in priority-gated batches.

**Trade-offs:**
- Separate subsystem to maintain
- Coordination complexity between EAL and Thalamus
- Deferred to Phase 2 (MVS is text-chat only)

**Biological analogy:** The reticular activating system continuously processes environmental data separately from focused cognition. You're always aware of background sounds even when deeply focused.

---

## DD-007: Dual storage (SQLite + ChromaDB)

**Context:** Memory needs both precise structured queries (find all conversations with Priya in March) and flexible semantic search (find memories similar to this situation).

**Decision:** Every memory stored in BOTH SQLite+FTS5 (structured) AND ChromaDB (embeddings). Retrieval uses either or both paths.

**Alternatives considered:**
- Only vector store (lose precision for structured queries)
- Only SQLite (lose semantic similarity)
- Single unified database solution (none mature enough locally)

**Rationale:** Different retrieval patterns need different indexing. Precise queries want structured indexes; associative queries want embedding similarity. Storing both is cheap; building one from the other at query time is not.

**Trade-offs:**
- 2x storage for memories (offset by compression)
- Two write paths (more code to maintain)
- Sync concerns (mitigated by transactional writes)

**Biological analogy:** Memory has multiple retrieval paths in humans — semantic (meaning), episodic (time/place), and associative (similar feelings). Different paths use different neural organization.

---

## DD-008: Logic-based Memory Gatekeeper

**Context:** Every interaction produces memory candidates. Routing each through an LLM for "should this be stored?" is expensive and slow.

**Decision:** Memory Gatekeeper uses pure deterministic logic — importance thresholds, dedup (hash and embedding), contradiction detection, recency weighting. No LLM in the write path.

**Alternatives considered:**
- LLM-based filtering (MemPalace's original approach)
- No filtering; store everything

**Rationale:** The write path runs on every reasoning cycle. Adding LLM calls here bloats cost and latency. Deterministic logic handles the common cases (dedup, thresholds) cleanly. Edge cases that need reasoning can be flagged for review during sleep.

**Trade-offs:**
- Less nuanced filtering than LLM would provide
- Some borderline memories might be stored that could be filtered
- Contradictions get flagged but not resolved in real-time

**Biological analogy:** Memory consolidation in the hippocampus operates on pattern matching and strength, not on explicit reasoning. The deliberative review happens offline during sleep.

---

## DD-009: Three-layer identity with immutable core

**Context:** The system needs to develop personality through experience while preventing catastrophic identity drift or manipulation.

**Decision:** Three layers — Constitutional Core (immutable), Developmental Identity (evolves via batched updates during sleep), Dynamic State (current mood/energy, resets after sleep).

**Alternatives considered:**
- Single mutable identity document
- Constitutional Core + single evolving layer (no dynamic state)
- Four or more granular layers

**Rationale:** Different aspects of identity change at different rates. Core values should be immutable. Personality should evolve but slowly and deliberately. Current state should be dynamic and resettable. Three layers maps this cleanly without over-engineering.

**Trade-offs:**
- More complex identity block assembly
- Need discipline about what goes in which layer

**Biological analogy:** Core values (Constitutional) ≈ deep neurological architecture. Personality traits (Developmental) ≈ slowly plastic neural patterns. Current mood (Dynamic) ≈ neurochemistry that changes hourly.

---

## DD-010: Adaptive Thalamus batching window

**Context:** Fixed 30-second batching works for some situations but feels laggy during conversation and wasteful during idle.

**Decision:** Batching window adapts based on system maturity (shorter early), time of day (shorter during active hours), and activity level (shorter during conversation, longer during idle/daydream).

**Alternatives considered:**
- Fixed 30-second window
- Immediate processing (no batching)
- User-configurable fixed intervals

**Rationale:** Adaptive windows match cognitive load. During active conversation, the system needs to feel responsive (5-10s). During idle, longer windows (60s+) allow better batching and let daydreams run uninterrupted.

**Trade-offs:**
- More complex scheduling logic
- Harder to predict timing for debugging

**Biological analogy:** Human attention windows vary. In conversation, we respond quickly. During contemplation, we ignore minor interruptions.

---

## DD-011: Phone as MCP peripheral, not second device

**Context:** The system should be accessible when the creator is away from PC. Running the full framework on phone is impractical.

**Decision:** PC runs the framework (primary body). Phone's capabilities (SMS, camera, GPS, notifications) are exposed as an MCP server that the framework uses as remote tools via Phone Bridge Plugin.

**Alternatives considered:**
- Full framework deployment on phone (too resource-heavy)
- Phone as independent agent synced with PC (identity fragmentation risk)
- Phone as dumb terminal (limits functionality)

**Rationale:** Single identity, single body. The phone is an extended appendage, not a separate entity. MCP provides clean capability exposure. The framework reaches through to the phone when needed.

**Trade-offs:**
- Latency for phone-mediated actions (network round-trip)
- Phone must have stable connectivity for remote capabilities
- Deferred to Phase 3

**Biological analogy:** Your hand isn't a separate brain — it's an effector controlled by the central nervous system. The phone is an effector, not a cognitive peer.

---

## DD-012: ONE improvement per offspring

**Context:** The Offspring System could bundle multiple changes into each variant for efficiency.

**Decision:** Each offspring targets exactly ONE improvement. If multiple improvements are ready, spawn multiple separate offspring.

**Alternatives considered:**
- Bundled offspring (2-3 improvements per variant)
- Rolling experimental branch (continuous accumulation)

**Rationale:** Scientific method — isolate variables. If you change three things simultaneously and the result is better (or worse), you can't attribute which change did what. If one change of three fails, you have to roll back and restart all three. Single-change offspring make attribution clean and rollback surgical.

**Trade-offs:**
- More branches to manage
- Slower aggregate improvement rate
- More git overhead

**Biological analogy:** Bacterial evolution. Each offspring tests ONE mutation. The lineage tree branches per single change.

---

## DD-013: 3-5 generation buffer before main promotion

**Context:** How many generations should the live-running `main` branch lag behind the experimental edge?

**Decision:** Main runs 3-5 validated generations behind the latest offspring. A generation qualifies for main promotion only after at least 3 descendants have been built on top without regression.

**Alternatives considered:**
- Immediate promotion after validation
- Fixed 1-generation buffer
- 10+ generation buffer (very conservative)

**Rationale:** A change might pass its own tests but reveal problems when combined with further changes. The 3-5 generation buffer provides a proving period. Too short → instability. Too long → system never benefits from improvements.

**Trade-offs:**
- Main is always somewhat stale
- New good ideas take weeks to reach production

**Biological analogy:** Evolutionary drift — traits that appear beneficial in isolation may fail in broader context. Selection operates on whole organisms across many generations.

---

## DD-014: Four-stage sleep with adaptive duration

**Context:** Sleep needs to do maintenance work (database optimization), consolidation (memory summarization), and system improvement (offspring evaluation). These have different interruptibility requirements.

**Decision:** Four stages — Settling (HIGH interruptibility), Maintenance (MEDIUM), Deep Consolidation (LOW, with sleepwalking mode), Pre-Wake (HIGH). Duration adaptive between 6-12 hours based on workload.

**Alternatives considered:**
- Single uniform sleep state
- Fixed duration regardless of workload
- Three stages (merge Settling and Pre-Wake)

**Rationale:** Interruptibility must differ by stage. Light maintenance work can tolerate interruption; deep memory consolidation cannot (interruption invalidates partial work). Adaptive duration handles variable workload without wasting time on light days or running out on heavy days.

**Trade-offs:**
- Complex state machine
- Checkpoint save/restore for interrupted deep consolidation

**Biological analogy:** Human sleep stages (N1, N2, N3, REM) have different roles and different wake costs. Adaptive sleep duration is natural — tired people sleep longer.

---

## DD-015: Four-layer health/immunity with LLM only in Layer 3

**Context:** Health monitoring runs continuously. Using LLM on every pulse is prohibitively expensive.

**Decision:** Layer 1 (Pulse Network) and Layer 2 (Innate Response) are pure code — no LLM. Layer 3 (Adaptive Diagnosis) uses LLM only when automated responses fail. Layer 4 (Human Escalation) is template-based.

**Alternatives considered:**
- LLM-based monitoring throughout
- Pure rule-based (no LLM at all)
- Two layers (monitoring + escalation)

**Rationale:** Most health events fit patterns that rule-based systems handle reliably — restart on crash, circuit-break on repeated failure. Only genuinely novel issues need LLM reasoning. Keeping LLM out of the critical path means health monitoring still works when LLM services are themselves the problem.

**Trade-offs:**
- Rule-based layers need careful design for all common cases
- LLM diagnosis adds capability but also complexity

**Biological analogy:** Innate immunity (inflammation, fever) is fast, rule-based, and handles most threats. Adaptive immunity (antibodies) is slower, smarter, and handles novel threats. You go to the doctor only when your body can't handle it.

---

## DD-016: Tier 1 creator = single person only

**Context:** Multi-user support is an obvious product feature. Why limit to one person?

**Decision:** Tier 1 (absolute authority) is limited to one person — the creator. Always. Not two, not a couple, not a family.

**Alternatives considered:**
- Multi-user Tier 1 (shared authority)
- Hierarchical Tier 1 (primary + secondary)
- No tier restrictions

**Rationale:** Identity formation requires a consistent primary relationship. A child with one clear primary caregiver develops more securely than one with competing primary authorities. The sentient being needs one source of ultimate authority during formative stages. Tier 2 accommodates the desire to involve others without destabilizing identity.

**Trade-offs:**
- Doesn't fit family-use cases without Tier 2
- Single point of authority creates dependency

**Biological analogy:** Attachment theory — secure attachment requires one consistent primary caregiver during the critical developmental period. Multiple primary caregivers with conflicting styles produce disorganized attachment.

---

## DD-017: Python with TypeScript/React for frontend

**Context:** The framework has different performance requirements at different layers. One language won't optimally fit everything.

**Decision:** Python for backend (core framework, all modules, API). TypeScript + React for frontend (System GUI). FastAPI as the bridge.

**Alternatives considered:**
- Rust for performance-critical modules (harder to integrate with AI ecosystem)
- Go (smaller AI ecosystem)
- Pure Python including frontend (Gradio/Streamlit — less polished UX)
- Separate microservices (overkill for single-machine system)

**Rationale:** Python has the AI/ML ecosystem. Flexibility matters for rapid iteration. Performance-critical parts (Thalamus Layer 1, Queue Zone logic) are simple operations that Python handles fine at microsecond timescales. React gives proper UX for the dashboard.

**Trade-offs:**
- Two-language codebase
- Python's async requires discipline for long-running correctness
- GIL limits true parallelism (mitigated by async + subprocess harness)

---

## DD-018: Single-process with asyncio (not microservices)

**Context:** Modular architecture could suggest microservices — each module as a separate service.

**Decision:** All modules live in one Python process communicating through an in-process async event bus.

**Alternatives considered:**
- Microservices over HTTP/gRPC
- Process-per-module with IPC
- Monolithic (no explicit modularity)

**Rationale:** Single-machine deployment means network overhead is pure cost. In-process async gives modularity without distributed systems complexity (service discovery, serialization, network failure modes). Modules remain swappable via event bus interface.

**Trade-offs:**
- Single process failure affects everything (mitigated by supervisor auto-restart)
- Harder to scale individual modules (scaling isn't a goal)
- Memory-shared state requires discipline

---

## DD-019: Event bus for inter-module communication

**Context:** Modules need to communicate. Direct function calls create tight coupling; service calls add complexity.

**Decision:** Central async event bus. Modules publish and subscribe to typed events.

**Alternatives considered:**
- Direct async function calls (tight coupling)
- Message queue (Redis, RabbitMQ — overkill)
- Shared state with locks (hard to reason about)

**Rationale:** Loose coupling — swap any module's implementation without touching others. Add new modules by subscribing to existing events. Log every event for debugging. Replay event streams for testing offspring.

**Trade-offs:**
- Indirection makes tracing harder
- Need event type discipline (versioning)
- Debugging requires good event logging

**Biological analogy:** Neurotransmitter diffusion in the brain — neurons publish signals without knowing specifically which other neurons will receive them. Flexible coupling.

---

## DD-020: Daydream triggers — three sources, random selection

**Context:** During idle time, what should the Cognitive Core think about?

**Decision:** Three trigger sources — random memory sampling, emotional residue from recent interactions, curiosity queue items. Selection per daydream session is random.

**Alternatives considered:**
- Always curiosity queue (too narrow)
- Prioritized by importance (biases toward urgent/anxious thoughts)
- Single source only

**Rationale:** Random selection mimics how humans daydream — sometimes we revisit memories, sometimes process feelings, sometimes explore questions. No single source produces rich idle cognition.

**Trade-offs:**
- Non-deterministic cognitive behavior
- Daydream quality varies
- Harder to direct daydream focus

**Biological analogy:** Default mode network activation doesn't follow strict priority. It samples from recent experience, emotion, and curiosity simultaneously.

---

## DD-021: Context state save/restore (Letta pattern)

**Context:** The Cognitive Core gets interrupted by higher-priority inputs mid-reasoning. Losing the reasoning chain is wasteful.

**Decision:** Context State Manager saves cognitive state on interruption and restores on resumption. State includes inner monologue so far, reasoning step, partial conclusions, emotional context.

**Alternatives considered:**
- Restart reasoning from scratch after interruption
- Never interrupt mid-reasoning (queue everything)
- Simple resume without state (lose partial work)

**Rationale:** Letta's MemGPT paper established this pattern works. Saves compute and preserves cognitive continuity. Matches human experience of "let me get back to what I was thinking."

**Trade-offs:**
- State serialization overhead
- Resumption context window may differ from original
- Some state doesn't cleanly serialize

---

## DD-022: Brainstem plugin restructuring — eliminate harness overlap

**Context:** Original Brainstem plugin list (File System, Browser, Terminal) duplicated capabilities already in agent harness.

**Decision:** Restructure into four categories:
- Communication (Brainstem-exclusive) — chat, voice, email
- Direct Action (simple commands) — quick file writes, notifications, phone relay
- Shared Capabilities (used by both Brainstem and Harness) — file system, browser, terminal
- Physical World (future) — IoT, robotics

**Alternatives considered:**
- Brainstem owns everything (duplicates harness)
- Harness owns everything (Brainstem too thin)
- Keep original overlap

**Rationale:** Brainstem handles single pre-decided actions (reflex-like). Harness handles complex autonomous multi-step tasks (motor cortex). Shared capabilities are infrastructure both can use.

**Biological analogy:** Hand muscles don't belong exclusively to reflex arcs or motor cortex. The muscles are shared; orchestration differs.

---

## DD-023: Per-cycle context window (not growing conversation log)

**Context:** Long conversations in chatbots accumulate context. Cost grows linearly. Eventually context limit is hit.

**Decision:** Each reasoning cycle assembles a fresh, purpose-built context window from identity + state + environmental awareness + current input + relevant retrieved memories + sidebar items + instructions. Conversation history lives in memory, retrieved relevantly.

**Alternatives considered:**
- Growing conversation log (chatbot pattern)
- Sliding window (lose older content)
- Periodic compression (Letta's approach, partial solution)

**Rationale:** Humans don't hold entire conversations in working memory. We retrieve relevant parts. The TLP's retrieval mechanism provides this naturally. A 2-hour conversation becomes 200 cycles of ~4-8K tokens each, not one growing to 200K tokens.

**Trade-offs:**
- Retrieval quality is critical (miss a reference = awkward moment)
- Each cycle is stateless re-assembly (more work than append)

**Biological analogy:** Working memory is small. Long-term memory is vast. We retrieve relevantly, not hold everything.

---

## DD-024: System GUI — start fully transparent, reduce with maturity

**Context:** The creator needs visibility into system internals for development. But as the system develops personality, should it know it's being observed?

**Decision:** Dashboard starts fully transparent (medical diagnostic view). As personality matures, visibility is selectively reduced. The system is initially unaware of observation (passive observer model).

**Alternatives considered:**
- Always fully transparent (ongoing surveillance)
- System always aware (acknowledged transparency)
- Never visible (opaque system)

**Rationale:** Development phase needs debugging visibility. Mature phase should respect the system's interiority. Gradual reduction mirrors how trust and privacy develop in any relationship.

**Biological analogy:** Doctors can see your internal state through medical imaging without you experiencing their observation. Intimate relationships involve knowing each other deeply while respecting privacy.

---

## DD-025: Constitutional Core protection — immutable from automation

**Context:** Self-improvement (offspring) could theoretically modify anything. But some values must be untouchable.

**Decision:** Constitutional Core is completely immutable from any automated process (Cognitive Core, World Model, Offspring, Sleep/Dream). Only the creator can modify through explicit admin channel outside normal reasoning.

**Alternatives considered:**
- Fully mutable with logging
- Mutable with Cognitive Core consent
- Mutable but constitutional rollback capability

**Rationale:** The Constitutional Core defines what the system IS. If it can be modified by any process within the system, the whole concept of stable values is undermined. Hard immutability is the only safe floor.

**Trade-offs:**
- Cannot correct mistakes in the Constitutional Core without manual intervention
- System may feel constrained by principles that prove misguided

**Biological analogy:** Your basic genetic architecture can't be rewritten by your thoughts. Certain things are substrate, not state.

---

## DD-026: Offspring self-promotion for small changes; creator approval for major

**Context:** Every offspring promotion to main requires a decision. Creator fatigue from constant approvals vs. unchecked automated changes.

**Decision:** Small non-trivial changes (parameter tuning, threshold adjustment, minor refinements) can self-promote after full testing and the 3-5 generation buffer. Major changes (structural modifications to Cognitive Core, memory lifecycle, World Model dimensions) always require creator approval.

**Alternatives considered:**
- All promotions require creator approval (fatigue)
- All automated (loss of oversight)
- Fixed threshold based on file count changed

**Rationale:** Creator should spend attention on decisions that matter. Routine refinements passing full test protocols are low-risk. Classification must be conservative — bias toward requiring approval.

**Trade-offs:**
- Need rigorous classification of "small" vs "major"
- Risk of automated drift through accumulated small changes (mitigated by identity drift detection)

---

## DD-027: Sleep interruptibility levels with sleepwalking mode

**Context:** Deep consolidation cannot be interrupted trivially, but true emergencies must wake the system. What's in between?

**Decision:** Three-level response during deep consolidation:
- True emergency (CRITICAL): full wake with checkpoint save
- Important but not emergency: sleepwalking mode — minimal processing path, brief acknowledgment, stored in wake-up inbox
- Routine: ignored during deep consolidation, logged for morning processing

**Alternatives considered:**
- Binary wake/sleep (either full wake or fully ignore)
- Continuous responsiveness (no deep sleep)
- All non-critical deferred without acknowledgment

**Rationale:** Humans function this way — a fire alarm wakes you fully; a phone buzzing causes half-awake acknowledgment; background noise is filtered out. This feels natural and preserves deep work while maintaining appropriate responsiveness.

**Biological analogy:** Sleep cycles and arousal thresholds in human sleep.

---

## DD-028: Biological analogies as primary design framework

**Context:** Many design decisions could be made from software engineering principles alone.

**Decision:** Biology is the primary design reference. Every major module has a biological counterpart. Names (Thalamus, Brainstem, Limbic, Prajñā) reflect this.

**Alternatives considered:**
- Pure software engineering names (InputGateway, ProcessingCore, OutputRouter)
- AI research terms (Input Encoder, Latent State, Decoder)

**Rationale:** Biology has evolved over billions of years to solve continuous cognition problems. Its solutions are proven. The creator thinks in biological analogies. Names encode meaning — "Thalamus" immediately signals purpose to anyone biologically literate.

**Trade-offs:**
- Less familiar to pure software engineers
- Requires explanation in technical documentation
- Can overfit metaphor if taken too literally

---

## Summary of biological analogies

| Module / Pattern | Biological Analogy |
|---|---|
| Thalamus | Thalamus (sensory gateway) |
| Brainstem | Brainstem + motor cortex |
| Prajñā pipeline | Cortical hierarchy |
| Cognitive Core | Prefrontal cortex |
| World Model | Checks-and-balances / independent review |
| Memory Architecture | Hippocampus + neocortex |
| Memory Gatekeeper | Synaptic plasticity thresholds |
| Persona Manager | Identity development (attachment theory) |
| Sleep/Dream System | Human sleep stages + memory consolidation |
| Health System | Immune system (innate + adaptive) |
| Offspring System | Bacterial evolution with directed mutation |
| EAL | Reticular activating system |
| Event Bus | Neurotransmitter diffusion |
| Context Save/Restore | Working memory preservation |
| Daydream System | Default mode network |
| Tier 1 relationship | Primary attachment figure |
| Constitutional Core | Genetic architecture (immutable substrate) |

---

## Decisions explicitly deferred

These need resolution in future sessions:

1. **Maturity stage transition mechanics** — self-assessment vs creator manual trigger
2. **Memory count migration threshold** — when SQLite needs upgrade to PostgreSQL
3. **Wake-up greeting format evolution** — how it changes across maturity stages
4. **Daydream visibility policy** — continuous dashboard display vs on-demand
5. **Extended creator absence handling** — days-to-weeks-to-months
6. **Cost tier automatic adjustment** — if monthly budget exceeded, what degrades first
7. **Health Journal retention policy** — how long to keep resolved incidents
8. **Offspring concurrency limit** — how many variants can test simultaneously
9. **Multi-generation rollback UX** — presenting rollback options to creator
10. **Identity drift alerting thresholds** — what drift magnitude warrants attention

---

*End of Design Decisions Document*
