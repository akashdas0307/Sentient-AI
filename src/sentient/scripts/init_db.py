"""Initialize the database schema.

Run with: python -m sentient.scripts.init_db
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from sentient.memory.architecture import SQLITE_SCHEMA
import sqlite3
import yaml

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    # Load config to find DB path
    config_path = Path("config/system.yaml")
    if not config_path.exists():
        logger.error("config/system.yaml not found — run from project root")
        return 1

    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    sqlite_path = Path(
        cfg.get("memory", {}).get("storage", {}).get("sqlite_path", "./data/memory.db")
    )
    chroma_path = Path(
        cfg.get("memory", {}).get("storage", {}).get("chroma_path", "./data/chroma")
    )
    logs_dir = Path(cfg.get("logging", {}).get("log_dir", "./data/logs"))

    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    chroma_path.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    # Initialize SQLite schema
    logger.info("Initializing SQLite at %s", sqlite_path)
    conn = sqlite3.connect(str(sqlite_path))
    conn.executescript(SQLITE_SCHEMA)
    conn.close()

    # ChromaDB initializes itself on first use; just ensure dir exists
    logger.info("ChromaDB will initialize at %s on first use", chroma_path)

    logger.info("Database initialization complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
