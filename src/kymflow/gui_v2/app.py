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
from kymflow.gui.app_context import AppContext
from kymflow.gui.config import DEFAULT_PORT, STORAGE_SECRET
from kymflow.gui.navigation import inject_global_styles

from kymflow.gui_v2.bus import BusConfig, get_event_bus
from kymflow.gui_v2.events_folder import FolderChosen
from kymflow.gui_v2.pages.home_page import HomePage

logger = get_logger(__name__)

# Configure logging at module import (runs in uvicorn worker)
setup_logging(
    level="INFO",
    log_file=Path.home() / ".kymflow" / "logs" / "kymflow.log",
)

# ---------------------------------------------------------------------
# Dev folder (hard-coded, env overridable)
# ---------------------------------------------------------------------
_DEFAULT_DEV_FOLDER = Path("/Users/cudmore/Sites/kymflow_outer/kymflow/tests/data")
DEV_FOLDER = Path(os.getenv("KYMFLOW_DEV_FOLDER", str(_DEFAULT_DEV_FOLDER))).expanduser()
USE_DEV_FOLDER = os.getenv("KYMFLOW_USE_DEV_FOLDER", "1") == "1"

# Shared application context (singleton, process-level)
context = AppContext()

# Track which clients have been bootstrapped (per-client dev folder loading)
_BOOTSTRAPPED_CLIENTS: set[str] = set()


@ui.page("/")
def home() -> None:
    """Home route for v2 GUI.

    Creates a per-client EventBus and HomePage instance. Each browser tab/window
    gets its own isolated bus to prevent cross-client event leakage.
    """
    from kymflow.gui_v2.bus import get_client_id

    ui.page_title("KymFlow")
    inject_global_styles()

    # Get per-client EventBus (created on first access for this client)
    bus = get_event_bus(BusConfig(trace=True))
    client_id = get_client_id()

    # Build UI (this must construct FileTableView + FileTableBindings)
    page = HomePage(context, bus)
    page.render(page_title="KymFlow")

    # Emit dev bootstrap event once per client (if enabled)
    if USE_DEV_FOLDER and client_id not in _BOOTSTRAPPED_CLIENTS:
        if DEV_FOLDER.exists():
            logger.info(f"DEV bootstrap: emitting FolderChosen({DEV_FOLDER}) for client {client_id}")
            bus.emit(FolderChosen(folder=str(DEV_FOLDER)))
        else:
            logger.warning(f"DEV_FOLDER does not exist: {DEV_FOLDER}")
        _BOOTSTRAPPED_CLIENTS.add(client_id)


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
        storage_secret=STORAGE_SECRET,
        title="KymFlow",
    )


if __name__ in {"__main__", "__mp_main__", "kymflow.gui_v2.app"}:
    freeze_support()
    logger.info(f"__name__: {__name__}")
    main()