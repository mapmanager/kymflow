"""Helper for emitting footer status messages through the EventBus.

Usage:
    from kymflow.gui_v2.footer_status import set_footer_status

    set_footer_status(bus, "Settings saved")
    set_footer_status(bus, "No file selected", level="warning")
"""

from __future__ import annotations

from typing import Literal

from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.events_state import FooterStatusMessage


FooterLevel = Literal["info", "warning", "error", "success"]


def set_footer_status(bus: EventBus, text: str, level: FooterLevel = "info") -> None:
    """Emit a footer status message on the GUI event bus.

    This is the preferred way for controllers/views in gui_v2 to update the
    footer status text directly, instead of reaching into FooterView.
    """
    bus.emit(FooterStatusMessage(text=text, level=level))

