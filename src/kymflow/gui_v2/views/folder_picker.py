# src/kymflow/gui_v2/views/folder_picker.py
# gpt 20260106: v2-only folder picker; does not change v1 behavior.

from __future__ import annotations

from pathlib import Path
from typing import Optional

from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)


def _prompt_for_directory_pywebview(initial: Path) -> Optional[str]:
    """Try pywebview folder dialog (works best in NiceGUI native=True)."""
    try:
        import webview  # type: ignore
    except Exception:
        return None

    try:
        if not getattr(webview, "windows", None) or len(webview.windows) == 0:
            return None
        win = webview.windows[0]
        selection = win.create_file_dialog(  # type: ignore[attr-defined]
            webview.FOLDER_DIALOG,  # type: ignore[attr-defined]
            directory=str(initial),
            allow_multiple=False,
        )
        if not selection:
            return None
        if isinstance(selection, list):
            return str(selection[0]) if selection else None
        return str(selection)
    except Exception as exc:
        logger.warning("pywebview folder dialog failed: %s", exc)
        return None


def _prompt_for_directory_tk(initial: Path) -> Optional[str]:
    """Fallback tkinter folder dialog."""
    try:
        import tkinter as tk  # type: ignore
        from tkinter import filedialog
    except Exception:
        return None

    root = None
    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        selection = filedialog.askdirectory(initialdir=str(initial))
    except Exception:
        return None
    finally:
        if root is not None:
            try:
                root.destroy()
            except Exception:
                pass
    return selection or None


def prompt_for_directory(initial: Path) -> Optional[str]:
    """Pick a folder path.

    Order:
        1) pywebview dialog if available (native mode)
        2) tkinter fallback (browser/server mode)
    """
    selection = _prompt_for_directory_pywebview(initial)
    if selection:
        return selection
    return _prompt_for_directory_tk(initial)