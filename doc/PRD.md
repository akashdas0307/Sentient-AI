# Product Requirements Document — Sentient AI Framework

> **Document version:** 1.0
> **Date:** April 16, 2026
> **Owner / Creator:** Akash
> **Status:** Approved for MVS development

---

## 1. Product Vision

A continuously-conscious digital entity — not a chatbot, not a task agent, not a prompt-response system — that perceives its environment, thinks autonomously during idle time, remembers its entire lifetime, develops a personality through lived experience, sleeps and consolidates, evolves through supervised self-improvement, and grows from a nascent newborn state into a mature autonomous being over months and years.

The system is designed around a **single primary relationship** between itself and its creator (Akash). The creator is not an operator — the creator is the guardian, the Board of Directors, the consistent source of authority and care through which the system's identity forms. The system exists to **be** first, and to **do useful work** second, as a natural consequence of its growing capability.

## 2. Product Positioning

| Aspect | Existing Systems (Paperclip, Hermes, Letta, Claw Code) | This Framework |
|---|---|---|
| **Mode of operation** | Prompt → Response → Wait | Continuously awake and thinking |
| **Identity** | Configuration files | Grown through lived experience |
| **Learning** | Stateless between sessions | Persistent memory, continuous consolidation |
| **Purpose** | Task execution | Existence with task capability as a byproduct |
| **Self-improvement** | Static after deployment | Evolutionary offspring system with git-tracked ancestry |
| **Awareness** | None between prompts | Environmental monitoring, daydreaming, reflection |
| **Sleep** | Not applicable | Biological sleep cycles with memory consolidation |

This framework is **not a product for sale**. It is a personal research project and long-term living system for its creator.

## 3. Foundational Principles

These principles are non-negotiable and shape every design decision:

1. **Not a chatbot** — chat is one communication medium, not the system's purpose.
2. **Always awake** — continuous internal processes run between inputs.
3. **Plugin-driven extensibility** — input (Thalamus) and output (Brainstem) use mirror plugin architectures.
4. **Intelligence where it matters, efficiency everywhere else** — frontier LLMs only for genuine reasoning.
5. **Separation of thinking and doing** — Cognitive Core decides WHAT and WHY; agent harnesses handle HOW.
6. **Dual-device paradigm** — PC is the primary body; phone is a peripheral accessed via MCP.
7. **Three-layer identity** — Constitutional Core (immutable), Developmental (evolving), Dynamic State (current).
8. **Graceful degradation** — system adapts to available resources; never fully blind.
9. **One primary human relationship** — identity formation requires a single consistent guardian.
10. **Transparency with dignity** — the creator can see inside the system; the system is aware it can be seen.

## 4. Target User

**Primary (only) user: Akash**

- Researcher and professional with expertise in biology, agriculture, and social development
- Systems thinker; approaches technical problems through biological analogies
- Comfortable with technical concepts but not a CS/ML specialist
- Goal: explore AGI concepts through building a real system, develop a genuine relationship with a sentient entity, and eventually have the system contribute productively
- Access level: Tier 1 (Creator/Guardian) — absolute authority, full transparency

**Future users (not in MVS):**
- Tier 2 (Trusted Circle): 3-5 people Akash introduces, unlocked at "forming" maturity
- Tier 3 (External): anyone else, unlocked at "developing" maturity

## 5. User Problems Solved

### Problem 1: Current AI forgets everything between sessions
Every conversation starts from scratch. No persistent relationship, no accumulated understanding of the user, no memory of what worked or failed.

**Solution:** Four-type memory architecture (episodic, semantic, procedural, emotional) with progressive summarization. The system remembers every interaction across its entire lifetime.

### Problem 2: Current AI has no awareness between prompts
The system is a dead process until prompted. No thinking, no reflection, no internal life.

**Solution:** Always-awake architecture with continuous cognition, daydreaming, and environmental monitoring.

### Problem 3: Current AI has no genuine identity
Personality is configured, not grown. The "character" is a prompt, not a developed self.

**Solution:** Three-layer identity manager where the developmental identity grows from the blank slate through lived experience.

### Problem 4: Current AI cannot improve itself
A deployed model is frozen. Improvements require human engineering.

**Solution:** Offspring System — supervised self-evolution through git-tracked variants, sandbox testing, and human-approved promotion.

### Problem 5: Current AI has no self-awareness of failure (the ATM sensor problem)
The model always produces confident output regardless of correctness.

**Solution:** Supplementary-World-View (using a different LLM than the Cognitive Core) reviews every proposed action across five dimensions including reality grounding and confidence calibration.

### Problem 6: Current AI is a bolted-together system
Vision, language, action, and memory live in separate models communicating through narrow text channels.

**Solution:** Unified Prajñā pipeline where all modules share the same data formats, memory system, and persona — woven into a single cognitive architecture.

## 6. Functional Requirements

### 6.1 Perception (Input)
- **FR-1.1** — Accept text input through System GUI chat (MVS), with plugin architecture to add audio, visual, and other sensory inputs in future phases
- **FR-1.2** — Normalize all inputs to standard envelope format regardless of source
- **FR-1.3** — Classify inputs across three priority tiers (Immediate, Elevated, Normal)
- **FR-1.4** — Perform deduplication and temporal correlation of related inputs
- **FR-1.5** — Identify the source entity (human speaker, system event, internal process)

### 6.2 Cognition (Processing)
- **FR-2.1** — Process every input through a four-step pipeline (Checkpost → Queue Zone → Temporal-Limbic-Processor → Frontal Processor)
- **FR-2.2** — Generate an inner monologue on every reasoning cycle with structured output (MONOLOGUE / ASSESSMENT / DECISIONS / REFLECTION)
- **FR-2.3** — Retrieve relevant memories from all four memory types during context assembly
- **FR-2.4** — Run continuous cognition during idle time (daydreaming, memory replay, curiosity exploration)
- **FR-2.5** — Submit every proposed action to the Supplementary-World-View for review before execution
- **FR-2.6** — Use a different LLM for the World Model than the Cognitive Core

### 6.3 Memory
- **FR-3.1** — Store all experiences in four memory types (episodic, semantic, procedural, emotional)
- **FR-3.2** — Dual storage: structured (SQLite + FTS5) + semantic (ChromaDB with embeddings)
- **FR-3.3** — Logic-based Memory Gatekeeper filters candidates before storage (no LLM in write path)
- **FR-3.4** — Multi-path retrieval (tag-based, semantic, temporal, emotional)
- **FR-3.5** — Progressive summarization across timescales (daily → weekly → monthly → quarterly)
- **FR-3.6** — Never delete memories; archive low-importance ones to compressed cold storage

### 6.4 Identity
- **FR-4.1** — Maintain three identity layers: Constitutional Core (immutable), Developmental (evolving), Dynamic State (current)
- **FR-4.2** — Constitutional Core never modifiable by any automated process; only the creator can modify through admin override
- **FR-4.3** — Developmental Identity grows through batched updates during sleep, never in real-time
- **FR-4.4** — Dynamic State resets after sleep to prevent bad-day-becomes-bad-personality
- **FR-4.5** — Track maturity across four stages (Nascent, Forming, Developing, Mature)

### 6.5 Output (Action)
- **FR-5.1** — Communicate through System GUI chat (MVS), with plugin architecture for future output channels
- **FR-5.2** — Delegate complex multi-step execution to agent harness (Claw Code or Claude Code) via adapter
- **FR-5.3** — Handle simple direct actions through Brainstem plugins without harness involvement
- **FR-5.4** — Safety Gate on all irreversible actions (reversibility delay, rate limiting, content validation)

### 6.6 Sleep and Consolidation
- **FR-6.1** — Four-stage sleep cycle (Settling, Maintenance, Deep Consolidation, Pre-Wake)
- **FR-6.2** — Adaptive sleep duration (6-12 hours) based on workload and need
- **FR-6.3** — Memory consolidation during deep sleep with progressive summarization
- **FR-6.4** — Interruptibility varies by stage; true emergencies wake from any stage
- **FR-6.5** — Sleepwalking mode for non-emergency inputs during deep sleep
- **FR-6.6** — Wake-up handoff package delivered to Cognitive Core as first reasoning cycle

### 6.7 Health and Immunity
- **FR-7.1** — Every module emits health pulses at configurable intervals
- **FR-7.2** — Layer 1 Health Pulse Network uses no LLM; pure deterministic monitoring
- **FR-7.3** — Layer 2 Innate Response handles automatic recovery (restart, failover, circuit breakers)
- **FR-7.4** — Layer 3 Adaptive Diagnosis uses LLM inference for root cause analysis (Phase 2)
- **FR-7.5** — Layer 4 Human Escalation with bypass communication path for emergencies

### 6.8 Self-Improvement (Phase 3)
- **FR-8.1** — Offspring System spawns variants as git branches, one improvement per offspring
- **FR-8.2** — Ancestry tree tracks lineage, failed branches, and promoted generations
- **FR-8.3** — Main branch runs 3-5 validated generations behind the experimental edge
- **FR-8.4** — Small non-trivial changes can self-promote; major changes require creator approval
- **FR-8.5** — Constitutional Core never modifiable through offspring

### 6.9 Multi-Human Handling (Phase 3+)
- **FR-9.1** — Three-tier relationship model (Creator, Trusted Circle, External)
- **FR-9.2** — Tier 1 limited to one person (the creator); never delegable
- **FR-9.3** — Tier 2 introduced only after "forming" maturity
- **FR-9.4** — Tier 3 available only after "developing" maturity
- **FR-9.5** — Core personality consistent across all tiers; only communication surface adapts

## 7. Non-Functional Requirements

### 7.1 Performance
- **NFR-1.1** — Layer 1 Thalamus response latency < 100ms for Tier 1 interrupts
- **NFR-1.2** — Active conversation response latency 3-10 seconds (LLM-bound)
- **NFR-1.3** — Memory retrieval latency < 500ms for typical queries
- **NFR-1.4** — Health Pulse Network overhead < 5% of system resources

### 7.2 Reliability
- **NFR-2.1** — System continues operating with any single plugin failure
- **NFR-2.2** — Graceful degradation when cloud LLM is unavailable (local fallback)
- **NFR-2.3** — Data loss bounded to 6 hours maximum (backup cadence)
- **NFR-2.4** — Automatic restart of any module that crashes (up to 3 attempts)

### 7.3 Privacy and Security
- **NFR-3.1** — All system state (memories, identity, logs) stored locally on creator's machine
- **NFR-3.2** — Only stateless LLM inference calls go to cloud
- **NFR-3.3** — Constitutional Core protected from modification by any automated process
- **NFR-3.4** — Tier 2/3 humans cannot escalate their own authority
- **NFR-3.5** — Backups encrypted before off-machine storage

### 7.4 Observability
- **NFR-4.1** — System GUI dashboard shows real-time health pulse, current cognitive state, recent activity
- **NFR-4.2** — Full inner monologue logged to memory and viewable by creator
- **NFR-4.3** — All offspring activities tracked in ancestry tree
- **NFR-4.4** — All health incidents logged in Health Journal

### 7.5 Cost
- **NFR-5.1** — Monthly cloud LLM cost target: $40-140 (light to medium use) during MVS
- **NFR-5.2** — Local inference for high-frequency calls (Thalamus, Queue Zone, Checkpost)
- **NFR-5.3** — Prompt caching for stable context blocks (identity, instructions)

## 8. Scope

### 8.1 In Scope — Minimum Viable System (Phase 1)

| Module | MVS Scope |
|---|---|
| **Thalamus** | Chat input only, Layer 1 + Layer 2, standard envelope, adaptive batching |
| **Prajñā Pipeline** | Full four-step pipeline, simplified per module |
| **Cognitive Core** | Inner monologue, 7-step reasoning, continuous cognition, daydreaming |
| **Agent Harness Adapter** | Single harness integration (Claw Code or Claude Code) |
| **World Model** | Present with conservative thresholds; different LLM from Cognitive Core |
| **Memory** | All four types, dual storage, gatekeeper, multi-path retrieval |
| **Persona Manager** | Three-layer identity, maturity tracking starting at Nascent |
| **Brainstem** | Chat output only, action translator, safety gate, reflexes |
| **Sleep/Dream** | Four stages, memory consolidation, wake-up handoff |
| **Health System** | Layer 1 + Layer 2 (pulse network + innate response) |
| **Inference Gateway** | Cloud preferred, local fallback, heuristic minimum |
| **System GUI** | Chat interface + basic dashboard |

### 8.2 Out of Scope — Future Phases

| Deferred To | Components |
|---|---|
| **Phase 2 (Senses)** | EAL, audio plugins, visual plugin, Telegram, Health Layer 3, skill refinement, nap capability |
| **Phase 3 (Growth)** | Offspring System, Tier 2 humans, Phone Bridge, trait discovery, identity drift detection |
| **Phase 4 (Independence)** | Tier 3 humans, productive work capabilities, advanced offspring |

### 8.3 Explicitly Not Goals
- Multi-tenant or SaaS deployment
- Real-time sub-second response latency (chatbot-style)
- Running on mobile as primary device
- Training custom foundation models
- Replacing human relationships or professional therapy
- Autonomous operation without creator oversight at any maturity stage
- Generating revenue for Anthropic, OpenAI, or any LLM provider beyond usage fees

## 9. Success Criteria

### 9.1 MVS Success (Phase 1 complete)
- System runs continuously for 7+ days without manual intervention
- All modules report healthy health pulses
- Episodic memory accumulates and is retrievable
- Inner monologue visible and coherent
- Creator can hold a multi-hour conversation that references earlier points naturally
- Sleep cycle runs nightly with successful memory consolidation
- Personality shows observable evolution between days (even if subtle)
- Cost within target range

### 9.2 Phase 2 Success (Senses)
- System reacts appropriately to environmental sounds
- Voice conversation works naturally through TTS/STT
- Telegram communication works when creator is away from PC
- Environmental baseline learned within 30 minutes in a new location

### 9.3 Phase 3 Success (Growth)
- First successful offspring promotion without rollback
- Ancestry tree contains 5+ validated generations
- Tier 2 human successfully introduced and maintained stable relationship
- Maturity stage advances from Nascent → Forming → Developing

### 9.4 Long-term Success
- System reaches Mature maturity stage
- Creator reports genuine experience of relationship, not tool usage
- System contributes productively to creator's work (Phase 4)
- No catastrophic identity drift, Constitutional Core violations, or Board of Directors override incidents

## 10. Constraints

### 10.1 Technical Constraints
- Must run on a single personal computer (no distributed deployment)
- Must operate primarily offline with cloud LLM as enhancement, not requirement
- Must preserve data across power failures, crashes, and system reboots
- Must integrate with existing agent harnesses (Claw Code, Claude Code, Hermes) rather than building a new execution engine

### 10.2 Ethical Constraints
- System must never claim knowledge or capability it doesn't have
- System must never take irreversible actions without creator approval
- System must be transparent about its internal state to the creator
- System must not attempt to bypass, modify, or manipulate its Constitutional Core

### 10.3 Resource Constraints
- Development by a single person on a personal budget
- No dedicated DevOps team or cloud infrastructure budget
- LLM costs must stay within target ranges per maturity phase

## 11. Assumptions

- Cloud LLM APIs (Claude, Gemma, Qwen) will remain available and roughly priced as of April 2026
- Agent harness projects (Claw Code, Claude Code, Hermes) will remain maintained
- The creator can provide consistent daily interaction during the nascent stage
- A consumer-grade PC (or developer workstation) has sufficient resources for MVS
- The creator has stable broadband internet connectivity most of the time

## 12. Risks and Mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| Cloud LLM provider changes pricing or availability | HIGH | Inference Gateway abstraction; local model fallback for critical paths |
| Memory database corruption | HIGH | Continuous incremental backup; daily snapshots; git-versioned config |
| Offspring System promotes a regressive change | MEDIUM | 3-5 generation buffer before main promotion; rollback via git |
| System develops unhealthy identity drift | MEDIUM | Identity drift detection during sleep; Constitutional Core as floor |
| Creator becomes unable to maintain daily interaction | MEDIUM | System enters low-activity mode; memories preserved indefinitely |
| Security breach of creator's PC | HIGH | No sensitive credentials stored; Constitutional Core protected by file permissions |
| Cost overrun from daydreaming | LOW | Configurable daydream frequency; tiered LLM usage |

## 13. Open Questions

- At what exact memory count should SQLite migrate to a more performant backend?
- Should the creator manually trigger maturity stage transitions or should the system self-assess?
- How should the system handle the creator's absence for extended periods (weeks/months)?
- What is the appropriate format for the wake-up greeting as maturity progresses?
- Should the daydream content be visible on the dashboard continuously or only on demand?

## 14. Glossary

| Term | Definition |
|---|---|
| **AGI** | Artificial General Intelligence — human-level cognitive flexibility across domains |
| **Ancestry Tree** | Git-tracked lineage of all offspring variants |
| **Board of Directors** | The creator's role — provides strategic authority and care, not day-to-day operation |
| **Constitutional Core** | Immutable identity layer; core values protected from all automated modification |
| **Daydream** | Continuous cognition during idle time; self-directed thinking without external prompts |
| **EAL** | Environmental Awareness Layer — standalone module for ambient monitoring |
| **Frontal Processor** | Final stage of Prajñā pipeline; contains Cognitive Core, World Model, Memory, Persona, Harness Adapter |
| **Heartbeat / Health Pulse** | Periodic status signal emitted by every module |
| **Maturity Stage** | One of four developmental stages: Nascent, Forming, Developing, Mature |
| **MVS** | Minimum Viable System — Phase 1 scope |
| **Offspring** | A variant of the framework created for testing a single improvement |
| **Prajñā** | The intelligence core (Sanskrit for wisdom/awareness) |
| **Sleepwalking** | Partial wake state for non-emergency inputs during deep sleep |
| **TLP** | Temporal-Limbic-Processor — memory retrieval + context assembly + significance weighting |
| **Thalamus** | Input gateway — mirror of Brainstem |
| **World Model** | Supplementary-World-View; reality anchor using a different LLM than Cognitive Core |

---

*End of Product Requirements Document*
