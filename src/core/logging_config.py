"""
Centralized logging configuration for the D&D AI DM application.

Sets up:
- Console handler: INFO+ by default (keeps terminal clean)
- Rotating file handler: DEBUG+ (captures everything for review)
- Log path: dnd-ai-dm/logs/dnd_ai_dm.log (5MB, 3 backups)

Usage:
    from core.logging_config import setup_logging
    setup_logging()  # Call once at startup
"""

import logging
import logging.handlers
from pathlib import Path


def setup_logging(log_level: str = "INFO") -> None:
    """
    Configure application-wide logging.

    Args:
        log_level: Console log level (DEBUG, INFO, WARNING, ERROR).
                   File handler always captures DEBUG+.
    """
    # Ensure logs directory exists
    log_dir = Path(__file__).parent.parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "dnd_ai_dm.log"

    # Root logger
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # Prevent duplicate handlers on repeated calls
    if any(isinstance(h, logging.handlers.RotatingFileHandler) for h in root.handlers):
        return

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)-7s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console handler — respects LOG_LEVEL env var
    console = logging.StreamHandler()
    console.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    console.setFormatter(fmt)
    root.addHandler(console)

    # Rotating file handler — always DEBUG
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    # Quiet noisy third-party loggers
    for noisy in ("urllib3", "openai", "httpx", "httpcore", "engineio", "socketio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
