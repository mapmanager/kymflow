"""KymFlow GUI v2 application entry point.

This module provides the main entry point for the v2 GUI, which uses an event-driven
architecture with per-client EventBus instances for clean signal flow and isolation.

Run with:
    uv run python -m kymflow.gui_v2.app
"""

from __future__ import annotations

import os
import multiprocessing as mp
from multiprocessing import freeze_support
from pathlib import Path

from platformdirs import user_config_dir

# abb declan 20260225, fixing frozen nicegui runtime error `OSError: [Errno 30] Read-only file system: '/.nicegui'`
# NiceGUI persistence: use platformdirs app dir so path is writable when .app runs with CWD=/
os.environ["NICEGUI_STORAGE_PATH"] = str(Path(user_config_dir("kymflow", None)) / ".nicegui")

from nicegui import ui, app

from kymflow.core.utils.logging import get_logger, setup_logging
from kymflow.gui_v2.app_context import AppContext
from kymflow.gui_v2.app_config import AppConfig
from kymflow.gui_v2._pywebview import (
    configure_native_window_args,
    configure_save_on_quit,
    # install_shutdown_handlers,
)
from kymflow.gui_v2.config import STORAGE_SECRET
from kymflow.gui_v2.navigation import inject_global_styles

from kymflow.gui_v2.bus import get_event_bus
from kymflow.gui_v2.events_folder import SelectPathEvent
from kymflow.gui_v2.page_cache import cache_page, get_cached_page, get_stable_session_id
from kymflow.gui_v2.runtime_mode import is_native_mode
# from kymflow.gui_v2.pages.batch_page import BatchPage
from kymflow.gui_v2.pages.home_page import HomePage
# from kymflow.gui_v2.pages.pool_page import PoolPage

logger = get_logger(__name__)

# Configure logging at module import (runs in uvicorn worker)
setup_logging(level="DEBUG")

# Shared application context (singleton, process-level)
# AppContext.__init__ will check if we're in a worker process and skip initialization
# context = AppContext()

# def _tmp_native_drop(e):
#     ctx = AppContext()
#     logger.info(e)

# supported events: shown, loaded, minimized, maximized, restored, resized, moved, closed, drop
# app.native.on('resized', _native_resize)
# app.native.on('moved', _native_moved)
# app.native.on('drop', _tmp_native_drop)
# app.native.on('drop', lambda e: print(f'Dropped files: {e.args["files"]}'))

# app.native.start_args['debug'] = True

def _native_init_window_position():
    app_config = AppConfig.load()

    x, y, w, h = app_config.get_window_rect()

    logger.info(f"  initial window rect: x:{x}, y:{y}, w:{w}, h:{h}")
    app.native.window_args.update({
        "x": x,
        "y": y,
        "width": w,
        "height": h,
    })
_native_init_window_position()

# this is REQUIRED here for nicegui-pack (pyinstaller) to work
try:
    app.native.window_args["confirm_close"] = True
    logger.info(f'global app.native.window_args: {app.native.window_args}')
except Exception:
    # Web mode or older NiceGUI internals: ignore safely.
    logger.error('FAILED: app.native.window_args["confirm_close"]')
    pass

@ui.page("/")
def home() -> None:
    """Home route for v2 GUI.

    Uses cached page instances to prevent recreation on navigation.
    Each browser tab/window gets its own isolated session.
    """

    _storage_path = os.environ.get("NICEGUI_STORAGE_PATH", "(not set)")
    logger.info(f"NICEGUI_STORAGE_PATH={_storage_path}")

    # this has to be in a page function ???
    from kymflow.gui_v2.styles import install_global_styles
    install_global_styles()

    ui.page_title("KymFlow")
    
    # set style of all nicegui ui widgets
    inject_global_styles()

    # one ocntext for this page
    context = AppContext()

    # app.native.on('resized', _native_resize)
    # app.native.on('moved', _native_moved)

    logger.info(f"  app.native.window_args: {app.native.window_args}")

    if is_native_mode():
        # Native desktop: no stable session id or page cache (disk-backed AppConfig instead).
        # install_shutdown_handlers(context)  # only used for native
    
        cached_page = None
        bus = get_event_bus()
        page = HomePage(context, bus)
        logger.info("native mode: skipping stable session id and page cache")
    else:
        session_id = get_stable_session_id()
        cached_page = get_cached_page(session_id, "/")
        logger.info(f"cached_page:{cached_page}")

        if cached_page is not None:
            page = cached_page
        else:
            bus = get_event_bus()
            page = HomePage(context, bus)
            cache_page(session_id, "/", page)

    # Render the page (creates fresh UI elements each time and ensures setup)
    page.render(page_title="KymFlow")

    # Bootstrap folder loading once per session (if enabled)
    # NOTE: determine web/native from the same env var used by main(), NOT from app.native/main_window.
    if cached_page is None and context.app_state.folder is None:
        last_path, last_depth = context.user_config.get_last_path()

        # Web vs native: same rule as is_native_mode() / main().
        is_web = not is_native_mode()

        default_path = os.getenv("KYMFLOW_DEFAULT_PATH") if is_web else None

        raw_default_depth = os.getenv("KYMFLOW_DEFAULT_DEPTH", "4")
        try:
            default_depth = int(raw_default_depth) if is_web else None
        except ValueError:
            default_depth = 4 if is_web else None

        # In web mode, prefer default_path; in native mode, prefer last_path
        if is_web:
            chosen_path = default_path or last_path
            chosen_depth = default_depth if default_path else last_depth
            # chosen_source = "default_path" if default_path else ("last_path" if last_path else "none")
        else:
            chosen_path = last_path
            chosen_depth = last_depth
            # chosen_source = "last_path" if last_path else "none"

        if chosen_path:
            chosen_path_obj = Path(chosen_path)
            exists = chosen_path_obj.exists()
            # logger.info(f"chosen_path exists={exists} resolved={str(chosen_path_obj)!r}")

            if exists:
                logger.info("-->> emitting SelectPathEvent")
                logger.info(f'  new_path={str(chosen_path_obj)}')
                logger.info(f'  depth={chosen_depth}')
                page.bus.emit(
                    SelectPathEvent(
                        new_path=str(chosen_path_obj),
                        depth=int(chosen_depth) if chosen_depth is not None else 3,
                        phase="intent",
                    )
                )
            else:
                logger.warning(f"-->> path does not exist: {chosen_path!r}")
        else:
            logger.info("-->> No chosen_path (nothing to bootstrap)")

def _env_bool(name: str, default: bool) -> bool:
    """Parse env var as bool; if unset/invalid returns default."""
    raw = os.getenv(name)
    if raw is None:
        return default
    v = raw.strip().lower()
    if v in {"1", "true", "yes", "on"}:
        return True
    if v in {"0", "false", "no", "off"}:
        return False
    return default


def _env_int(name: str, default: int) -> int:
    """Parse env var as int; if unset/invalid returns default."""
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default

def main(*, reload: bool | None = None, native_bool: bool | None = None) -> None:
    """Start the KymFlow v2 GUI application.

    Defaults (no env vars, no args):
      - native=True
      - reload=False

    Env vars (used only when arg is None):
      - KYMFLOW_GUI_NATIVE: 1/0
      - KYMFLOW_GUI_RELOAD: 1/0
      - HOST: bind host (Render commonly uses 0.0.0.0)
      - PORT: bind port (Render sets this)

    If ``native_bool`` is passed explicitly, ``KYMFLOW_GUI_NATIVE`` is set so
    :func:`~kymflow.gui_v2.runtime_mode.is_native_mode` matches ``ui.run(native=...)``.
    """
    if native_bool is not None:
        os.environ["KYMFLOW_GUI_NATIVE"] = "1" if native_bool else "0"
    native_bool = is_native_mode()
    reload = _env_bool("KYMFLOW_GUI_RELOAD", False) if reload is None else reload

    native_bool = False
    
    from nicegui import native as native_module    
    if native_bool:
        port = _env_int("PORT", native_module.find_open_port())
    else:
        port = _env_int("PORT", 8080)

    # For web deployments you MUST bind 0.0.0.0; for native local dev, 127.0.0.1 is fine.
    default_host = "127.0.0.1" if native_bool else "0.0.0.0"
    host = os.getenv("HOST", default_host)

    # moved into home / page
    # if native_bool:
    #     install_shutdown_handlers(context)

    logger.info('Starting KymFlow GUI ui.run with')
    logger.info(f'  host={host}')
    logger.info(f'  port={port}')
    logger.info(f'  reload={reload}')
    logger.info(f'  native={native_bool}')

    run_kwargs: dict = {
        "host": host,
        "port": port,
        "reload": reload,
        "native": native_bool,
        "title": "KymFlow",
    }
    if not native_bool:
        run_kwargs["storage_secret"] = STORAGE_SECRET
    ui.run(**run_kwargs)


if __name__ in {"__main__", "__mp_main__", "kymflow.gui_v2.app"}:
    freeze_support()
    # CRITICAL: Only start GUI in the actual main process, not in worker processes
    # Worker processes will have __name__ == "__mp_main__" but process name != "MainProcess"
    current_process = mp.current_process()
    is_main_process = current_process.name == "MainProcess"
    
    logger.info(f"__name__: {__name__}, process: {current_process.name}, is_main: {is_main_process}")
    

    native_bool = is_native_mode()
    # configure_save_on_quit()

    # try:
    #     app.native.window_args["confirm_close"] = True
    # except Exception:
    #     # Web mode or older NiceGUI internals: ignore safely.
    #     logger.error('2 FAILED: app.native.window_args["confirm_close"]')
    #     pass

    # if native_bool:
        # try:
        #     app.native.window_args["confirm_close"] = True
        # except Exception:
        #     # Web mode or older NiceGUI internals: ignore safely.
        #     logger.error('3 FAILED: app.native.window_args["confirm_close"]')
        #     pass

        # removed while making context local to home / page
        # configure_save_on_quit()
        # configure_native_window_args(context)

    if is_main_process:
        main()

    else:
        # This is a worker process - do NOT start the GUI
        logger.debug(f"Skipping GUI startup in worker process: {current_process.name}")