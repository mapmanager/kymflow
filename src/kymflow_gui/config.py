from __future__ import annotations

from pathlib import Path

from kymflow_core.utils.logging import setup_logging

APP_NAME = "KymFlow GUI"
# DEFAULT_DATA_DIR = Path.home() / "kymflow-data"
DEFAULT_DATA_DIR = Path("/Users/cudmore/Dropbox/data/declan/data/20221102")
DEFAULT_PORT = 8080


def init_config() -> None:
    """Initialize shared services like logging."""
    setup_logging(
        level="INFO",
        log_file=Path.home() / ".kymflow" / "kymflow.log",
    )
