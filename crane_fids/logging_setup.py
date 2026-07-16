"""Logging configuration.

The whole project logs through :mod:`logging` and never uses ``print``.  This
module is the single place where handlers are installed, so that the format
stays consistent across the application, the FFmpeg stderr pump and any future
module.
"""

from __future__ import annotations

import logging
import sys
from typing import Final

__all__ = ["configure_logging"]

_FORMAT: Final[str] = "%(asctime)s | %(levelname)-8s | %(name)-28s | %(message)s"
_DATE_FORMAT: Final[str] = "%Y-%m-%dT%H:%M:%S%z"

_configured = False


def configure_logging(level: str = "INFO") -> None:
    """Install a stdout handler for the whole process.

    Idempotent: calling it twice only adjusts the level, which keeps container
    log output free of duplicated lines.

    Args:
        level: Any standard level name, e.g. ``"DEBUG"``.
    """
    global _configured  # noqa: PLW0603 - guarding a process-wide side effect
    numeric = logging.getLevelName(level.upper())
    if not isinstance(numeric, int):  # pragma: no cover - guarded by Config
        numeric = logging.INFO

    root = logging.getLogger()
    if not _configured:
        handler = logging.StreamHandler(stream=sys.stdout)
        handler.setFormatter(logging.Formatter(fmt=_FORMAT, datefmt=_DATE_FORMAT))
        root.handlers.clear()
        root.addHandler(handler)
        _configured = True

    root.setLevel(numeric)
    # Pillow's debug channel is extremely chatty and says nothing useful here.
    logging.getLogger("PIL").setLevel(max(numeric, logging.INFO))
