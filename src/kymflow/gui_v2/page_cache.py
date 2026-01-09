"""Page instance caching for stable navigation across route changes.

This module provides a simple page cache that persists page instances across
navigation, preventing unnecessary recreation and stale callback accumulation.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from nicegui import app

if TYPE_CHECKING:
    from kymflow.gui_v2.pages.base_page import BasePage

logger = None  # Lazy import to avoid circular dependencies


def _get_logger():
    """Lazy import logger."""
    global logger
    if logger is None:
        from kymflow.core.utils.logging import get_logger
        logger = get_logger(__name__)
    return logger


def get_stable_session_id() -> str:
    """Get or create a stable session ID that persists across page navigations.

    Uses app.storage.user to persist a session ID per browser session.
    This ID remains stable even when NiceGUI creates new client IDs on
    page navigation.

    Returns:
        Stable session ID string.
    """
    session_key = "_kymflow_v2_session_id"
    session_id = app.storage.user.get(session_key)
    if session_id is None:
        session_id = str(uuid.uuid4())
        app.storage.user[session_key] = session_id
        _get_logger().debug(f"Created new stable session ID: {session_id}")
    return str(session_id)


# Module-level page cache: (session_id, route) -> page instance
_PAGE_CACHE: dict[tuple[str, str], BasePage] = {}


def get_cached_page(session_id: str, route: str) -> BasePage | None:
    """Get a cached page instance for a session and route.

    Args:
        session_id: Stable session identifier.
        route: Route path (e.g., "/", "/about").

    Returns:
        Cached page instance, or None if not cached.
    """
    key = (session_id, route)
    return _PAGE_CACHE.get(key)


def cache_page(session_id: str, route: str, page: BasePage) -> None:
    """Cache a page instance for a session and route.

    Args:
        session_id: Stable session identifier.
        route: Route path (e.g., "/", "/about").
        page: Page instance to cache.
    """
    key = (session_id, route)
    _PAGE_CACHE[key] = page
    _get_logger().debug(f"Cached page for session {session_id[:8]}... route {route}")


def clear_session_pages(session_id: str) -> None:
    """Clear all cached pages for a session.

    Args:
        session_id: Stable session identifier.
    """
    keys_to_remove = [key for key in _PAGE_CACHE.keys() if key[0] == session_id]
    for key in keys_to_remove:
        del _PAGE_CACHE[key]
    if keys_to_remove:
        _get_logger().debug(f"Cleared {len(keys_to_remove)} cached pages for session {session_id[:8]}...")

