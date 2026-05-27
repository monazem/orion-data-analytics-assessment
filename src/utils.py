"""Shared utilities: configuration loading and logging setup.

Centralizing these in one module means every other module looks the same
(logger = get_logger(__name__)) and config changes happen in one place.
"""
from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


# ---------------------------------------------------------------------------
# Configuration loading
# ---------------------------------------------------------------------------

def load_config(config_path: str | Path = "config/pipeline.yaml") -> dict[str, Any]:
    """Load YAML pipeline config from disk.

    We pass the result around as a plain dict instead of a typed object —
    simpler for a small pipeline. At larger scale, swap this for a Pydantic
    model so config errors fail loudly at startup.
    """
    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(
            f"Config file not found: {config_path.resolve()}. "
            "Run from project root, not from inside src/."
        )
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

_logger_initialized = False


def setup_logging(log_dir: str | Path = "logs", level: str = "INFO") -> None:
    """Configure root logger to write to both stdout and a timestamped file.

    Idempotent: safe to call multiple times.
    """
    global _logger_initialized
    if _logger_initialized:
        return

    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    fmt = "%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s"
    handlers = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file, mode="w"),
    ]
    logging.basicConfig(level=level, format=fmt, handlers=handlers)
    _logger_initialized = True

    logging.getLogger(__name__).info(f"Logging initialized -> {log_file}")


def get_logger(name: str) -> logging.Logger:
    """Return a named logger. Setup must be called first (pipeline.py does this)."""
    return logging.getLogger(name)