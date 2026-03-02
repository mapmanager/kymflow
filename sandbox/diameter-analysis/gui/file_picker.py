from __future__ import annotations

import logging
from typing import Sequence

from nicegui import app

logger = logging.getLogger(__name__)


async def _prompt_for_path(
    *,
    dialog_type: str,
    directory: str,
    file_types: Sequence[str] | None = None,
) -> str | None:
    native = getattr(app, "native", None)
    if not native:
        logger.error("file picker unavailable: app.native is not available")
        return None

    main_window = getattr(native, "main_window", None)
    if not main_window:
        logger.error("file picker unavailable: app.native.main_window is not available")
        return None

    if dialog_type != "file":
        raise ValueError(f"Unsupported dialog_type={dialog_type!r}; expected 'file'.")

    import webview

    selection = await main_window.create_file_dialog(  # type: ignore[attr-defined]
        webview.FileDialog.OPEN,
        allow_multiple=False,
        directory=directory,
        file_types=list(file_types or ["TIFF (*.tif;*.tiff)"]),
    )
    if not selection:
        return None

    first = selection[0] if isinstance(selection, (list, tuple)) else selection
    return str(first)


async def prompt_tiff_path(*, initial_dir: str) -> str | None:
    return await _prompt_for_path(
        dialog_type="file",
        directory=initial_dir,
        file_types=["TIFF (*.tif;*.tiff)", "TIFF (*.tif)", "TIFF (*.tiff)"],
    )
