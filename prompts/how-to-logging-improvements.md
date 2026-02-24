# Logging How-To: Improvements and Final Draft

This document suggests improvements to [how-to-add-logging.md](how-to-add-logging.md), weighs pros/cons, and provides a complete implementation.

---

## Suggested Improvements

### 1. Add optional file handler support to `configure_logging`

**Current how-to:** Only mentions console-style configuration (level, fmt, datefmt).

**Suggestion:** Add optional `log_file`, `max_bytes`, and `backup_count` parameters.

| Pros | Cons |
|------|------|
| Demos and CLI tools often need log files for debugging | More API surface |
| Matches real-world needs (nicewidgets, kymflow use file logging) | Slightly more complex implementation |
| Single function covers both console-only and file use cases | — |

**Recommendation:** Add it. Use `RotatingFileHandler` so logs don't grow unbounded.

---

### 2. Add `get_log_file_path()` when file logging is enabled

**Current how-to:** Does not mention retrieving the log file path.

**Suggestion:** When `log_file` is set, store the resolved path and expose it via `get_log_file_path()`.

| Pros | Cons |
|------|------|
| Enables "View Log" / "Open Log" in GUIs | One more function to maintain |
| Useful for error messages ("See log at X") | — |
| Low implementation cost | — |

**Recommendation:** Add it.

---

### 3. Clarify package logger vs root logger (and when to use each)

**Current how-to:** Says "Configure your package logger rather than the root logger" to avoid breaking host apps.

**Suggestion:** Explicitly document:
- **Package logger:** For libraries. Host app controls root; library only configures its own logger.
- **Root logger:** Only for standalone apps/demos that need all logs (library + nicegui + etc.). Not for library import paths.

**Edge case:** Demo scripts that use both nicewidgets and nicegui. If we only configure the package logger, nicegui logs won't appear unless the demo also configures root. The how-to should say: "Demo scripts that are apps may configure root if they want all library logs; library code must never configure root."

**Recommendation:** Add a short "Package vs root" subsection and clarify demo behavior.

---

### 4. Avoid duplicate handlers with `force` parameter

**Current how-to:** Mentions `force=True` to attach handler even if one exists.

**Suggestion:** By default (`force=False`), only add a handler if the package logger has none. With `force=True`, clear existing handlers first (or add anyway and document that duplicate lines may occur).

| Pros | Cons |
|------|------|
| Prevents duplicate log lines when `configure_logging` is called repeatedly | `force=True` behavior needs clear docs |
| Handles hot-reload / repeated setup in demos | — |

**Recommendation:** Implement: if logger already has handlers and `force=False`, skip. If `force=True`, remove existing handlers then add.

---

### 5. Environment variable override for level

**Current how-to:** Suggests `ACQSTORE_LOG_LEVEL=DEBUG` (or package-specific name).

**Suggestion:** In `configure_logging`, if `level` is None (or a sentinel), read from `os.environ.get("PACKAGE_LOG_LEVEL", "INFO")` where PACKAGE is your package name.

| Pros | Cons |
|------|------|
| Override without code changes | Another env var to document |
| Useful for debugging in deployed apps | Might be surprising if undocumented |
| Optional—only used when not explicitly passed | — |

**Recommendation:** Add as optional. Use explicit `level` when passed; otherwise fall back to env var.

---

### 6. Set `propagate=False` when adding a handler

**Current how-to:** Does not specify propagation.

**Suggestion:** When we add a handler to the package logger, set `logger.propagate = False` so logs don't also go to the root logger (avoiding duplicates when both have handlers).

| Pros | Cons |
|------|------|
| Avoids duplicate lines | If host configures root and expects library logs via propagation, they won't see them |
| Clear ownership: our handler = our output | — |

**Note:** When we configure the package logger, we're in "standalone script" mode. The host isn't configuring root in that scenario. So `propagate=False` is safe. When the library is imported by a host that configures root, we don't call `configure_logging`, so we never add our handler—propagation stays True and logs go to root.

**Recommendation:** Set `propagate=False` when we add our own handler.

---

### 7. Provide `get_logger(name)` helper

**Current how-to:** Shows `logging.getLogger(__name__)` directly in modules.

**Suggestion:** Provide `get_logger(name=None)` that returns `logging.getLogger(name or "package")`. This centralizes the package name and allows `get_logger(__name__)` for consistency.

| Pros | Cons |
|------|------|
| Consistent pattern across modules | Redundant with `logging.getLogger` |
| Single place to change package logger name | — |
| Some projects prefer explicit helper | — |

**Recommendation:** Keep it. Matches existing nicewidgets/kymflow style.

---

### 8. Add NullHandler at package init

**Current how-to:** Recommends it. Prevents "No handler could be found" warning.

**Recommendation:** Keep as-is. Essential for library hygiene.

---

## Final Draft: Complete Source Code

Below is a drop-in implementation suitable for a package like `nicewidgets` or `kymflow_zarr`. Replace `PACKAGE_NAME` with your package name (e.g. `"nicewidgets"`, `"kymflow_zarr"`).

### Package `__init__.py`

```python
"""
Your package description.
"""

import logging

# Prevent "No handler could be found" when library is imported without logging config
logging.getLogger(__name__).addHandler(logging.NullHandler())

from your_package.utils.logging import get_logger, get_log_file_path, configure_logging

__all__ = [
    "configure_logging",
    "get_log_file_path",
    "get_logger",
]

__version__ = "0.1.0"
```

### `your_package/utils/logging.py`

```python
"""
Logging utilities for the PACKAGE_NAME library.

Library code should use get_logger(__name__) and never call configure_logging().
Applications, CLI tools, and demo scripts may call configure_logging() to enable
log output. Importing the library never changes the host application's logging.
"""

from __future__ import annotations

import logging
import logging.handlers
import os
from pathlib import Path
from typing import Optional, Union

# Replace with your package name, e.g. "nicewidgets", "kymflow_zarr"
PACKAGE_LOGGER_NAME = "PACKAGE_NAME"
ENV_LOG_LEVEL = "PACKAGE_LOG_LEVEL"  # e.g. "NICEWIDGETS_LOG_LEVEL"

_LOG_FILE_PATH: Optional[Path] = None

_DEFAULT_FMT = "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d:%(funcName)s: %(message)s"
_DEFAULT_DATEFMT = "%Y-%m-%d %H:%M:%S"


def _resolve_level(level: Optional[Union[str, int]]) -> int:
    """Resolve level from str, int, or env var."""
    if level is not None:
        if isinstance(level, str):
            return getattr(logging, level.upper(), logging.INFO)
        return int(level)
    env = os.environ.get(ENV_LOG_LEVEL, "INFO")
    return getattr(logging, env.upper(), logging.INFO)


def _expand_path(path: Union[str, Path]) -> Path:
    return Path(os.path.expanduser(str(path))).resolve()


def configure_logging(
    level: Union[str, int, None] = None,
    *,
    fmt: Optional[str] = None,
    datefmt: Optional[str] = None,
    log_file: Optional[Union[str, Path]] = None,
    max_bytes: int = 5_000_000,
    backup_count: int = 5,
    force: bool = False,
) -> None:
    """
    Configure logging for this package. For use by applications, demos, and CLI tools.

    Configures the package logger only (not root). Importing the library never
    changes the host application's logging.

    Parameters
    ----------
    level
        Log level (e.g. "DEBUG", "INFO"). If None, uses env var PACKAGE_LOG_LEVEL.
    fmt
        Log format string. Default includes time, level, name, lineno, message.
    datefmt
        Date format for timestamps.
    log_file
        Optional path for rotating log file.
    max_bytes
        Max size per log file in bytes (for RotatingFileHandler).
    backup_count
        Number of rotated backup files to keep.
    force
        If True, remove existing handlers before adding. Prevents duplicates
        when called multiple times (e.g. hot reload).
    """
    global _LOG_FILE_PATH

    level_int = _resolve_level(level)
    fmt_str = fmt or _DEFAULT_FMT
    datefmt_str = datefmt or _DEFAULT_DATEFMT

    logger = logging.getLogger(PACKAGE_LOGGER_NAME)
    logger.setLevel(level_int)

    if force and logger.handlers:
        for h in list(logger.handlers):
            logger.removeHandler(h)

    # Skip if already configured (unless force)
    if logger.handlers and not force:
        return

    formatter = logging.Formatter(fmt=fmt_str, datefmt=datefmt_str)

    # Console handler
    console = logging.StreamHandler()
    console.setLevel(level_int)
    console.setFormatter(formatter)
    logger.addHandler(console)

    # File handler (optional)
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
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    else:
        _LOG_FILE_PATH = None

    logger.propagate = False


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get a logger. Use get_logger(__name__) in library modules.
    """
    if name is None:
        name = PACKAGE_LOGGER_NAME
    return logging.getLogger(name)


def get_log_file_path() -> Optional[Path]:
    """
    Return the path to the log file if file logging was configured via configure_logging().
    """
    return _LOG_FILE_PATH
```

### Usage in library modules

```python
from your_package.utils.logging import get_logger

logger = get_logger(__name__)

def my_function():
    logger.debug("Detail")
    logger.info("Done")
```

### Usage in demo/CLI script

```python
from your_package.utils.logging import configure_logging, get_logger

configure_logging("DEBUG", log_file="~/myapp.log")
logger = get_logger(__name__)

# ... rest of script
```

### Usage with env override

```bash
export PACKAGE_LOG_LEVEL=DEBUG
python my_script.py
```

```python
from your_package.utils.logging import configure_logging

configure_logging()  # Uses PACKAGE_LOG_LEVEL from env
```

---

## Summary of Changes vs Original How-To

| Item | Original | Improved |
|------|----------|----------|
| configure_logging API | level, fmt, datefmt, force | + log_file, max_bytes, backup_count |
| Root vs package | Package only | Same (package only) |
| get_log_file_path | Not mentioned | Added |
| Env override | Mentioned | Implemented (level=None reads env) |
| Duplicate handlers | force mentioned | force=False skips if handlers exist; force=True removes first |
| propagate | Not specified | Set False when we add handler |
| get_logger | Not specified | Provided with package default |

---

## Migration from existing setup_logging (root-based)

If migrating from a root-based `setup_logging`:

1. Add NullHandler in package `__init__.py`.
2. Replace `setup_logging` with `configure_logging` (package-logger-based).
3. Update all demo/CLI callers to use `configure_logging`.
4. **Note:** Demos will only see package logs. If they need all logs (e.g. nicegui), they must configure root themselves (outside the library).
