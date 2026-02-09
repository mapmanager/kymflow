"""Window utility functions for native mode operations.

This module provides utilities for interacting with the native window,
such as setting window titles based on file or folder paths.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from nicegui import app

from kymflow.core.utils.logging import get_logger

if TYPE_CHECKING:
    from kymflow.core.image_loaders.kym_image import KymImage
    from kymflow.gui_v2.app_context import AppContext

logger = get_logger(__name__)


def set_window_title_from_context(app_context: "AppContext") -> None:
    """Set native window title based on AppContext.
    
    Uses selected file (with blinded support) if available, otherwise uses selected path.
    Only sets title in native mode. Does nothing in web mode.
    
    Args:
        app_context: AppContext to get selected file, path, and blinded setting.
    """
    # Only set window title in native mode
    native = getattr(app, "native", None)
    if native is None:
        return
    
    main_window = getattr(native, "main_window", None)
    if main_window is None:
        logger.error('=== main_window is None, cannot set window title')
        return
    
    # Get selected file and path from app state
    selected_file = app_context.app_state.selected_file if app_context.app_state else None
    selected_path = app_context.app_state.folder if app_context.app_state else None
    
    # Build title based on rules
    if selected_path is not None:
        path_obj = Path(selected_path) if not isinstance(selected_path, Path) else selected_path
        
        if path_obj.is_file():
            # If selected_path is a file, use that
            title = f'KymFlow - {path_obj.name}'
        else:
            # Otherwise, use selected_path and selected_file
            if selected_file is not None:
                # Get blinded file name if available
                blinded = app_context.app_config.get_blinded() if app_context.app_config else False
                file_name = selected_file.get_file_name(blinded=blinded) or "unknown"
                title = f'KymFlow - {selected_path} - {file_name}'
            else:
                # Just use the path
                title = f'KymFlow - {selected_path}'
    else:
        # No path selected, use default title
        blinded = app_context.app_config.get_blinded() if app_context.app_config else False
        title = f'KymFlow - {blinded}'
    
    logger.debug(f'=== setting window title to "{title}"')
    main_window.set_title(title)

def set_window_title_for_path(path: Path | str, *, is_file: bool = False) -> None:
    """Set native window title based on file or folder path.
    
    Only sets title in native mode. Does nothing in web mode.
    
    Args:
        path: File or folder path (Path object or string).
        is_file: True if path is a file, False if folder. Defaults to False.
    
    Examples:
        set_window_title_for_path(Path("/data/folder"), is_file=False)
        # Sets title to "KymFlow - folder/"
        
        set_window_title_for_path("/data/file.tif", is_file=True)
        # Sets title to "KymFlow - file.tif"
    """
    # Convert to Path if string
    path_obj = Path(path) if isinstance(path, str) else path
    
    # Build title based on file or folder
    if is_file:
        title = f'KymFlow - {path_obj.name}'
    else:
        title = f'KymFlow - {path_obj.name}/'
    
    # Only set window title in native mode
    native = getattr(app, "native", None)
    if native is not None:
        main_window = getattr(native, "main_window", None)
        if main_window is not None:
            logger.debug(f'=== setting window title to "{title}"')
            main_window.set_title(title)
        else:
            logger.error(f'=== main_window is None for title:{title}')


def set_window_title_for_file(file: "KymImage", app_context: "AppContext") -> None:
    """Set native window title based on KymImage with blinded support.
    
    Only sets title in native mode. Does nothing in web mode.
    
    Args:
        file: KymImage instance.
        app_context: AppContext to get blinded setting.
    """
    if file is None:
        return
    
    blinded = app_context.app_config.get_blinded() if app_context.app_config else False
    file_name = file.get_file_name(blinded=blinded) or "unknown"
    
    title = f'KymFlow - {file_name}'
    
    # Only set window title in native mode
    native = getattr(app, "native", None)
    if native is not None:
        main_window = getattr(native, "main_window", None)
        if main_window is not None:
            logger.debug(f'=== setting window title to "{title}"')
            main_window.set_title(title)
        else:
            pass
            # perfectly fine in native=False mode
            # logger.error(f'=== main_window is None for title:{title}')
