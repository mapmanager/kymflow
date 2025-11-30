# see: https://stackoverflow.com/questions/63871662/python-multiprocessing-freeze-support-error
# Add the following snippet before anything else in your main app's file,
# to prevent new processes from being spawned in an endless loop:
from multiprocessing import freeze_support  # noqa

freeze_support()  # noqa

import os
import sys
from pathlib import Path

from nicegui import ui

from kymflow_gui.config import DEFAULT_DATA_DIR, DEFAULT_PORT, STORAGE_SECRET
from kymflow_gui.frontend.layout import (
    create_about_page,
    create_batch_page,
    create_main_page,
)

# IMPORTANT: configure logging at module import, so it runs in the uvicorn worker too
from kymflow_core.utils.logging import get_logger, setup_logging
from kymflow_gui import _getVersionInfo

setup_logging(
    level="INFO",
    log_file=Path.home() / ".kymflow" / "kymflow.log",
)

logger = get_logger(__name__)
logger.warning("=== kymflow_gui.main imported")


def main(*, reload: bool | None = None) -> None:
    """Start the NiceGUI app.

    reload: override auto-reload. Defaults to on for CLI/dev, off when frozen/packaged.
    """
    is_frozen = getattr(sys, "frozen", False)
    default_reload = not is_frozen and os.getenv("KYMFLOW_GUI_RELOAD", "1") == "1"
    reload = default_reload if reload is None else reload

    logger.info(f"is_frozen: {is_frozen}")
    logger.info(f"default_reload: {default_reload}")
    logger.info(f"reload: {reload}")

    logger.info(f"DEFAULT_DATA_DIR: {DEFAULT_DATA_DIR}")
    logger.info(f"DEFAULT_PORT: {DEFAULT_PORT}")

    versionInfo = _getVersionInfo()
    logger.info("versionInfo:")
    from pprint import pprint

    pprint(versionInfo)

    @ui.page("/")
    def index() -> None:
        create_main_page(DEFAULT_DATA_DIR)

    @ui.page("/batch")
    def batch() -> None:
        create_batch_page(DEFAULT_DATA_DIR)

    @ui.page("/about")
    def about() -> None:
        create_about_page(_getVersionInfo())

    _native = False  # when True, runs in native window (Mac only)
    # reload = False
    ui.run(
        port=DEFAULT_PORT, reload=reload, native=_native, storage_secret=STORAGE_SECRET
    )


if __name__ in {"__main__", "__mp_main__"}:
    logger.warning(f"__name__: {__name__}")
    main()

    # from pprint import pprint
    # versionInfo = _getVersionInfo()
    # logger.info(f"versionInfo:")
    # pprint(versionInfo)
