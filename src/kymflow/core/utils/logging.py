"""
Simple, reliable logging utilities for the kymflow application.

- Configure logging via `setup_logging(...)` at app startup.
- Get module-specific loggers via `get_logger(__name__)`.
- Reconfigure anytime by calling `setup_logging(...)` again.

This uses the *root logger* so it plays nicely with most frameworks.
Log file is written under the same per-user app directory as user_config/app_config
(platformdirs, app name "kymflow"), in a "logs" subfolder: e.g. kymflow.log.
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional, Union

from platformdirs import user_config_dir

# App name used for config/log paths; must match user_config.py and app_config.py.
_APP_NAME = "kymflow"
_LOG_FILENAME = "kymflow.log"

# Store the log file path for retrieval
_LOG_FILE_PATH: Optional[Path] = None


def setup_logging(
    level: Union[str, int] = "DEBUG",
    max_bytes: int = 5_000_000,
    backup_count: int = 5,
) -> None:
    """
    Configure root logging with console and rotating file handler.

    Console and file both receive the same formatter. Console uses the given
    level; file captures everything at DEBUG. Log file is always written to the
    platformdirs-based kymflow config directory (same location as user_config
    and app_config JSON files), in a "logs" subfolder.

    Calling this multiple times will reconfigure logging (removes old handlers first).

    Parameters
    ----------
    level:
        Logging level for console (e.g. "DEBUG", "INFO").
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
    for handler in root.handlers[:]:
        handler.close()
        root.removeHandler(handler)

    root.setLevel(level)

    # -------- Formatters --------
    # Console: keep existing format, no timestamp
    console_fmt = "[%(levelname)s] %(name)s:%(funcName)s:%(lineno)d: %(message)s"
    # File: prepend timestamp using the same date format
    file_fmt = "%(asctime)s [%(levelname)s] %(name)s:%(funcName)s:%(lineno)d: %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    console_formatter = logging.Formatter(fmt=console_fmt)
    file_formatter = logging.Formatter(fmt=file_fmt, datefmt=datefmt)

    # -------- Console handler (unchanged) --------
    console = logging.StreamHandler(sys.stderr)
    console.setLevel(level)
    console.setFormatter(console_formatter)
    root.addHandler(console)

    # -------- File handler (platformdirs-based path, same folder as user_config) --------
    global _LOG_FILE_PATH
    log_dir = Path(user_config_dir(_APP_NAME)) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / _LOG_FILENAME
    _LOG_FILE_PATH = log_path

    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)  # capture everything to file
    file_handler.setFormatter(file_formatter)
    root.addHandler(file_handler)


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
    Get the path to the log file (always set after setup_logging).

    Returns
    -------
    Path to the log file.

    Examples
    --------
    ```python
    log_path = get_log_file_path()
    if log_path:
        print(f"Logging to: {log_path}")
    ```
    """
    return _LOG_FILE_PATH
