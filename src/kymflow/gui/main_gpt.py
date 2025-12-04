# see: https://stackoverflow.com/questions/63871662/python-multiprocessing-freeze-support-error
from multiprocessing import freeze_support  # noqa

freeze_support()  # noqa

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Callable

from nicegui import ui, app

from kymflow.gui.config import DEFAULT_DATA_DIR, DEFAULT_PORT, STORAGE_SECRET
from kymflow.gui.frontend.layout import (
    create_about_page,
    create_batch_page,
    create_main_page,
)

from kymflow.core.utils.logging import get_logger, setup_logging
from kymflow.gui import _getVersionInfo

# ---------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------

setup_logging(
    level="INFO",
    log_file=Path.home() / ".kymflow" / "kymflow.log",
)

logger = get_logger(__name__)
logger.warning("=== kymflow_gui.main imported ===")


# ---------------------------------------------------------------------
# Shared GUI state
# ---------------------------------------------------------------------

@dataclass
class KymflowState:
    """Shared GUI state for a *single user*.

    This is intentionally minimal here; you can extend it with:
        - current_folder: Path
        - selected_file: Path | None
        - ROI sets, analysis params, etc.
    """
    data_dir: Path = DEFAULT_DATA_DIR
    current_folder: Optional[Path] = None
    selected_file: Optional[Path] = None


def get_state() -> KymflowState:
    """Return per-user GUI state, stored in NiceGUI's user storage.

    This gives each browser/client its own state while keeping
    the code simple and centralised.
    """
    if "kymflow_state" not in app.storage.user:
        logger.info("Initializing new KymflowState for user")
        app.storage.user["kymflow_state"] = KymflowState()
    return app.storage.user["kymflow_state"]


# ---------------------------------------------------------------------
# Layout helper (common header + navigation)
# ---------------------------------------------------------------------

def with_main_layout(
    page_title: str,
    content_builder: Callable[[KymflowState], None],
) -> None:
    """Build the common layout (header + nav) and insert page content.

    Each @ui.page just calls this to avoid duplicating header/nav logic.
    """
    ui.page_title(page_title)

    state = get_state()

    # Header with navigation
    with ui.header().classes("items-center justify-between px-4"):
        ui.label("KymFlow").classes("text-xl font-bold")
        with ui.row().classes("gap-4"):
            ui.link("Main", "/")
            ui.link("Batch", "/batch")
            ui.link("About", "/about")

    # Main page content
    with ui.column().classes("p-4 gap-4"):
        content_builder(state)


# ---------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------

def main(*, reload: bool | None = None, native: bool | None = None) -> None:
    """Start the NiceGUI app.

    reload: override auto-reload. Defaults to on for CLI/dev, off when frozen/packaged.
    native: override native mode. Defaults to False, or from KYMFLOW_GUI_NATIVE env var.
    """
    is_frozen = getattr(sys, "frozen", False)
    default_reload = not is_frozen and os.getenv("KYMFLOW_GUI_RELOAD", "1") == "1"
    reload = default_reload if reload is None else reload

    default_native = os.getenv("KYMFLOW_GUI_NATIVE", "0") == "1"
    native = default_native if native is None else native

    logger.info(f"is_frozen: {is_frozen}")
    logger.info(f"default_reload: {default_reload}")
    logger.info(f"reload: {reload}")
    logger.info(f"native: {native}")
    logger.info(f"DEFAULT_DATA_DIR: {DEFAULT_DATA_DIR}")
    logger.info(f"DEFAULT_PORT: {DEFAULT_PORT}")

    # You can compute this once up front instead of inside the about page:
    version_info = _getVersionInfo()
    logger.info("versionInfo:")
    from pprint import pprint
    pprint(version_info)

    # ------------------------------
    # Routes
    # ------------------------------

    @ui.page("/")
    def index() -> None:
        """Main page (single trace / interactive)."""
        def build(state: KymflowState) -> None:
            # Suggestion: change create_main_page signature to accept `state`
            # so it can read/write data_dir, current_folder, selected_file, etc.
            create_main_page(state)

        with_main_layout("KymFlow - Main", build)

    @ui.page("/batch")
    def batch() -> None:
        """Batch processing page."""
        def build(state: KymflowState) -> None:
            # Likewise, let batch page work off shared state
            create_batch_page(state)

        with_main_layout("KymFlow - Batch", build)

    @ui.page("/about")
    def about() -> None:
        """About / version information."""
        def build(_: KymflowState) -> None:
            # About usually doesn't need state, but passing version_info
            # is nicer than recomputing it.
            create_about_page(version_info)

        with_main_layout("KymFlow - About", build)

    ui.run(
        port=DEFAULT_PORT,
        reload=reload,
        native=native,
        storage_secret=STORAGE_SECRET,
    )


if __name__ in {"__main__", "__mp_main__"}:
    logger.warning(f"__name__: {__name__}")
    main()
