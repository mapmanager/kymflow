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
from kymflow.gui_v2.config import DEFAULT_PORT, STORAGE_SECRET
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

    # Install once per session, delayed slightly so native window exists.
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

    # Bootstrap folder loading once per session (if enabled)
    # MUST be after render() so controllers are set up via _ensure_setup()
    # Only bootstrap if this is a new page instance (cached_page is None)
    # and no folder is already loaded
    if cached_page is None and context.app_state.folder is None:
        # Try to load last path from user config
        last_path, last_depth = context.user_config.get_last_path()
        if last_path:
            last_path_obj = Path(last_path)
            if last_path_obj.exists():
                # Emit event - FolderController will auto-detect CSV from path
                logger.info(
                    f"Loading last path from config: {last_path} (depth={last_depth}) "
                    f"for session {session_id[:8]}..."
                )
                page.bus.emit(SelectPathEvent(
                    new_path=last_path,
                    depth=last_depth,
                    phase="intent",
                ))
            else:
                logger.debug(f"Last path from config does not exist: {last_path}")


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


def main(*, reload: bool | None = None, native: bool | None = None) -> None:
    """Start the KymFlow v2 GUI application.

    Args:
        reload: Enable auto-reload on code changes. If None, auto-detects based on
            frozen state and KYMFLOW_GUI_RELOAD env var.
        native: Launch as native desktop app. If None, uses KYMFLOW_GUI_NATIVE env var.
    """
    
    # keep this, is usefull for github workflow to build app with nicegui-pack (pyinstaller)
    # see kymflow/.github/workflows/release.yml
    # is_frozen = getattr(sys, "frozen", False)

    # default_reload = (not is_frozen) and os.getenv("KYMFLOW_GUI_RELOAD", "1") == "1"
    # reload = default_reload if reload is None else reload

    # default_native = os.getenv("KYMFLOW_GUI_NATIVE", "0") == "1"
    # native = default_native if native is None else native

    native = True
    reload = False

    logger.info(
        "Starting KymFlow GUI v2: port=%s reload=%s native=%s",
        DEFAULT_PORT,
        reload,
        native,
    )

    if native:
        x, y, w, h = context.app_config.get_window_rect()
        logger.info(f'  === loaded window_rect: {x}, {y}, {w}, {h}')
        if w<100 or h<100:
            logger.error(f'20260205 window_rect is too small: {w}, {h}')
            window_size = None
        else:
            window_size = (w, h)
    else:
        window_size = None

    # Register minimal shutdown handlers to persist configs
    # window_rect is updated by poller in app_config
    install_shutdown_handlers(context, native=native)

    # never set nicegui window_size, is handled in configure_native_window_args()
    window_size = None
    
    # configure_save_on_quit()
    
    ui.run(
        port=DEFAULT_PORT,
        reload=reload,
        native=native,
        # window_size=window_size,
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
    

    configure_save_on_quit()
    configure_native_window_args(context)

    if is_main_process:
        main()

    else:
        # This is a worker process - do NOT start the GUI
        logger.debug(f"Skipping GUI startup in worker process: {current_process.name}")