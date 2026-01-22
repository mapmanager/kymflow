"""GUI event origin tracking.

This module defines enums used to track the origin/source of GUI events,
allowing components to coordinate and avoid feedback loops when handling
state changes triggered by user interactions.
"""

from __future__ import annotations

from enum import Enum


class SelectionOrigin(str, Enum):
    """Origin of a file selection change event.

    Used to identify which UI element initiated a selection change, allowing
    components to avoid feedback loops when updating selections.

    Values:
        TABLE: Selection originated from the file table.
        IMAGE: Selection originated from the image viewer.
        PLOT: Selection originated from a plot component.
        NAV: Selection originated from navigation controls.
        OTHER: Selection originated from an unknown or programmatic source.
    """

    TABLE = "table"
    IMAGE = "image"
    PLOT = "plot"
    NAV = "nav"
    OTHER = "other"


class ImageDisplayOrigin(str, Enum):
    """Origin of an image display parameter change event.

    Used to identify which UI element initiated a display parameter change
    (colorscale, intensity range), allowing components to avoid feedback loops.

    Values:
        CONTRAST_WIDGET: Change originated from the contrast control widget.
        PROGRAMMATIC: Change originated from programmatic code.
        OTHER: Change originated from an unknown source.
    """

    CONTRAST_WIDGET = "contrast_widget"
    PROGRAMMATIC = "programmatic"
    OTHER = "other"

