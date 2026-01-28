"""Utilities for checking client validity and handling client lifecycle."""

from __future__ import annotations

from typing import Callable

from nicegui import ui


def is_client_alive() -> bool:
    """Check if the current NiceGUI client context is still alive.

    Returns:
        True if client is alive and accessible, False otherwise.
    """
    try:
        # Try to access client context - if it raises RuntimeError, client is dead
        _ = ui.context.client.id
        return True
    except (AttributeError, RuntimeError):
        return False


def safe_call(func: Callable, *args, **kwargs) -> None:
    """Safely call a function, catching "client deleted" errors.

    Useful for UI update functions that might be called after a client
    has been deleted (e.g., from stale AppState callbacks).

    Args:
        func: Function to call.
        *args: Positional arguments to pass to function.
        **kwargs: Keyword arguments to pass to function.
    """
    try:
        func(*args, **kwargs)
    except RuntimeError as e:
        # Silently ignore "client deleted" errors
        if "deleted" in str(e).lower():
            return
        raise

