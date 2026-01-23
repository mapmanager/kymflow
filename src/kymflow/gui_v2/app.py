"""KymFlow GUI v2 application entry point.

This module provides the main entry point for the v2 GUI, which uses an event-driven
architecture with per-client EventBus instances for clean signal flow and isolation.

Run with:
    uv run python -m kymflow.gui_v2.app
"""

from __future__ import annotations

import os
import sys
from multiprocessing import freeze_support
from pathlib import Path

from nicegui import ui

from kymflow.core.utils.logging import get_logger, setup_logging
from kymflow.gui_v2.app_context import AppContext
from kymflow.gui_v2.config import DEFAULT_PORT, STORAGE_SECRET
from kymflow.gui_v2.navigation import inject_global_styles

from kymflow.gui_v2.bus import BusConfig, get_event_bus
from kymflow.gui_v2.events_folder import FolderChosen
from kymflow.gui_v2.page_cache import cache_page, get_cached_page, get_stable_session_id
from kymflow.gui_v2.pages.about_page import AboutPage
from kymflow.gui_v2.pages.home_page import HomePage

logger = get_logger(__name__)

# Configure logging at module import (runs in uvicorn worker)
setup_logging(
    level="DEBUG",
    log_file=Path.home() / ".kymflow" / "logs" / "kymflow.log",
)

# ---------------------------------------------------------------------
# Dev folder (hard-coded, env overridable)
# ---------------------------------------------------------------------
# _DEFAULT_DEV_FOLDER = Path("/Users/cudmore/Sites/kymflow_outer/kymflow/tests/data")
# _DEFAULT_DEV_FOLDER = Path("/Users/cudmore/Dropbox/data/declan/2026/declan-data-analyzed")
_DEFAULT_DEV_FOLDER = Path("/Users/cudmore/Dropbox/data/declan/2026/data/20251204")
DEV_FOLDER = Path(os.getenv("KYMFLOW_DEV_FOLDER", str(_DEFAULT_DEV_FOLDER))).expanduser()
USE_DEV_FOLDER = os.getenv("KYMFLOW_USE_DEV_FOLDER", "1") == "1"

# Shared application context (singleton, process-level)
context = AppContext()


@ui.page("/")
def home() -> None:
    """Home route for v2 GUI.

    Uses cached page instances to prevent recreation on navigation.
    Each browser tab/window gets its own isolated session.
    """
    ui.page_title("KymFlow")
    inject_global_styles()

    # Get stable session ID (persists across navigations)
    session_id = get_stable_session_id()

    # Get or create cached page instance
    cached_page = get_cached_page(session_id, "/")
    if cached_page is not None:
        # Reuse cached page
        logger.debug(f"Reusing cached HomePage for session {session_id[:8]}...")
        page = cached_page
    else:
        # Create new page instance and cache it
        bus = get_event_bus(BusConfig(trace=True))
        page = HomePage(context, bus)
        cache_page(session_id, "/", page)
        logger.debug(f"Created and cached new HomePage for session {session_id[:8]}...")

    # Render the page (creates fresh UI elements each time and ensures setup)
    page.render(page_title="KymFlow")

    # Emit dev bootstrap event once per session (if enabled)
    # MUST be after render() so controllers are set up via _ensure_setup()
    # Only bootstrap if:
    # 1. This is a new page instance (cached_page is None)
    # 2. Dev folder loading is enabled
    # 3. AppState doesn't already have this folder loaded (prevents redundant loading)
    folder_already_loaded = (
        context.app_state.folder is not None
        and context.app_state.folder.resolve() == DEV_FOLDER.resolve()
    )
    if cached_page is None and USE_DEV_FOLDER and not folder_already_loaded:
        if DEV_FOLDER.exists():
            logger.info(f"DEV bootstrap: emitting FolderChosen({DEV_FOLDER}) for session {session_id[:8]}...")
            page.bus.emit(FolderChosen(folder=str(DEV_FOLDER)))
        else:
            logger.warning(f"DEV_FOLDER does not exist: {DEV_FOLDER}")


@ui.page("/about")
def about() -> None:
    """About route for v2 GUI.

    Displays version information and application logs. Uses cached page
    instances to prevent recreation on navigation.
    """
    ui.page_title("KymFlow - About")
    inject_global_styles()

    # Get stable session ID (persists across navigations)
    session_id = get_stable_session_id()

    # Get or create cached page instance
    cached_page = get_cached_page(session_id, "/about")
    if cached_page is not None:
        # Reuse cached page
        logger.debug(f"Reusing cached AboutPage for session {session_id[:8]}...")
        page = cached_page
    else:
        # Create new page instance and cache it
        bus = get_event_bus(BusConfig(trace=False))
        page = AboutPage(context, bus)
        cache_page(session_id, "/about", page)
        logger.debug(f"Created and cached new AboutPage for session {session_id[:8]}...")

    # Render the page (creates fresh UI elements each time)
    page.render(page_title="KymFlow - About")


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

    ui.run(
        port=DEFAULT_PORT,
        reload=reload,
        native=native,
        window_size=(1200, 800),
        storage_secret=STORAGE_SECRET,
        title="KymFlow",
    )


if __name__ in {"__main__", "__mp_main__", "kymflow.gui_v2.app"}:
    freeze_support()
    logger.info(f"__name__: {__name__}")
    main()