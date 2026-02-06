# src/kymflow/gui_v2/views/folder_picker.py
# gpt 20260106: v2-only folder picker; does not change v1 behavior.

from __future__ import annotations

from pathlib import Path
from typing import Optional

from nicegui import app

from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)


async def _prompt_for_directory_pywebview(initial: Path) -> Optional[str]:
    """Open native folder picker dialog using pywebview (NiceGUI native mode).
    
    Uses NiceGUI's app.native.main_window.create_file_dialog with FOLDER_DIALOG.
    Imports webview inside function to avoid pickling issues with multiprocessing.
    """
    # Check if native mode is available
    native = getattr(app, "native", None)
    if not native:
        logger.warning("app.native is not available - not in native mode?")
        return None
    
    main_window = getattr(native, "main_window", None)
    if not main_window:
        logger.warning("app.native.main_window is not available")
        return None

    try:
        # Import webview inside function to avoid pickling issues
        import webview  # type: ignore
        
        # In pywebview 6.1+, FOLDER_DIALOG is deprecated, use FileDialog.FOLDER instead
        try:
            # Try new API first (pywebview 6.1+)
            folder_dialog_type = webview.FileDialog.FOLDER  # type: ignore
            logger.debug("Using webview.FileDialog.FOLDER for folder dialog")
        except AttributeError:
            # Fallback to deprecated constant (older versions)
            folder_dialog_type = webview.FOLDER_DIALOG  # type: ignore
            logger.debug("Using deprecated webview.FOLDER_DIALOG for folder dialog")
        
        logger.debug("Opening folder dialog with initial directory: %s", initial)
        selection = await main_window.create_file_dialog(  # type: ignore[attr-defined]
            folder_dialog_type,
            directory=str(initial),
            allow_multiple=False,
        )
        
        if not selection:
            logger.debug("User cancelled folder dialog or no selection returned")
            return None
        
        # Log the type of selection for debugging
        selection_type = type(selection).__name__
        logger.debug(f"1 Folder dialog returned selection_type:{selection_type} selection: {selection}")
        logger.debug(f'  selection is: {selection}')
        logger.debug(f'  selection type is: {type(selection)}')

        # Handle return value - can be string, list, or tuple (pywebview returns tuple on macOS)
        if isinstance(selection, (list, tuple)):
            result = str(selection[0]) if selection else None
            # logger.debug("  2 Folder dialog returned %s: %s -> %s", selection_type, selection, result)
            logger.debug(f'    result is: {result}')
            return result
            
        result = str(selection)
        logger.debug("Folder dialog returned string: %s", result)
        return result
    except Exception as exc:
        logger.warning("pywebview folder dialog failed: %s", exc, exc_info=True)
        return None


async def _prompt_for_file_pywebview(initial: Path) -> Optional[str]:
    """Open native file picker dialog using pywebview (NiceGUI native mode).
    
    Uses NiceGUI's app.native.main_window.create_file_dialog with FileDialog.OPEN.
    Imports webview inside function to avoid pickling issues with multiprocessing.
    Filters for .tif files only.
    """
    # Check if native mode is available
    native = getattr(app, "native", None)
    if not native:
        logger.warning("app.native is not available - not in native mode?")
        return None
    
    main_window = getattr(native, "main_window", None)
    if not main_window:
        logger.warning("app.native.main_window is not available")
        return None

    try:
        # Import webview inside function to avoid pickling issues
        import webview  # type: ignore
        
        # Use FileDialog.OPEN for file selection
        file_dialog_type = webview.FileDialog.OPEN  # type: ignore
        logger.debug("Using webview.FileDialog.OPEN for file dialog")
        
        logger.debug("Opening file dialog with initial directory: %s", initial)
        selection = await main_window.create_file_dialog(  # type: ignore[attr-defined]
            file_dialog_type,
            directory=str(initial),
            allow_multiple=False,
            file_types=("TIF files (*.tif)",),
        )
        
        if not selection:
            logger.debug("User cancelled file dialog or no selection returned")
            return None
        
        # Log the type of selection for debugging
        selection_type = type(selection).__name__
        logger.debug("1 File dialog returned type: %s, value: %s", selection_type, selection)
            
        # Handle return value - can be string, list, or tuple (pywebview returns tuple on macOS)
        if isinstance(selection, (list, tuple)):
            result = str(selection[0]) if selection else None
            logger.debug("2 File dialog returned %s: %s -> %s", selection_type, selection, result)
            return result
            
        result = str(selection)
        logger.debug("3File dialog returned string: %s", result)
        return result
    except Exception as exc:
        logger.warning("pywebview file dialog failed: %s", exc, exc_info=True)
        return None