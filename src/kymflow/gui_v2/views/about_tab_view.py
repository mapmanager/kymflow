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
from kymflow.gui_v2.styles import kym_expansion

logger = get_logger(__name__)


class AboutTabView:
    """About tab view component (version info + logs)."""

    def __init__(self, *, max_log_lines: int = 300) -> None:
        self._max_log_lines = max_log_lines

    def _open_config_in_window(self, config_path: str) -> None:
        """reveal user config kymflow path in finder."""
        from nicewidgets.utils.file_manager import reveal_in_file_manager
        reveal_in_file_manager(config_path)

    def _copy_version_info(self, version_info: dict ) -> None:
        """copy version info to clipboard."""
        from nicewidgets.utils.clipboard import copy_to_clipboard
        version_info_str = "\n".join([f"{key}: {value}" for key, value in version_info.items()])
        copy_to_clipboard(version_info_str)

    def render(self) -> None:
        """Create the About tab UI inside the current container."""
        
        # Version information card
        version_info = getVersionInfo_gui()

        with ui.row().classes("items-center gap-2"):
            ui.label("Version info").classes("text-lg font-semibold")
            ui.button('Copy', on_click=lambda: self._copy_version_info(version_info)).classes("text-blue-500")
        if 1:
            for key, value in version_info.items():
                with ui.row().classes("items-center gap-2"):
                    ui.label(f"{key}:").classes("text-gray-500")
                    ui.label(str(value))

                    if key == 'User Config':
                        _config = value
                        ui.button('Open', on_click=lambda: self._open_config_in_window(_config)).classes("text-blue-500")


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
        # with ui.expansion("Logs", value=False).classes("w-full"):
        with kym_expansion("Logs", value=False).classes("w-full"):
            # ui.label(f"Log file: {log_path or 'N/A'}").classes("text-sm text-gray-500")
            ui.code(log_content).classes("w-full text-sm").style(
                "white-space: pre-wrap; font-family: monospace; max-height: 400px; overflow: auto;"
            )


def getVersionInfo_gui() -> dict:
    """Get version info with GUI-specific details included."""
    
    # get pure python info
    version_info = getVersionInfo()

    import nicegui
    import kymflow.gui_v2 as kymflow_gui

    version_info["KymFlow GUI version"] = kymflow_gui.__version__  # noqa: SLF001
    version_info["NiceGUI version"] = nicegui.__version__

    # get build info
    from kymflow.build_info import get_build_info
    build_info = get_build_info()
    # version_info["Build info"] = build_info
    for key, value in build_info.items():
        version_info[key] = value
        
    return version_info

