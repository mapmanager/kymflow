from __future__ import annotations

from enum import Enum


class SelectionOrigin(str, Enum):
    """Identify which UI element initiated a selection change."""

    TABLE = "table"
    IMAGE = "image"
    PLOT = "plot"
    NAV = "nav"
    OTHER = "other"


class ThemeMode(str, Enum):
    """UI theme used for coordinating between components."""

    DARK = "dark"
    LIGHT = "light"
