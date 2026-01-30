from __future__ import annotations

from nicegui import app, ui

from kymflow.gui_v2.app_context import AppContext

from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)

async def _capture_native_window_rect(context: AppContext, *, log: bool = False) -> None:
    """Best-effort capture of native window rect on shutdown."""
    
    log = True
    
    native = getattr(app, "native", None)
    if native is None:
        return
    win = getattr(native, "main_window", None)
    if win is None:
        return

    try:
        size = await win.get_size()
    except Exception:
        size = None
    try:
        pos = await win.get_position()
    except Exception:
        pos = None

    if not size:
        return

    try:
        w, h = int(size[0]), int(size[1])
    except Exception:
        return

    if pos:
        try:
            x, y = int(pos[0]), int(pos[1])
        except Exception:
            x, y = 0, 0
    else:
        x, y = 0, 0

    if log:
        logger.info(f"setting window rect to {x}, {y}, {w}, {h}")
    context.user_config.set_window_rect(x, y, w, h)


def install_shutdown_handlers(context: AppContext, *, native: bool) -> None:
    """Register app shutdown handlers for GUI v2."""
    logger.info("install_shutdown_handlers(native=%s)", native)

    async def _persist_on_shutdown() -> None:
        await _capture_native_window_rect(context, log=True)
        context.user_config.save()

    app.on_shutdown(_persist_on_shutdown)

    # NOTE: No runtime timer here. We only capture at shutdown to avoid
    # introducing startup-time timer errors.
