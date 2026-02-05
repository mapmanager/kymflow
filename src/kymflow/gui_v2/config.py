from __future__ import annotations
from typing import Optional

from nicegui import native

APP_NAME = "KymFlow"
DEFAULT_PORT = native.find_open_port()  # 8080
STORAGE_SECRET = "kymflow-session-secret"  # Secret key for browser session storage

# Developer-level runtime configuration
MAX_NUM_ROI: Optional[int] = None  # Maximum number of ROIs allowed per file. None = no limit, int = enforce limit
ALLOW_EDIT_ROI: bool = False  # Whether ROI editing is allowed