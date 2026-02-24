from __future__ import annotations

from pathlib import Path

from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)


def get_hidden_cache_dir(visible_path: Path) -> Path:
    """Return the hidden cache directory for a visible DB path."""
    return visible_path.parent / ".kymflow_hidden"


def get_hidden_cache_path(visible_path: Path) -> Path:
    """Return the hidden CSV path (same filename under .kymflow_hidden)."""
    return get_hidden_cache_dir(visible_path) / visible_path.name


def ensure_hidden_cache_dir(visible_path: Path) -> Path:
    """Ensure hidden cache directory exists; log when it is first created.

    Returns:
        The hidden cache directory path.
    """
    hidden_dir = get_hidden_cache_dir(visible_path)
    if not hidden_dir.exists():
        hidden_dir.mkdir(parents=True, exist_ok=True)
        logger.warning("Created hidden cache directory: %s", hidden_dir)
    return hidden_dir

