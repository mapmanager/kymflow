"""Modern KymFlow GUI application with clean architecture.

This module provides a traditional multi-page architecture with:
- Shared state that persists across page navigation (process-level singleton)
- Common layout helper to eliminate code duplication
- Clean separation between layout and content
- Reactive bindings for automatic UI updates

Run with:
    uv run python -m kymflow.gui.app
"""

from multiprocessing import freeze_support
import os
import sys
from pathlib import Path

from nicegui import ui

from kymflow.gui.config import DEFAULT_DATA_DIR, DEFAULT_PORT, STORAGE_SECRET
from kymflow.gui.core.app_context import AppContext
from kymflow.gui.core.navigation import build_header, inject_global_styles
from kymflow.core.utils.logging import setup_logging, get_logger

# Import page content builders
from kymflow.gui.pages.home_page import build_home_content
from kymflow.gui.pages.batch_page import build_batch_content
from kymflow.gui.pages.about_page import build_about_content

# Configure logging at module import (runs in uvicorn worker)
setup_logging(
    level="INFO",
    log_file=Path.home() / ".kymflow" / "logs" / "kymflow.log",
)

logger = get_logger(__name__)
logger.info("=== kymflow.gui.app imported (clean architecture) ===")

# Initialize shared application context (singleton) at module level
context = AppContext()
context.set_default_folder(DEFAULT_DATA_DIR)


def with_main_layout(page_title: str, page_name: str, content_builder) -> None:
    """Build the common layout (header + navigation + content) and call content_builder.
    
    This helper eliminates code duplication across pages while keeping each
    page function tiny and focused.
    
    Args:
        page_title: HTML page title
        page_name: Page name for navigation highlighting ("home", "batch", "about")
        content_builder: Function that builds page-specific content
    """
    ui.page_title(page_title)
    inject_global_styles()
    build_header(context)
    
    # Main content area
    with ui.column().classes("w-full p-4 gap-4"):
        content_builder(context)


# ============================================================
# Page Routes
# ============================================================

@ui.page("/")
def page_home() -> None:
    """Home page route."""
    with_main_layout("KymFlow", "home", build_home_content)


@ui.page("/batch")
def page_batch() -> None:
    """Batch analysis page route."""
    with_main_layout("KymFlow - Batch Analysis", "batch", build_batch_content)


@ui.page("/about")
def page_about() -> None:
    """About page route."""
    with_main_layout("KymFlow - About", "about", build_about_content)


# ============================================================
# Main Entry Point
# ============================================================

def main(*, reload: bool | None = None, native: bool | None = None) -> None:
    """Start the KymFlow GUI application.
    
    Args:
        reload: Override auto-reload. Defaults to on for CLI/dev, off when frozen.
        native: Override native mode. Defaults to False or from KYMFLOW_GUI_NATIVE env var.
    """
    is_frozen = getattr(sys, "frozen", False)
    default_reload = not is_frozen and os.getenv("KYMFLOW_GUI_RELOAD", "1") == "1"
    reload = default_reload if reload is None else reload
    
    default_native = os.getenv("KYMFLOW_GUI_NATIVE", "0") == "1"
    native = default_native if native is None else native
    
    logger.info(f"Starting KymFlow GUI: port={DEFAULT_PORT}, reload={reload}, native={native}")
    
    ui.run(
        port=DEFAULT_PORT,
        reload=reload,
        native=native,
        storage_secret=STORAGE_SECRET,
    )


if __name__ in {"__main__", "__mp_main__"}:
    freeze_support()
    logger.info(f"__name__: {__name__}")
    main()
