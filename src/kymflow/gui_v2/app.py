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

#
from platformdirs import user_cache_dir

from nicegui import ui, app

from kymflow.core.utils.logging import get_logger, setup_logging
from kymflow.gui_v2.app_context import AppContext
from kymflow.gui_v2._pywebview import (
    configure_native_window_args,
    configure_save_on_quit,
    install_shutdown_handlers,
)
from kymflow.gui_v2.config import STORAGE_SECRET
from kymflow.gui_v2.navigation import inject_global_styles

from kymflow.gui_v2.bus import BusConfig, get_event_bus
from kymflow.gui_v2.events_folder import SelectPathEvent
from kymflow.gui_v2.page_cache import cache_page, get_cached_page, get_stable_session_id
from kymflow.gui_v2.pages.batch_page import BatchPage
from kymflow.gui_v2.pages.home_page import HomePage
from kymflow.gui_v2.pages.pool_page import PoolPage

logger = get_logger(__name__)

# Configure logging at module import (runs in uvicorn worker)
setup_logging(
    level="DEBUG",
    log_file=Path.home() / ".kymflow" / "logs" / "kymflow.log",
)

# Shared application context (singleton, process-level)
# AppContext.__init__ will check if we're in a worker process and skip initialization
context = AppContext()

@ui.page("/")
def home() -> None:
    """Home route for v2 GUI.

    Uses cached page instances to prevent recreation on navigation.
    Each browser tab/window gets its own isolated session.
    """

    logger.info('xxx')
    
    # Install native rect polling only in native mode (delayed slightly so native window exists).
    # Skip entirely in browser mode - no reason to poll native window rects.
    native = getattr(app, "native", None)
    if native is not None:
        from kymflow.gui_v2._pywebview import install_native_rect_polling
        ui.timer(0.2, lambda: install_native_rect_polling(poll_sec=0.5, debounce_sec=1.0), once=True)

    #
    # global css styles
    # this has to be in a page function ???
    from kymflow.gui_v2.styles import install_global_styles
    install_global_styles()

    ui.page_title("KymFlow")
    
    # set style of all nicegui ui widgets
    inject_global_styles()

    # Get stable session ID (persists across navigations)
    session_id = get_stable_session_id()

    # Get or create cached page instance
    cached_page = get_cached_page(session_id, "/")
    if cached_page is not None:
        # Reuse cached page
        # logger.debug(f"Reusing cached HomePage for session {session_id[:8]}...")
        page = cached_page
    else:
        # Create new page instance and cache it
        # bus = get_event_bus(BusConfig(trace=True))
        bus = get_event_bus()
        page = HomePage(context, bus)
        cache_page(session_id, "/", page)
        # logger.debug(f"Created and cached new HomePage for session {session_id[:8]}...")

    # Render the page (creates fresh UI elements each time and ensures setup)
    page.render(page_title="KymFlow")

    # original before bootstrap from gpt for web render
    
    # Bootstrap folder loading once per session (if enabled)
    # MUST be after render() so controllers are set up via _ensure_setup()
    # Only bootstrap if this is a new page instance (cached_page is None)
    # and no folder is already loaded
    # if cached_page is None and context.app_state.folder is None:
    #     # Try to load last path from user config
    #     last_path, last_depth = context.user_config.get_last_path()
    #     if last_path:
    #         last_path_obj = Path(last_path)
    #         if last_path_obj.exists():
    #             # Emit event - FolderController will auto-detect CSV from path
    #             logger.info(
    #                 f"Loading last path from config: {last_path} (depth={last_depth}) "
    #                 f"for session {session_id[:8]}..."
    #             )
    #             page.bus.emit(SelectPathEvent(
    #                 new_path=last_path,
    #                 depth=last_depth,
    #                 phase="intent",
    #             ))
    #         else:
    #             logger.debug(f"Last path from config does not exist: {last_path}")

    # Bootstrap folder loading once per session (if enabled)
    # NOTE: determine web/native from the same env var used by main(), NOT from app.native/main_window.
    if cached_page is None and context.app_state.folder is None:
        last_path, last_depth = context.user_config.get_last_path()

        # Decide "web vs native" robustly
        # - In Render/Docker we set KYMFLOW_GUI_NATIVE=0
        # - Locally (no env var) your default is native=True
        raw_native = os.getenv("KYMFLOW_GUI_NATIVE", "").strip().lower()
        is_web = raw_native in {"0", "false", "no", "off"}

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
            chosen_source = "default_path" if default_path else ("last_path" if last_path else "none")
        else:
            chosen_path = last_path
            chosen_depth = last_depth
            chosen_source = "last_path" if last_path else "none"

        # ---- Debug logging (so you can see exactly what branch you hit) ----
        logger.info(f"[bootstrap] cached_page is None: {cached_page is None}")
        logger.info(f"[bootstrap] context.app_state.folder is None: {context.app_state.folder is None}")
        logger.info(f"[bootstrap] KYMFLOW_GUI_NATIVE raw: {raw_native!r} -> is_web={is_web}")
        logger.info(f"[bootstrap] last_path={last_path!r} last_depth={last_depth!r}")
        logger.info(f"[bootstrap] KYMFLOW_DEFAULT_PATH={default_path!r}")
        logger.info(f"[bootstrap] KYMFLOW_DEFAULT_DEPTH raw={raw_default_depth!r} parsed={default_depth!r}")
        logger.info(f"[bootstrap] chosen_source={chosen_source} chosen_path={chosen_path!r} chosen_depth={chosen_depth!r}")

        if chosen_path:
            chosen_path_obj = Path(chosen_path)
            exists = chosen_path_obj.exists()
            logger.info(f"[bootstrap] chosen_path exists={exists} resolved={str(chosen_path_obj)!r}")

            if exists:
                logger.info(f"[bootstrap] emitting SelectPathEvent new_path={str(chosen_path_obj)!r} depth={chosen_depth!r}")
                page.bus.emit(
                    SelectPathEvent(
                        new_path=str(chosen_path_obj),
                        depth=int(chosen_depth) if chosen_depth is not None else 3,
                        phase="intent",
                    )
                )
            else:
                logger.warning(f"[bootstrap] Bootstrap path does not exist: {chosen_path!r}")
        else:
            logger.info("[bootstrap] No chosen_path (nothing to bootstrap)")



@ui.page("/batch")
def batch() -> None:
    """Batch route for v2 GUI.

    Uses cached page instances to prevent recreation on navigation.
    Each browser tab/window gets its own isolated session.
    """
    ui.page_title("KymFlow - Batch")
    inject_global_styles()

    # Get stable session ID (persists across navigations)
    session_id = get_stable_session_id()

    # Get or create cached page instance
    cached_page = get_cached_page(session_id, "/batch")
    if cached_page is not None:
        # Reuse cached page
        # logger.debug(f"Reusing cached BatchPage for session {session_id[:8]}...")
        page = cached_page
    else:
        # Create new page instance and cache it
        # bus = get_event_bus(BusConfig(trace=False))
        bus = get_event_bus()
        page = BatchPage(context, bus)
        cache_page(session_id, "/batch", page)
        # logger.debug(f"Created and cached new BatchPage for session {session_id[:8]}...")

    # Render the page (creates fresh UI elements each time)
    page.render(page_title="KymFlow - Batch")


@ui.page("/pool")
def pool() -> None:
    """Pool route for v2 GUI.

    Uses cached page instances to prevent recreation on navigation.
    Each browser tab/window gets its own isolated session.
    """
    ui.page_title("KymFlow - Pool")
    inject_global_styles()

    # Get stable session ID (persists across navigations)
    session_id = get_stable_session_id()

    # Get or create cached page instance
    cached_page = get_cached_page(session_id, "/pool")
    if cached_page is not None:
        # Reuse cached page
        # logger.debug(f"Reusing cached PoolPage for session {session_id[:8]}...")
        page = cached_page
    else:
        # Create new page instance and cache it
        # bus = get_event_bus(BusConfig(trace=False))
        bus = get_event_bus()
        page = PoolPage(context, bus)
        cache_page(session_id, "/pool", page)
        # logger.debug(f"Created and cached new PoolPage for session {session_id[:8]}...")

    # Render the page (creates fresh UI elements each time)
    page.render(page_title="KymFlow - Pool")

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
    """
    native_bool = _env_bool("KYMFLOW_GUI_NATIVE", True) if native_bool is None else native_bool
    reload = _env_bool("KYMFLOW_GUI_RELOAD", False) if reload is None else reload

    # Render sets PORT; if absent use 8080.
    # from nicegui import native as native_module
    # port = _env_int("PORT", native_module.find_open_port())
    # port = _env_int("PORT", 8080)
    from nicegui import native as native_module    
    port = _env_int("PORT", native_module.find_open_port())

    # For web deployments you MUST bind 0.0.0.0; for native local dev, 127.0.0.1 is fine.
    default_host = "127.0.0.1" if native_bool else "0.0.0.0"
    host = os.getenv("HOST", default_host)

    logger.info(
        "Starting KymFlow GUI v2: port=%s reload=%s native=%s",
        port,
        reload,
        native_bool,
    )

    # Register minimal shutdown handlers to persist configs (native mode only)
    if native_bool:
        install_shutdown_handlers(context)

    ui.run(
        host=host,
        port=port,
        reload=reload,
        native=native_bool,
        storage_secret=STORAGE_SECRET,
        title="KymFlow",
    )


if __name__ in {"__main__", "__mp_main__", "kymflow.gui_v2.app"}:
    freeze_support()
    # CRITICAL: Only start GUI in the actual main process, not in worker processes
    # Worker processes will have __name__ == "__mp_main__" but process name != "MainProcess"
    current_process = mp.current_process()
    is_main_process = current_process.name == "MainProcess"
    
    logger.info(f"__name__: {__name__}, process: {current_process.name}, is_main: {is_main_process}")
    

    native_bool = _env_bool("KYMFLOW_GUI_NATIVE", True)
    if native_bool:
        configure_save_on_quit()
        configure_native_window_args(context)

    if is_main_process:
        main()

    else:
        # This is a worker process - do NOT start the GUI
        logger.debug(f"Skipping GUI startup in worker process: {current_process.name}")