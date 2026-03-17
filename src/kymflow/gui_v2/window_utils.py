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


def set_window_title_for_path(path: Path | str, *, is_file: bool = False) -> None:
    """Set native window title to the full loaded path.

    Only sets title in native mode. Does nothing in web mode.

    Args:
        path: Loaded folder, file, or CSV path (Path object or string).
        is_file: Kept for backward compatibility; not used in title formatting.
    """
    path_obj = Path(path) if isinstance(path, str) else path
    title = f"KymFlow - {path_obj}"
    
    # Only set window title in native mode
    native = getattr(app, "native", None)
    if native is not None:
        main_window = getattr(native, "main_window", None)
        if main_window is not None:
            # logger.debug(f'=== setting window title to is_file:{is_file} title:"{title}"')
            # print(f'  path:{is_file}')

            main_window.set_title(title)
        else:
            logger.error(f'=== main_window is None for title:{title}')


def set_window_title_for_file(file: "KymImage", app_context: "AppContext") -> None:
    """Deprecated: window title now reflects only the loaded path.

    The main window title is set via set_window_title_for_path() when a folder,
    CSV, or single file is loaded. Per-file selection is shown in the footer
    rather than in the native window title.
    """
    return
