#!/usr/bin/env python3
"""
Self-contained NiceGUI folder picker demo.

This demonstrates the working native folder picker solution that:
- Uses pywebview's FileDialog.FOLDER API (pywebview 6.1+)
- Falls back to deprecated FOLDER_DIALOG for older versions
- Works in NiceGUI native mode (requires KYMFLOW_GUI_NATIVE=1)
- Imports webview inside async function to avoid pickling issues
- Uses await for the async create_file_dialog method

Run with native mode:
    KYMFLOW_GUI_NATIVE=1 python sandbox/file_picker_cursor.py

Or in browser mode (folder picker won't work, but app will load):
    python sandbox/file_picker_cursor.py
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from nicegui import app, ui


async def prompt_for_folder_pywebview(initial: Path) -> Optional[str]:
    """
    Open native folder picker dialog using pywebview (NiceGUI native mode).
    
    Key points learned:
    1. Import webview INSIDE the function to avoid multiprocessing pickling issues
    2. Use FileDialog.FOLDER (pywebview 6.1+) instead of deprecated FOLDER_DIALOG
    3. Must use await on create_file_dialog (it's async)
    4. Access via app.native.main_window (NiceGUI's native window)
    """
    print(f"[prompt_for_folder_pywebview] Starting with initial={initial}")
    
    # Check if native mode is available via NiceGUI's app.native
    native = getattr(app, "native", None)
    if not native:
        print("[prompt_for_folder_pywebview] ERROR: app.native is not available - not in native mode?")
        print("[prompt_for_folder_pywebview]   Set KYMFLOW_GUI_NATIVE=1 to enable native mode")
        return None
    
    main_window = getattr(native, "main_window", None)
    if not main_window:
        print("[prompt_for_folder_pywebview] ERROR: app.native.main_window is not available")
        return None
    
    print("[prompt_for_folder_pywebview] Native window found, proceeding with dialog...")
    
    try:
        # CRITICAL: Import webview INSIDE function to avoid pickling issues
        # when NiceGUI spawns worker processes
        import webview  # type: ignore
        print("[prompt_for_folder_pywebview] webview module imported successfully")
        
        # Use new API (pywebview 6.1+): FileDialog.FOLDER
        # Falls back to deprecated FOLDER_DIALOG for older versions
        try:
            folder_dialog_type = webview.FileDialog.FOLDER  # type: ignore
            print("[prompt_for_folder_pywebview] Using webview.FileDialog.FOLDER (new API)")
        except AttributeError:
            # Fallback to deprecated constant (older pywebview versions)
            folder_dialog_type = webview.FOLDER_DIALOG  # type: ignore
            print("[prompt_for_folder_pywebview] Using deprecated webview.FOLDER_DIALOG (fallback)")
        
        print(f"[prompt_for_folder_pywebview] Opening dialog with type={folder_dialog_type}, initial={initial}")
        
        # CRITICAL: Must use await - create_file_dialog is async!
        selection = await main_window.create_file_dialog(  # type: ignore[attr-defined]
            folder_dialog_type,
            directory=str(initial),
            allow_multiple=False,
        )
        
        print(f"[prompt_for_folder_pywebview] Dialog returned: {selection} (type: {type(selection).__name__})")
        
        if not selection:
            print("[prompt_for_folder_pywebview] User cancelled or no selection")
            return None
        
        # Handle return value - can be string or list
        if isinstance(selection, list):
            result = str(selection[0]) if selection else None
            print(f"[prompt_for_folder_pywebview] Selection was list, extracted: {result}")
            return result
        
        result = str(selection)
        print(f"[prompt_for_folder_pywebview] Selection was string: {result}")
        return result
        
    except Exception as exc:
        print(f"[prompt_for_folder_pywebview] EXCEPTION: {type(exc).__name__}: {exc}")
        import traceback
        traceback.print_exc()
        return None


@ui.page("/")
def main_page() -> None:
    """Main UI page with folder picker button."""
    print("[main_page] Rendering UI...")
    
    # Get initial directory (home directory)
    initial_dir = Path.home().expanduser().resolve()
    current_folder = initial_dir
    
    ui.label("NiceGUI Native Folder Picker Demo").classes("text-h5 mb-4")
    
    # Display current folder
    folder_display = ui.label(f"Current folder: {current_folder}").classes("text-body1 mb-2")
    
    # Status label for messages
    status_label = ui.label("Ready to select folder").classes("text-body2 mb-4")
    
    async def on_choose_folder() -> None:
        """Handle folder selection button click."""
        nonlocal current_folder
        print(f"[on_choose_folder] Button clicked, current_folder={current_folder}")
        
        # Check if we're in native mode (for user feedback)
        native = getattr(app, "native", None)
        main_window = getattr(native, "main_window", None) if native else None
        
        if not main_window:
            msg = "Native mode not available. Set KYMFLOW_GUI_NATIVE=1 to enable folder picker."
            print(f"[on_choose_folder] WARNING: {msg}")
            status_label.text = msg
            status_label.classes("text-orange-600")
            ui.notify(msg, type="warning")
            return
        
        print("[on_choose_folder] Native mode detected, opening folder dialog...")
        status_label.text = "Opening folder dialog..."
        status_label.classes("text-blue-600")
        
        # Open folder picker
        selected = await prompt_for_folder_pywebview(current_folder)
        
        if selected:
            current_folder = Path(selected)
            folder_display.text = f"Current folder: {current_folder}"
            status_label.text = f"Selected: {current_folder}"
            status_label.classes("text-green-600")
            ui.notify(f"Folder selected: {current_folder}", type="positive")
            print(f"[on_choose_folder] SUCCESS: Selected folder: {current_folder}")
        else:
            status_label.text = "Folder selection cancelled"
            status_label.classes("text-grey-600")
            ui.notify("Folder selection cancelled", type="info")
            print("[on_choose_folder] User cancelled folder selection")
    
    # Button to open folder picker
    ui.button("Choose Folder", on_click=on_choose_folder).classes("mb-4")
    
    # Display native mode status
    native_available = getattr(app, "native", None) is not None
    mode_status = "Native mode" if native_available else "Browser mode (folder picker disabled)"
    ui.label(f"Mode: {mode_status}").classes("text-caption text-grey-600 mt-4")
    
    print(f"[main_page] UI rendered, native_mode={native_available}")


if __name__ in {"__main__", "__mp_main__"}:
    print("=" * 60)
    print("NiceGUI Folder Picker Demo")
    print("=" * 60)
    
    # Check if native mode is enabled via environment variable
    native_env = os.environ.get("KYMFLOW_GUI_NATIVE", "0")
    native_enabled = native_env.lower() in ("1", "true", "yes")
    
    print(f"[main] KYMFLOW_GUI_NATIVE={native_env} -> native_enabled={native_enabled}")
    
    if native_enabled:
        print("[main] Starting NiceGUI in native mode...")
        ui.run(native=True, window_size=(600, 400), title="Folder Picker Demo")
    else:
        print("[main] Starting NiceGUI in browser mode...")
        print("[main] NOTE: Folder picker requires native mode (set KYMFLOW_GUI_NATIVE=1)")
        ui.run(port=8080, title="Folder Picker Demo")
