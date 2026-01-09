"""About page for GUI v2 displaying version information and logs."""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

from nicegui import ui

from kymflow.core.utils.about import getVersionInfo
from kymflow.core.utils.logging import get_log_file_path
from kymflow.gui.app_context import AppContext
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.pages.base_page import BasePage

if TYPE_CHECKING:
    pass


class AboutPage(BasePage):
    """About page displaying version information and application logs.

    This is a simple read-only page that displays:
    - Version information (KymFlow versions, Python, NiceGUI, etc.)
    - Application logs (last 300 lines in an expandable section)

    This page does not require EventBus subscriptions or controllers since
    it's purely informational and doesn't interact with application state.

    Attributes:
        None (pure view, no state to track)
    """

    def __init__(self, context: AppContext, bus: EventBus) -> None:
        """Initialize About page.

        Args:
            context: Shared application context (used for consistency with other pages).
            bus: Per-client EventBus instance (not used for this page, but required by BasePage).
        """
        super().__init__(context, bus)
        # No additional initialization needed - this is a simple view

    def build(self) -> None:
        """Build the About page UI.

        Creates the version information display and log viewer.
        This method is called fresh on each render (e.g., when navigating
        to the About page).
        """
        # Welcome heading
        ui.label("Welcome to KymFlow").classes("text-2xl font-bold")

        # Fetch version info (called fresh on each render)
        version_info = getVersionInfo()

        # Version information card
        with ui.card().classes("w-full p-4 gap-2"):
            ui.label("Version info").classes("text-lg font-semibold")
            for key, value in version_info.items():
                with ui.row().classes("items-center gap-2"):
                    ui.label(f"{key}:").classes("text-sm text-gray-500")
                    ui.label(str(value)).classes("text-sm")

        # Log file viewer (expandable section)
        log_path = get_log_file_path()

        # Read last 300 lines of log file
        max_lines = 300
        log_content = ""
        if log_path and log_path.exists():
            try:
                with log_path.open("r", encoding="utf-8", errors="replace") as f:
                    tail_lines = deque(f, maxlen=max_lines)
                log_content = "".join(tail_lines)
                if len(tail_lines) == max_lines:
                    log_content = (
                        f"...(truncated, last {max_lines} lines)...\n{log_content}"
                    )
            except Exception as e:
                log_content = f"Unable to read log file: {e}"
        else:
            log_content = "[empty]"

        # Log viewer in expandable section (collapsed by default)
        with ui.expansion("Logs", value=False).classes("w-full"):
            ui.label(f"Log file: {log_path or 'N/A'}").classes("text-sm text-gray-500")
            ui.code(log_content).classes("w-full text-sm").style(
                "white-space: pre-wrap; font-family: monospace; max-height: 400px; overflow: auto;"
            )

