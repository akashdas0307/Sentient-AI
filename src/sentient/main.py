"""Main entry point — wires all modules together and starts the system.

Per ARCHITECTURE.md §6.3, modules are initialized in dependency order:
  1. Event Bus
  2. Inference Gateway
  3. Memory Architecture
  4. Persona Manager
  5. Health Pulse Network + Innate Response
  6. Thalamus
  7. Prajñā pipeline (Checkpost → Queue Zone → TLP → Frontal)
  8. Brainstem
  9. Sleep Scheduler
  10. API Server

Starts the system by calling `python -m sentient.main`.
"""
from __future__ import annotations

import asyncio
import logging
import os
import signal
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from sentient.brainstem.gateway import Brainstem
from sentient.brainstem.plugins.chat_output import ChatOutputPlugin
from sentient.core.event_bus import get_event_bus
from sentient.core.inference_gateway import InferenceGateway
from sentient.core.lifecycle import LifecycleManager
from sentient.health.innate_response import InnateResponse
from sentient.health.pulse_network import HealthPulseNetwork
from sentient.memory.architecture import MemoryArchitecture
from sentient.persona.identity_manager import PersonaManager
from sentient.prajna.checkpost import Checkpost
from sentient.prajna.frontal.cognitive_core import CognitiveCore
from sentient.prajna.frontal.harness_adapter import HarnessAdapter
from sentient.prajna.frontal.world_model import WorldModel
from sentient.prajna.frontal.decision_arbiter import DecisionArbiter
from sentient.prajna.queue_zone import QueueZone
from sentient.prajna.temporal_limbic import TemporalLimbicProcessor
from sentient.sleep.scheduler import SleepScheduler
from sentient.sleep.consolidation import ConsolidationEngine
from sentient.sleep.contradiction_resolver import ContradictionResolver
from sentient.sleep.wm_calibrator import WMCalibrator
from sentient.thalamus.gateway import Thalamus
from sentient.thalamus.plugins.chat_input import ChatInputPlugin

# Load .env
load_dotenv()

# Configure logging
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def load_config() -> tuple[dict, dict]:
    """Load system.yaml and inference_gateway.yaml configurations."""
    config_dir = Path(os.environ.get("SENTIENT_CONFIG_DIR", "./config"))
    with open(config_dir / "system.yaml") as f:
        system_cfg = yaml.safe_load(f)
    with open(config_dir / "inference_gateway.yaml") as f:
        inference_cfg = yaml.safe_load(f)
    return system_cfg, inference_cfg


async def build_and_start() -> tuple[LifecycleManager, Any]:
    """Construct all modules, register them, and start the system."""
    logger.info("Sentient Framework MVS starting up...")
    system_cfg, inference_cfg = load_config()

    # Ensure data directories exist
    data_dir = Path(system_cfg.get("system", {}).get("data_dir", "./data"))
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "logs").mkdir(exist_ok=True)

    event_bus = get_event_bus()
    lifecycle = LifecycleManager(event_bus)

    # === 1. Inference Gateway (must be first) ===
    inference_gateway = InferenceGateway(inference_cfg)
    lifecycle.register(inference_gateway, essential=True)

    # === 2. Memory Architecture ===
    # Blend memory config with embedding config
    memory_cfg = dict(system_cfg.get("memory", {}))
    memory_cfg["embeddings"] = memory_cfg.get("embeddings") or {"model": "all-MiniLM-L6-v2"}
    memory = MemoryArchitecture(memory_cfg, event_bus)
    lifecycle.register(memory, essential=True)

    # === Consolidation Engine ===
    consolidation_engine = ConsolidationEngine(
        memory_architecture=memory,
        inference_gateway=inference_gateway,
        event_bus=event_bus,
        config=system_cfg.get("memory", {}),
    )

    # === 3. Persona Manager ===
    persona = PersonaManager(system_cfg.get("persona", {}), event_bus)
    lifecycle.register(persona, essential=True)

    # === 4. Health monitoring ===
    health_network = HealthPulseNetwork(
        system_cfg.get("health", {}), lifecycle, event_bus,
    )
    innate = InnateResponse(
        system_cfg.get("health", {}), lifecycle, event_bus,
    )
    lifecycle.register(health_network, essential=True)
    lifecycle.register(innate, essential=True)

    # === 5. Thalamus ===
    thalamus = Thalamus(system_cfg.get("thalamus", {}), event_bus)
    lifecycle.register(thalamus)

    # === 6. Prajñā pipeline ===
    checkpost = Checkpost(
        system_cfg.get("checkpost", {}), inference_gateway, memory, event_bus,
    )
    queue_zone = QueueZone(system_cfg.get("queue_zone", {}), event_bus)
    tlp = TemporalLimbicProcessor(
        system_cfg.get("tlp", {}), inference_gateway, memory, event_bus,
    )
    cognitive_core = CognitiveCore(
        system_cfg.get("cognitive_core", {}),
        inference_gateway,
        persona=persona,
        memory=memory,
        event_bus=event_bus,
    )
    world_model = WorldModel(
        system_cfg.get("world_model", {}),
        inference_gateway,
        persona=persona,
        event_bus=event_bus,
    )
    harness_adapter = HarnessAdapter(
        system_cfg.get("harness", {"harness": "claude_code", "command": ["claude"]}),
        event_bus,
    )

    lifecycle.register(checkpost)
    lifecycle.register(queue_zone)
    lifecycle.register(tlp)
    lifecycle.register(cognitive_core)
    lifecycle.register(world_model)
    lifecycle.register(harness_adapter)

    # === 7. Brainstem + Decision Arbiter ===
    # Decision Arbiter sits between World Model and Brainstem to own routing authority
    decision_arbiter = DecisionArbiter(
        system_cfg.get("decision_arbiter", {}),
        event_bus=event_bus,
    )
    lifecycle.register(decision_arbiter)

    brainstem = Brainstem(system_cfg.get("brainstem", {}), event_bus)
    lifecycle.register(brainstem)

    # === 8. Sleep Scheduler ===
    # Instantiate contradiction resolver
    contradiction_resolver = ContradictionResolver(
        memory_architecture=memory,
        inference_gateway=inference_gateway,
        event_bus=event_bus,
        config=system_cfg.get("sleep", {}).get("contradiction_resolution", {}),
    )
    # Instantiate WM calibrator
    wm_calibrator = WMCalibrator(
        world_model=world_model,
        memory_architecture=memory,
        event_bus=event_bus,
        config=system_cfg.get("sleep", {}).get("wm_calibration", {}),
    )

    sleep = SleepScheduler(
        system_cfg.get("sleep", {}),
        lifecycle,
        memory=memory,
        consolidation_engine=consolidation_engine,
        contradiction_resolver=contradiction_resolver,
        wm_calibrator=wm_calibrator,
        event_bus=event_bus,
    )
    lifecycle.register(sleep, essential=True)

    # === 9. Start all modules ===
    await lifecycle.startup()

    # === 10. Register input/output plugins with Thalamus/Brainstem ===
    chat_input = ChatInputPlugin()
    chat_output = ChatOutputPlugin()
    await thalamus.register_plugin(chat_input)
    await brainstem.register_plugin(chat_output)

    # === 11. Start API server ===
    from sentient.api.server import APIServer
    api_server = APIServer(
        system_cfg.get("api", {}),
        lifecycle,
        chat_input_plugin=chat_input,
        chat_output_plugin=chat_output,
        health_pulse_network=health_network,
        event_bus=event_bus,
    )
    await api_server.start()

    logger.info("=" * 60)
    logger.info("Sentient Framework MVS — SYSTEM READY")
    logger.info("Open http://%s:%d to interact.",
                api_server.host, api_server.port)
    logger.info("=" * 60)

    return lifecycle, api_server


async def run_forever() -> None:
    """Main async entry point."""
    lifecycle, api_server = await build_and_start()
    loop = asyncio.get_event_loop()

    # Setup signal handlers for graceful shutdown
    shutdown_event = asyncio.Event()

    def _signal_handler():
        logger.info("Shutdown signal received")
        shutdown_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            # Windows doesn't support signal handlers the same way
            pass

    # Wait until shutdown is requested
    await shutdown_event.wait()

    logger.info("Shutting down...")
    await api_server.shutdown()
    await lifecycle.shutdown()
    logger.info("Shutdown complete.")


def run() -> None:
    """Synchronous entry point (console_script target)."""
    try:
        asyncio.run(run_forever())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    run()
