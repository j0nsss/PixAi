"""Logging utility with rotating file handler and console output."""

from __future__ import annotations
import logging
import logging.handlers
from pathlib import Path

from config import LOG_DIR, LOG_FILE


def setup_logging(debug: bool = False) -> None:
    """Configure logging with rotating file handler and console output.

    Args:
        debug: If True, set log level to DEBUG, else INFO.
    """
    root_logger = logging.getLogger()
    if root_logger.handlers:
        # Already configured - idempotent
        return

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    level = logging.DEBUG if debug else logging.INFO
    root_logger.setLevel(level)

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s [%(threadName)s] %(name)s: %(message)s"
    )

    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)
    root_logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)
    root_logger.addHandler(console_handler)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name.

    Args:
        name: Logger name (typically __name__).

    Returns:
        A logging.Logger instance.
    """
    return logging.getLogger(name)