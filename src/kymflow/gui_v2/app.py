# src/kymflow/gui_v2/app.py
# gpt 20260106: dev bootstrap emits FolderChosen AFTER controllers subscribe (HomePage init)

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

from kymflow.gui_v2.bus import BusConfig, EventBus
from kymflow.gui_v2.events_folder import FolderChosen
from kymflow.gui_v2.pages.home_page import HomePage

logger = get_logger(__name__)

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

context = AppContext()
bus = EventBus(BusConfig(trace=True))

# gpt 20260106: ensure we only auto-emit once per process
_BOOTSTRAPPED = False


@ui.page("/")
def home() -> None:
    """Home route for v2 GUI."""
    global _BOOTSTRAPPED

    ui.page_title("KymFlow")
    inject_global_styles()

    # IMPORTANT: Instantiate HomePage FIRST so controllers subscribe to the bus.
    page = HomePage(context, bus)

    # DEV: mimic a user folder selection (emit after controllers exist)
    if USE_DEV_FOLDER and not _BOOTSTRAPPED:
        if DEV_FOLDER.exists():
            logger.info("DEV bootstrap: emitting FolderChosen(%s)", DEV_FOLDER)
            bus.emit(FolderChosen(folder=str(DEV_FOLDER)))
        else:
            logger.warning("DEV_FOLDER does not exist: %s", DEV_FOLDER)
        _BOOTSTRAPPED = True

    page.render(page_title="KymFlow")


def main(*, reload: bool | None = None, native: bool | None = None) -> None:
    """Start the KymFlow v2 GUI application."""
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
    main()