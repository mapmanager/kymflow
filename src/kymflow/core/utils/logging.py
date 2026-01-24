"""
Simple, reliable logging utilities for the kymflow application.

- Configure logging via `setup_logging(...)` at app startup.
- Get module-specific loggers via `get_logger(__name__)`.
- Reconfigure anytime by calling `setup_logging(...)` again.

This uses the *root logger* so it plays nicely with most frameworks.
Logs automatically go to ~/.kymflow/logs/kymflow.log by default.
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import sys
from pathlib import Path
from typing import Optional, Union

# Store the log file path for retrieval
_LOG_FILE_PATH: Optional[Path] = None


def _expand_path(path: Union[str, Path]) -> Path:
    return Path(os.path.expanduser(str(path))).resolve()


def setup_logging(
    level: Union[str, int] = "INFO",
    log_file: Optional[Union[str, Path]] = "~/.kymflow/logs/kymflow.log",
    max_bytes: int = 5_000_000,
    backup_count: int = 5,
) -> None:
    """
    Configure root logging with console + optional rotating file handler.

    Calling this multiple times will reconfigure logging (removes old handlers first).

    Parameters
    ----------
    level:
        Logging level for console (e.g. "DEBUG", "INFO").
    log_file:
        Path to a log file. Defaults to "~/.kymflow/logs/kymflow.log".
        Set to None to disable file logging (console only).
    max_bytes:
        Max size in bytes for rotating log file.
    backup_count:
        Number of rotated log files to keep.
    """
    # Convert string levels like "INFO" to logging.INFO
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)

    root = logging.getLogger()
    
    # Remove existing handlers to allow reconfiguration
    # This prevents duplicate handlers while allowing logging to be reconfigured
    for handler in root.handlers[:]:
        handler.close()
        root.removeHandler(handler)
    
    root.setLevel(level)

    # -------- Formatter --------
    # fmt = "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d:%(funcName)s: %(message)s"    # Shorter format: removed line number and function name to reduce log line length
    fmt = "[%(levelname)s] %(name)s:%(funcName)s:%(lineno)d: %(message)s"    # Shorter format: removed line number and function name to reduce log line length
    datefmt = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(fmt=fmt, datefmt=datefmt)

    # -------- Console handler --------
    console = logging.StreamHandler(sys.stderr)
    console.setLevel(level)
    console.setFormatter(formatter)
    root.addHandler(console)

    # -------- File handler (optional) --------
    global _LOG_FILE_PATH
    if log_file is not None:
        log_path = _expand_path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        _LOG_FILE_PATH = log_path

        file_handler = logging.handlers.RotatingFileHandler(
            filename=log_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)  # capture everything to file
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    else:
        # Clear log file path when file logging is disabled
        _LOG_FILE_PATH = None


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


def get_log_file_path() -> Optional[Path]:
    """
    Get the path to the log file, if file logging is configured.

    Returns
    -------
    Path to the log file, or None if file logging is not configured.

    Examples
    --------
    ```python
    log_path = get_log_file_path()
    if log_path:
        print(f"Logging to: {log_path}")
    ```
    """
    return _LOG_FILE_PATH
