from __future__ import annotations
from pathlib import Path

from nicegui import native

APP_NAME = "KymFlow"
# DEFAULT_DATA_DIR = Path.home() / "kymflow-data"
# DEFAULT_DATA_DIR = Path("/Users/cudmore/Dropbox/data/declan/data/20221102")
# DEFAULT_DATA_DIR = Path("/Users/cudmore/Sites/kymflow_outer/kymflow/tests/data")
DEFAULT_DATA_DIR = Path("/Users/cudmore/Dropbox/data/declan/2026/data/20251204")
DEFAULT_PORT = native.find_open_port()  # 8080
STORAGE_SECRET = "kymflow-session-secret"  # Secret key for browser session storage
