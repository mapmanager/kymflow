"""Window utility functions for native mode operations.

This module provides utilities for interacting with the native window,
such as setting window titles based on file or folder paths.
"""

from __future__ import annotations

from pathlib import Path

from nicegui import app

from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)


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
