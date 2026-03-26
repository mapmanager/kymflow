"""Runtime mode helpers for gui_v2."""

from __future__ import annotations

import os


def is_native_mode() -> bool:
    """Return True when gui_v2 should run in desktop native mode."""
    raw = os.getenv("KYMFLOW_GUI_NATIVE", "").strip().lower()
    return raw not in {"0", "false", "no", "off"}

