"""KymFlow GUI v2 application entry point.

This module provides the main entry point for the v2 GUI, which uses an event-driven
architecture with per-client EventBus instances for clean signal flow and isolation.

Run with:
    uv run python -m kymflow.gui_v2.app
"""

from __future__ import annotations

import os
import sys
import multiprocessing as mp
from multiprocessing import freeze_support
from pathlib import Path

#
# added for pyinstaller
# --- Matplotlib cache: MUST run before importing anything that might import matplotlib ---
from platformdirs import user_cache_dir

# from kymflow.gui_v2._window_size_timer import install_native_window_persistence

def _init_mpl_cache_dir() -> None:
    """Ensure Matplotlib uses a stable, writable cache dir (works for frozen + dev)."""
    cache_root = Path(user_cache_dir("kymflow")) / "matplotlib"
    cache_root.mkdir(parents=True, exist_ok=True)

    # Critical: forces font cache + other mpl caches to live here
    os.environ.setdefault("MPLCONFIGDIR", str(cache_root))

    # Optional but often helpful for frozen apps that only render/save figures
    # (If you truly need interactive mpl backends, remove this.)
    os.environ.setdefault("MPLBACKEND", "Agg")


def _warm_mpl_font_cache_once() -> None:
    """
    Warm font cache in the MAIN process only.
    Uses a sentinel file so the warm step runs once per user cache dir.
    """
    mpl_dir = Path(os.environ["MPLCONFIGDIR"])
    sentinel = mpl_dir / ".fontcache_warmed_v1"

    if sentinel.exists():
        return

    try:
        import matplotlib  # noqa: F401
        from matplotlib import font_manager

        # Trigger cache creation/loading
        _ = font_manager.fontManager  # noqa: F841
        font_manager.findSystemFonts()

        sentinel.write_text("ok\n", encoding="utf-8")
    except Exception:
        # Never block app startup if mpl cache warming fails
        pass


_init_mpl_cache_dir()
# -------------------------------------------------------------------

from nicegui import ui

from kymflow.core.utils.logging import get_logger, setup_logging
from kymflow.gui_v2.app_context import AppContext
from kymflow.gui_v2.shutdown_handlers import install_shutdown_handlers
from kymflow.gui_v2.config import DEFAULT_PORT, STORAGE_SECRET
from kymflow.gui_v2.navigation import inject_global_styles

from kymflow.gui_v2.bus import BusConfig, get_event_bus
from kymflow.gui_v2.events_folder import FolderChosen
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

# ---------------------------------------------------------------------
# Dev folder (hard-coded, env overridable)
# ---------------------------------------------------------------------
_DEFAULT_DEV_FOLDER = Path("/Users/cudmore/Sites/kymflow_outer/kymflow/tests/data")
# _DEFAULT_DEV_FOLDER = Path("/Users/cudmore/Dropbox/data/declan/2026/declan-data-analyzed")

# _DEFAULT_DEV_FOLDER = Path("/Users/cudmore/Dropbox/data/declan/2026/compare-condiitons/box-download")

# DO THIS NOW !!!!! 2026 jan 26
# _DEFAULT_DEV_FOLDER = Path("/Users/cudmore/Dropbox/data/declan/2026/data/20251204")

DEV_FOLDER = Path(os.getenv("KYMFLOW_DEV_FOLDER", str(_DEFAULT_DEV_FOLDER))).expanduser()
USE_DEV_FOLDER = os.getenv("KYMFLOW_USE_DEV_FOLDER", "0") == "1"  # Default to "0" (disabled)

# USE_DEV_FOLDER = False  # abb turn of before impleenting ~/ kymflow config json

# Shared application context (singleton, process-level)
# AppContext.__init__ will check if we're in a worker process and skip initialization
context = AppContext()

# abb setting window size hook
_native_window_persistence_installed = False

@ui.page("/")
def home() -> None:
    """Home route for v2 GUI.

    Uses cached page instances to prevent recreation on navigation.
    Each browser tab/window gets its own isolated session.
    """

    # global _native_window_persistence_installed
    # if not _native_window_persistence_installed:
    #     _native_window_persistence_installed = True
    #     ui.timer(0.2, lambda: install_native_window_persistence(context.user_config), once=True)

    ui.page_title("KymFlow")
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
        # Precedence: dev override > last folder from config
        if USE_DEV_FOLDER and DEV_FOLDER.exists():
            logger.info(f"DEV bootstrap: emitting FolderChosen({DEV_FOLDER}) for session {session_id[:8]}...")
            page.bus.emit(FolderChosen(folder=str(DEV_FOLDER)))
        else:
            # Try to load last folder from user config
            last_path, last_depth = context.user_config.get_last_folder()
            if last_path:
                last_folder_path = Path(last_path)
                if last_folder_path.exists():
                    logger.info(
                        f"Loading last folder from config: {last_path} (depth={last_depth}) "
                        f"for session {session_id[:8]}..."
                    )
                    page.bus.emit(FolderChosen(folder=last_path, depth=last_depth))
                else:
                    logger.debug(f"Last folder from config does not exist: {last_path}")


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
    is_frozen = getattr(sys, "frozen", False)

    default_reload = (not is_frozen) and os.getenv("KYMFLOW_GUI_RELOAD", "1") == "1"
    reload = default_reload if reload is None else reload

    default_native = os.getenv("KYMFLOW_GUI_NATIVE", "0") == "1"
    native = default_native if native is None else native

    logger.info(
        "Starting KymFlow GUI v2: port=%s reload=%s native=%s USE_DEV_FOLDER=%s DEV_FOLDER=%s",
        DEFAULT_PORT,
        reload,
        native,
        USE_DEV_FOLDER,
        DEV_FOLDER,
    )

    # abb for pyinstaller
    # Warm matplotlib cache once (main process only; safe in frozen builds)
    _warm_mpl_font_cache_once()
    
    x, y, w, h = context.user_config.get_window_rect()
    # logger.info(f"user_config window_rect: {x}, {y}, {w}, {h}")

    reload = False
    native = True

    install_shutdown_handlers(context, native=native)

    ui.run(
        port=DEFAULT_PORT,
        reload=reload,
        native=native,
        window_size=(w, h),
        storage_secret=STORAGE_SECRET,
        title="KymFlow",
    )

    logger.info('here')


if __name__ in {"__main__", "__mp_main__", "kymflow.gui_v2.app"}:
    freeze_support()
    # CRITICAL: Only start GUI in the actual main process, not in worker processes
    # Worker processes will have __name__ == "__mp_main__" but process name != "MainProcess"
    current_process = mp.current_process()
    is_main_process = current_process.name == "MainProcess"
    
    logger.info(f"__name__: {__name__}, process: {current_process.name}, is_main: {is_main_process}")
    
    if is_main_process:
        main()
    else:
        # This is a worker process - do NOT start the GUI
        logger.debug(f"Skipping GUI startup in worker process: {current_process.name}")