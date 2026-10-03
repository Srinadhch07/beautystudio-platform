"""Logging setup.

Only non-sensitive values are ever logged. Credentials, the MongoDB
connection string and object-storage keys must never reach a log record.
"""

from __future__ import annotations

import logging

LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_configured = False


def configure_logging(level: str = "INFO") -> None:
    """Configure root logging once per process."""
    global _configured
    if _configured:
        logging.getLogger().setLevel(level)
        return

    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format=LOG_FORMAT,
        datefmt=DATE_FORMAT,
    )
    logging.getLogger().setLevel(getattr(logging, level, logging.INFO))
    _configured = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
