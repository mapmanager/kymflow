from __future__ import annotations

import time
from typing import Optional, Tuple

from nicegui import app, ui

Rect = Tuple[int, int, int, int]

from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)

def install_native_window_persistence(cfg) -> None:
    """Persist native window rect by polling NiceGUI WindowProxy.

    - Works with nicegui.native.native.WindowProxy (no `.events`)
    - No-op when not running native
    - Debounced disk writes
    """
    if not getattr(app, "native", None):
        # logger.warning(f'installing native window persistence... app.native is None')
        return

    win = getattr(app.native, "main_window", None)
    if win is None:
        # logger.warning(f'installing native window persistence... app.native.main_window is None')
        return

    last_rect: dict[str, Optional[Rect]] = {"rect": None}
    last_save_t: dict[str, float] = {"t": 0.0}

    POLL_SEC = 0.25
    SAVE_DEBOUNCE = 0.75

    def _read_rect() -> Optional[Rect]:
        # width/height: most likely available
        w0 = getattr(win, "width", None)
        h0 = getattr(win, "height", None)
        if w0 is None or h0 is None:
            return None

        try:
            w = int(w0)
            h = int(h0)
        except Exception:
            return None

        # x/y: optional (may not exist on WindowProxy)
        x = y = 0
        x0 = getattr(win, "x", None)
        y0 = getattr(win, "y", None)
        if x0 is not None and y0 is not None:
            try:
                x = int(x0)
                y = int(y0)
            except Exception:
                pass

        return (x, y, w, h)

    def _tick() -> None:
        rect = _read_rect()
        if rect is None:
            logger.warning(f'rect is None')
            return
        if last_rect["rect"] == rect:
            logger.warning(f'rect is the same as last_rect')
            return

        last_rect["rect"] = rect

        now = time.monotonic()
        if now - last_save_t["t"] < SAVE_DEBOUNCE:
            return
        last_save_t["t"] = now

        x, y, w, h = rect
        logger.warning(f'saving window rect:{x}, {y}, {w}, {h}')
        cfg.set_window_rect(x, y, w, h)
        cfg.save()

    ui.timer(POLL_SEC, _tick)