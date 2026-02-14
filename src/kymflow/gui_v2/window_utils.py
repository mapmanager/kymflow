"""Window utility functions for native mode operations.

This module provides utilities for interacting with the native window,
such as setting window titles based on file or folder paths.
"""

from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from nicegui import app

from kymflow.core.utils.logging import get_logger

if TYPE_CHECKING:
    from kymflow.core.image_loaders.kym_image import KymImage
    from kymflow.gui_v2.app_context import AppContext

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
            logger.debug(f'=== setting window title to is_file:{is_file} title:"{title}"')
            print(f'  path:{is_file}')

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
    
    _parents = file._compute_parents_from_path(file.path)
    # _parents is a tuple(parent1, parent2, parent3)
    # reverse _parents
    _parents = _parents[::-1]
    # make a string with '/'
    _parents_str = '/'.join([p for p in _parents if p is not None])
    if blinded:
        _parents_str = 'Blinded'

    # logger.info(f'_parents:{_parents}')

    file_name = file.get_file_name(blinded=blinded) or "unknown"
    
    title = f'KymFlow - {_parents_str} - {file_name}'
    
    # Only set window title in native mode
    native = getattr(app, "native", None)
    if native is not None:
        main_window = getattr(native, "main_window", None)
        if main_window is not None:
            # logger.debug(f'=== setting window title to "{title}"')
            main_window.set_title(title)
        else:
            pass
            # perfectly fine in native=False mode
            # logger.error(f'=== main_window is None for title:{title}')

def reveal_in_file_manager(path: str | os.PathLike) -> None:
    """Reveal a path in the OS file manager (Finder/Explorer/etc).

    - macOS: Finder reveals + selects the item
    - Windows: Explorer reveals + selects the item
    - Linux: opens the containing folder (selection support varies)
    """
    p = Path(path).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(str(p))

    system = platform.system()

    if system == "Darwin":
        # Finder reveal (select)
        subprocess.run(["open", "-R", str(p)], check=False)

    elif system == "Windows":
        # Explorer reveal (select)
        subprocess.run(["explorer", f'/select,"{p}"'], check=False, shell=True)

    else:
        # Linux: open folder (best-effort)
        folder = p if p.is_dir() else p.parent
        subprocess.run(["xdg-open", str(folder)], check=False)