# app.py (or window_rect.py)
from __future__ import annotations

import asyncio
import time
from typing import Optional, Tuple

from nicegui import app, ui

from kymflow.core.utils.logging import get_logger
from kymflow.gui_v2.app_context import AppContext

Rect = Tuple[int, int, int, int]

logger = get_logger(__name__)

_native_rect_polling_installed = False


def install_native_rect_polling(*, poll_sec: float = 0.5, debounce_sec: float = 1.0) -> None:
    """Install ONE polling loop that monitors the native window rect (x,y,w,h).

    - Safe to call multiple times (installs only once per process).
    - No-op when not running native=True (i.e. app.native is None).
    - Uses ui.timer, so it must be called from inside a page function, not from main() pre-run.
    """
    global _native_rect_polling_installed
    if _native_rect_polling_installed:
        return
    _native_rect_polling_installed = True

    last: dict[str, Optional[Rect]] = {"rect": None}
    last_emit: dict[str, float] = {"t": 0.0}

    async def _read_rect() -> Optional[Rect]:
        native = getattr(app, "native", None)
        if native is None:
            return None
        win = getattr(native, "main_window", None)
        if win is None:
            return None

        size = await win.get_size()
        pos = await win.get_position()
        if not size or not pos:
            return None

        # in pyinstaller froen we are sometimes getting a file path ???
        # check return type of both size and pos
        if isinstance(size, str):
            logger.error(f'20260205 size is a string: {size}')
            return None
        if isinstance(pos, str):
            logger.error(f'20260205 pos is a string: {pos}')
            return None
            
        
        try:
            x, y = int(pos[0]), int(pos[1])
            w, h = int(size[0]), int(size[1])
        except ValueError as e:
            logger.error(f'  20260205 pos is a string: {pos}')
            logger.error(f'  20260205 size is a string: {size}')
            return None

        # logger.info(f'20260205 returning rect: {x}, {y}, {w}, {h}')
        # logger.info(f'  from pos:{pos} size:{size}')

        return (x, y, w, h)

    async def _poll_once() -> None:
        rect = await _read_rect()
        if rect is None:
            return

        if rect == last["rect"]:
            return
        last["rect"] = rect

        now = time.monotonic()
        if now - last_emit["t"] < debounce_sec:
            return
        last_emit["t"] = now

        # Update in-memory app_config window rect; do not save to disk here.
        context = AppContext()
        app_config = getattr(context, "app_config", None)
        if app_config is None:
            return

        try:
            x, y, w, h = rect
            # logger.warning(f'20260205 setting window_rect: {x}, {y}, {w}, {h}')
            app_config.set_window_rect(x, y, w, h)
            # logger.debug(f"[rect] updated in app_config: {rect}")
        except Exception:
            logger.exception("Failed to update app_config window_rect from native window rect")

    def _tick() -> None:
        # native-only: if user runs in browser mode, do nothing
        if getattr(app, "native", None) is None:
            return
        asyncio.create_task(_poll_once())

    ui.timer(poll_sec, _tick)
    logger.info(f"[rect] polling installed (poll_sec={poll_sec}, debounce_sec={debounce_sec})")