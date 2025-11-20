"""
Simple, reliable logging utilities for the kymflow project.

- Configure logging once via `setup_logging(...)` at app startup.
- Get module-specific loggers via `get_logger(__name__)`.

This uses the *root logger* so it plays nicely with most frameworks.
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import sys
from pathlib import Path
from typing import Optional, Union

# Internal flag to avoid double-configuration
_CONFIGURED = False


def _expand_path(path: Union[str, Path]) -> Path:
    return Path(os.path.expanduser(str(path))).resolve()


def setup_logging(
    level: Union[str, int] = "INFO",
    log_file: Optional[Union[str, Path]] = None,
    max_bytes: int = 5_000_000,
    backup_count: int = 5,
) -> None:
    """
    Configure root logging with console + optional rotating file handler.

    Calling this multiple times is safe; handlers are only added once.

    Parameters
    ----------
    level:
        Logging level for console (e.g. "DEBUG", "INFO").
    log_file:
        Optional path to a log file. If None, no file handler is added.
    max_bytes:
        Max size in bytes for rotating log file.
    backup_count:
        Number of rotated log files to keep.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    # Convert string levels like "INFO" to logging.INFO
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)

    root = logging.getLogger()
    root.setLevel(level)

    # -------- Formatter --------
    fmt = "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d:%(funcName)s: %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(fmt=fmt, datefmt=datefmt)

    # -------- Console handler --------
    console = logging.StreamHandler(sys.stderr)
    console.setLevel(level)
    console.setFormatter(formatter)
    root.addHandler(console)

    # -------- File handler (optional) --------
    if log_file is not None:
        log_path = _expand_path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.handlers.RotatingFileHandler(
            filename=log_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)  # capture everything to file
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    _CONFIGURED = True


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get a logger by name.

    If name is None, returns a 'kymflow' logger.
    Otherwise, returns logging.getLogger(name).

    Use like:
        logger = get_logger(__name__)
        logger.info("Hello")
    """
    if name is None:
        name = "kymflow"
    return logging.getLogger(name)
