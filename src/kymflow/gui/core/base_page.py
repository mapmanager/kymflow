"""Base page class for all KymFlow GUI pages."""

from __future__ import annotations

from abc import ABC, abstractmethod

from nicegui import ui

from .app_context import AppContext
from .navigation import build_header, inject_global_styles
from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)


class BasePage(ABC):
    """Abstract base class for all pages in the KymFlow GUI.
    
    Provides common functionality including header, navigation, and
    access to shared application state through AppContext.
    
    Subclasses must implement:
        - render_content(): Page-specific content rendering
    
    Attributes:
        context: Shared AppContext singleton
        page_name: Name of this page ("home", "batch", "about")
    """
    
    def __init__(self, context: AppContext, page_name: str):
        """Initialize the base page.
        
        Args:
            context: Application context with shared state
            page_name: Name of this page for navigation highlighting
        """
        self.context = context
        self.page_name = page_name
        logger.debug(f"Initializing {page_name} page")
    
    def render(self) -> None:
        """Render the page content.
        
        In sub_pages SPA mode, headers are rendered at the top level
        (outside sub_pages), so this method only renders page-specific content.
        """
        # Page-specific content rendered by subclass
        with ui.column().classes("w-full p-4 gap-4"):
            self.render_content()
    
    @abstractmethod
    def render_content(self) -> None:
        """Render page-specific content.
        
        This method must be implemented by subclasses to provide
        the unique content for each page.
        """
        pass
    
    def on_mount(self) -> None:
        """Optional lifecycle hook called when page is displayed.
        
        Override in subclasses if you need to:
        - Load data
        - Restore state
        - Start background tasks
        - Initialize connections
        """
        pass
    
    def on_unmount(self) -> None:
        """Optional lifecycle hook called when leaving page.
        
        Override in subclasses if you need to:
        - Save state
        - Clean up resources
        - Cancel tasks
        - Close connections
        """
        pass

