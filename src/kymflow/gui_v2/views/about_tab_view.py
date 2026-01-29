"""About tab view component.

This module provides a view component that displays:
- Version information (KymFlow versions, Python, NiceGUI, etc.)
- Application logs (last N lines)

This is used inside the left drawer tabs (not the standalone About page).
"""

from __future__ import annotations

from collections import deque

from nicegui import ui

from kymflow.core.utils.about import getVersionInfo
from kymflow.core.utils.logging import get_log_file_path, get_logger

logger = get_logger(__name__)


class AboutTabView:
    """About tab view component (version info + logs)."""

    def __init__(self, *, max_log_lines: int = 300) -> None:
        self._max_log_lines = max_log_lines

    def render(self) -> None:
        """Create the About tab UI inside the current container."""
        # Version information card
        version_info = getVersionInfo_gui()
        # with ui.card().classes("w-full p-4 gap-2"):
        if 1:
            ui.label("Version info").classes("text-lg font-semibold")
            for key, value in version_info.items():
                with ui.row().classes("items-center gap-2"):
                    ui.label(f"{key}:").classes("text-sm text-gray-500")
                    ui.label(str(value)).classes("text-sm")

        # Log file viewer
        log_path = get_log_file_path()
        log_content = ""
        if log_path and log_path.exists():
            try:
                with log_path.open("r", encoding="utf-8", errors="replace") as f:
                    tail_lines = deque(f, maxlen=self._max_log_lines)
                log_content = "".join(tail_lines)
                if len(tail_lines) == self._max_log_lines:
                    log_content = (
                        f"...(truncated, last {self._max_log_lines} lines)...\n{log_content}"
                    )
            except Exception as e:
                log_content = f"Unable to read log file: {e}"
        else:
            log_content = "[empty]"

        # Logs section - in disclosure triangle
        with ui.expansion("Logs", value=False).classes("w-full"):
            ui.label(f"Log file: {log_path or 'N/A'}").classes("text-sm text-gray-500")
            ui.code(log_content).classes("w-full text-sm").style(
                "white-space: pre-wrap; font-family: monospace; max-height: 400px; overflow: auto;"
            )


def getVersionInfo_gui() -> dict:
    """Get version info with GUI-specific details included."""
    version_info = getVersionInfo()

    import nicegui
    import kymflow.gui_v2 as kymflow_gui

    version_info["KymFlow GUI version"] = kymflow_gui.__version__  # noqa: SLF001
    version_info["NiceGUI version"] = nicegui.__version__

    return version_info

