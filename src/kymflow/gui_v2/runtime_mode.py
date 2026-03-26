"""Runtime mode helpers for gui_v2 (native desktop vs web/browser)."""

from __future__ import annotations

import os


def is_native_mode() -> bool:
    """Return True when gui_v2 should behave as native desktop mode.

    Uses the same convention as ``app.py`` / ``main()``:
    - Unset env -> native (True)
    - ``0`` / ``false`` / ``no`` / ``off`` -> web/browser (False)

    Returns:
        True for native desktop, False for web deployment.
    """
    raw = os.getenv("KYMFLOW_GUI_NATIVE", "").strip().lower()
    return raw not in {"0", "false", "no", "off"}
