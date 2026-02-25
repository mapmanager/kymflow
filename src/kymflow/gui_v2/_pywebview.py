"""Common utils for using nicegui native pywinview
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Literal, Optional, Tuple

from nicegui import app, ui

from kymflow.gui_v2.app_context import AppContext
from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)

Rect = Tuple[int, int, int, int]

_native_rect_polling_installed = False  # used by install_native_rect_polling

def install_native_rect_polling(*, poll_sec: float = 0.5, debounce_sec: float = 1.0) -> None:
    """Install ONE polling loop that monitors the native window rect (x,y,w,h).

    - Safe to call multiple times (installs only once per process).
    - No-op when not running native=True (app.native is None).
    - Must be called from inside a page function (uses ui.timer).
    - Cooperates with NativeUiGate: skips polling while folder dialogs are open.
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
            logger.error('native is None')
            return None
        win = getattr(native, "main_window", None)
        if win is None:
            # logger.error('main_window is None')
            return None

        size = await win.get_size()
        pos = await win.get_position()

        # Expect (w,h) and (x,y)
        if not isinstance(size, (list, tuple)) or len(size) < 2:
            logger.debug(f"[rect] get_size unexpected: {size!r}")
            return None
        if not isinstance(pos, (list, tuple)) or len(pos) < 2:
            logger.debug(f"[rect] get_position unexpected: {pos!r}")
            return None

        try:
            x, y = int(pos[0]), int(pos[1])
            w, h = int(size[0]), int(size[1])
        except Exception:
            logger.debug(f"[rect] failed to coerce pos/size to int: pos={pos!r} size={size!r}")
            return None

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

        ctx = AppContext()
        app_config = getattr(ctx, "app_config", None)
        if app_config is None:
            return

        try:
            x, y, w, h = rect
            logger.debug(f"[rect] updating app_config.window_rect -> {(x, y, w, h)}")
            app_config.set_window_rect(x, y, w, h)  # in-memory only; your shutdown handler saves
        except Exception:
            logger.exception("[rect] failed updating app_config.window_rect")

    def _tick() -> None:
        if getattr(app, "native", None) is None:
            return

        ctx = AppContext()
        gate = getattr(ctx, "native_ui_gate", None)
        if gate is not None and gate.is_busy():
            busy, reason, seconds = gate.status()
            # logger.debug(f"[rect] skip tick (gate busy reason={reason} for {seconds:0.2f}s)")
            return

        asyncio.create_task(_poll_once())

    ui.timer(poll_sec, _tick)
    logger.info(f"[rect] polling installed (poll_sec={poll_sec}, debounce_sec={debounce_sec})")

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

def _save_all_configs(context: AppContext) -> bool:
    """Save both user_config and app_config to disk.
    
    Single source of truth for persisting all application configs.
    Used by both shutdown handler and manual save button.
    
    Args:
        context: AppContext instance containing user_config and app_config.
    
    Returns:
        True if both configs saved successfully, False otherwise.
    """
    success = True
    
    cfg = getattr(context, "user_config", None)
    if cfg is not None:
        try:
            cfg.save()
            logger.info("user_config saved successfully")
        except Exception:
            logger.exception("Failed to save user_config")
            success = False

    app_cfg = getattr(context, "app_config", None)
    if app_cfg is not None:
        try:
            app_cfg.save()
            logger.info("app_config saved successfully")
        except Exception:
            logger.exception("Failed to save app_config")
            success = False
    
    return success


def install_shutdown_handlers(context: AppContext) -> None:
    """Register app shutdown handlers for GUI v2.
    
    Only installs handlers when running in native mode (native=True).
    In browser mode, configs are saved via other mechanisms.
    """
    native = getattr(app, "native", None)
    if native is None:
        logger.debug("install_shutdown_handlers: skipping (not native mode)")
        return
    
    logger.info("install_shutdown_handlers: installing (native mode detected)")

    async def _persist_on_shutdown() -> None:
        """Persist user and app config on shutdown without touching native window APIs."""
        _save_all_configs(context)

    app.on_shutdown(_persist_on_shutdown)

    # NOTE: No runtime timer here. We only capture at shutdown to avoid
    # introducing startup-time timer errors.

async def _prompt_for_path(
    initial: Path,
    *,
    dialog_type: Literal["folder", "file"] = "folder",
    file_extension: Optional[str] = None,
) -> Optional[str]:
    """Open native folder or file picker dialog using pywebview (NiceGUI native mode).

    Fix: cooperatively blocks rect polling (and any other gated native ops)
    while the dialog is active, preventing callback collisions.

    Args:
        initial: Initial directory for the dialog.
        dialog_type: Type of dialog to open - "folder" or "file". Defaults to "folder".
        file_extension: File extension to filter for when dialog_type="file"
            (e.g., ".tif", ".csv"). Defaults to ".tif" if not provided for file dialogs.

    Returns:
        Selected path as string, or None if cancelled or error.
    """
    native = getattr(app, "native", None)
    if not native:
        logger.warning("[picker] app.native not available (not native mode?)")
        return None

    main_window = getattr(native, "main_window", None)
    if not main_window:
        logger.warning("[picker] app.native.main_window not available")
        return None

    ctx = AppContext()
    gate = getattr(ctx, "native_ui_gate", None)
    if gate is None:
        logger.warning("[picker] no native_ui_gate on AppContext; continuing without gating")

    # Initialize log_prefix for error handling
    log_prefix = "dialog"  # fallback if exception occurs before setting

    try:
        # Import webview inside function to avoid spawn/pickling issues
        import webview  # type: ignore

        # Determine dialog type and parameters
        if dialog_type == "folder":
            # pywebview 6.1+: FileDialog.FOLDER; older: FOLDER_DIALOG
            try:
                dialog_type_enum = webview.FileDialog.FOLDER  # type: ignore[attr-defined]
                logger.debug("[picker] using webview.FileDialog.FOLDER")
            except Exception:
                dialog_type_enum = webview.FOLDER_DIALOG  # type: ignore[attr-defined]
                logger.debug("[picker] using deprecated webview.FOLDER_DIALOG")
            
            dialog_params = {
                "directory": str(initial),
                "allow_multiple": False,
            }
            gate_reason = "folder_dialog"
            log_prefix = "folder"
        else:  # dialog_type == "file"
            dialog_type_enum = webview.FileDialog.OPEN  # type: ignore[attr-defined]
            
            # Normalize file extension
            if file_extension is None:
                ext = ".tif"
            else:
                ext = file_extension.strip()
                if not ext.startswith("."):
                    ext = f".{ext}"
            
            # For display name, use extension without dot, uppercase
            ext_display = ext[1:].upper()
            
            dialog_params = {
                "directory": str(initial),
                "allow_multiple": False,
                "file_types": (f"{ext_display} files (*{ext})",),
            }
            gate_reason = "file_dialog"
            log_prefix = f"{ext_display} file"
            logger.debug(f"[picker] using webview.FileDialog.OPEN for {ext_display} file dialog")

        logger.info(f"[picker] opening {log_prefix} dialog (initial={initial})")

        if gate is not None:
            with gate.busy(gate_reason):
                logger.debug("[picker] gate acquired")
                selection = await main_window.create_file_dialog(  # type: ignore[attr-defined]
                    dialog_type_enum,
                    **dialog_params,
                )
        else:
            selection = await main_window.create_file_dialog(  # type: ignore[attr-defined]
                dialog_type_enum,
                **dialog_params,
            )

        logger.debug(f"[picker] dialog returned: type={type(selection)} value={selection}")

        if not selection:
            logger.info("[picker] user cancelled (no selection)")
            return None

        # pywebview on macOS often returns tuple; sometimes list
        if isinstance(selection, (list, tuple)):
            first = selection[0] if selection else None
            if first is None:
                return None
            result = str(first)
            logger.info(f"[picker] selected {log_prefix}: {result}")
            return result

        result = str(selection)
        logger.info(f"[picker] selected {log_prefix}: {result}")
        return result

    except Exception as exc:
        logger.exception(f"[picker] pywebview {log_prefix} dialog failed: {exc}")
        return None

def configure_save_on_quit() -> None:
    """Configure save on quit.
    
    safe to call in __main__ and __mp_main__.
    """
    # native = getattr(app, "native", None)
    # if native is None:
    #     logger.debug('not native')
    #     return  # native=False (browser)
    # logger.debug('=== setting pywebview native.window_args["confirm_close"] = True')
    # native.window_args["confirm_close"] = True

    # app.py (module scope; near top, after `from nicegui import app`)
    try:
        # This must be outside the main guard so the native subprocess sees it.
        app.native.window_args["confirm_close"] = True
    except Exception:
        # Web mode or older NiceGUI internals: ignore safely.
        logger.error('FAILED: app.native.window_args["confirm_close"]')
        pass



def configure_native_window_args(context: Optional[AppContext] = None) -> None:
    """Set pywebview window args (x, y, width, height).

    Must run in BOTH __main__ and __mp_main__.
    In __mp_main__, `context.app_config` may not exist, so we load AppConfig directly.

    Args:
        context: Optional AppContext instance. If None, will fetch via AppContext() singleton.
    """
    import multiprocessing as mp

    # MainProcess
    logger.warning(f'current_process_name: {mp.current_process().name}')

    native = getattr(app, "native", None)
    if native is None:
        logger.error('native is None')
        return  # browser mode or native not available

    # Fetch context if not provided
    if context is None:
        context = AppContext()

    rect: tuple[int, int, int, int] | None = None

    # 1) Fast path: MainProcess usually has context.app_config
    try:
        if getattr(context, "app_config", None) is not None:
            rect = context.app_config.get_window_rect()
    except Exception as e:
        logger.warning(f'context.app_config.get_window_rect failed: {e}')
        rect = None

    # 2) Fallback: load AppConfig directly (works in __mp_main__/Process-1)
    if rect is None:
        try:
            # Import your AppConfig class (update module path to your repo)
            from kymflow.gui_v2.app_config import AppConfig  # <-- adjust if needed

            # If AppConfig constructor auto-loads from platformdirs, this is enough:
            app_cfg = AppConfig.load()  # <-- if your AppConfig needs a path, pass it here
            rect = app_cfg.get_window_rect()
            logger.warning(f'loaded rect via standalone AppConfig: {rect}')
        except Exception as e:
            logger.error(f'failed to load standalone AppConfig for window rect: {e}')
            rect = None

    if rect is None:
        logger.warning('no window rect available; using default placement')
        return

    x, y, w, h = map(int, rect)

    # guard against garbage
    if w < 200 or h < 200:
        logger.warning(f'window rect too small; ignoring: {(x, y, w, h)}')
        return

    # omit rect if position is off-screen (e.g. secondary display disconnected);
    # let OS choose placement to avoid pywebview Cocoa AttributeError
    if x < 0 or y < 0:
        logger.warning(f'window rect has off-screen position (x={x}, y={y}); omitting rect, OS will place window')
        return

    logger.warning(f'setting initial pywebview window: x={x} y={y} w={w} h={h}')

    native.window_args.update({
        "x": x,
        "y": y,
        "width": w,
        "height": h,
    })

    # logger.warning(f'native.window_args now: {native.window_args}')
    