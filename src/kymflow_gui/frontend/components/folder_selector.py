from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from nicegui import ui

from kymflow_core.utils.logging import get_logger

logger = get_logger(__name__)


def prompt_for_directory(initial: Path) -> Optional[str]:
    """Prompt user to select a directory using a file dialog.
    
    Args:
        initial: Initial directory to show in the dialog
        
    Returns:
        Selected directory path as string, or None if cancelled/error
    """
    try:
        import tkinter as tk  # type: ignore
        from tkinter import filedialog
    except Exception as exc:  # pragma: no cover - platform specifics
        logger.warning("Folder dialog unavailable: %s", exc)
        ui.notify("Folder picker unavailable", color="negative")
        return None

    root = None
    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        selection = filedialog.askdirectory(initialdir=str(initial))
    except Exception as exc:  # pragma: no cover - user environment
        logger.warning("Folder dialog failed: %s", exc)
        ui.notify("Could not open folder picker", color="negative")
        return None
    finally:
        if root is not None:
            root.destroy()
    return selection or None


def create_folder_selector(
    current_folder: dict[str, Path],
    folder_display: ui.label,
    on_folder_changed: Callable[[Path], None],
) -> None:
    """Create folder selection UI with Choose and Reload buttons.
    
    Args:
        current_folder: Dictionary with 'path' key to track current folder
        folder_display: Label widget to display current folder path
        on_folder_changed: Callback function called when folder changes, receives Path
    """
    def _load_folder(path_str: str) -> None:
        folder = Path(path_str).expanduser()
        if not folder.exists():
            ui.notify(f"Folder not found: {folder}", color="negative")
            return
        logger.info("Loading folder %s", folder)
        current_folder["path"] = folder
        folder_display.set_text(f"Folder: {folder}")
        on_folder_changed(folder)

    def _choose_folder() -> None:
        initial = current_folder["path"]
        selection = prompt_for_directory(initial)
        if selection:
            _load_folder(selection)

    folder_row = ui.row().classes("w-full items-end gap-2")
    with folder_row:
        ui.button("Choose folder", on_click=_choose_folder)
        ui.button(
            "Reload",
            on_click=lambda: _load_folder(str(current_folder["path"]))
        )
        folder_display

