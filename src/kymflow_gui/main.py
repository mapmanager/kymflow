from pathlib import Path

from nicegui import ui

from .config import DEFAULT_DATA_DIR, DEFAULT_PORT
from .frontend.layout import create_main_page

# IMPORTANT: configure logging at module import, so it runs in the uvicorn worker too
from kymflow_core.utils.logging import get_logger, setup_logging

setup_logging(
    level="INFO",
    log_file=Path.home() / ".kymflow" / "kymflow.log",
)

logger = get_logger(__name__)
logger.info("kymflow_gui.main imported")


def main() -> None:
    @ui.page("/")
    def index() -> None:
        create_main_page(DEFAULT_DATA_DIR)

    ui.run(port=DEFAULT_PORT, reload=True)


if __name__ in {"__main__", "__mp_main__"}:
    main()
