"""About page content builder."""

from __future__ import annotations

from collections import deque

from nicegui import ui

from kymflow.gui.core.app_context import AppContext
from kymflow.core.utils.logging import get_log_file_path
from kymflow.gui import _getVersionInfo


def build_about_content(context: AppContext) -> None:
    """Build the About page content.
    
    Shows version/build information and application logs.
    
    Args:
        context: Application context (not heavily used on this page)
    """
    ui.label("Welcome to KymFlow").classes("text-2xl font-bold")
    
    # Fetch version info lazily when rendering
    version_info = _getVersionInfo()
    
    # Version information card
    with ui.card().classes("w-full p-4 gap-2"):
        ui.label("Version info").classes("text-lg font-semibold")
        for key, value in version_info.items():
            with ui.row().classes("items-center gap-2"):
                ui.label(f"{key}:").classes("text-sm text-gray-500")
                ui.label(str(value)).classes("text-sm")
    
    # Log file viewer
    log_path = get_log_file_path()
    
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
    
    with ui.expansion("Logs", value=False).classes("w-full"):
        ui.label(f"Log file: {log_path or 'N/A'}").classes("text-sm text-gray-500")
        ui.code(log_content or "[empty]").classes("w-full text-sm").style(
            "white-space: pre-wrap; font-family: monospace; max-height: 400px; overflow: auto;"
        )
