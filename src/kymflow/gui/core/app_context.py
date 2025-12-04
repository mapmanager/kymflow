"""Application context singleton for shared state across pages.

This module provides a singleton AppContext that manages shared state
across all pages in the KymFlow GUI. Since sub_pages creates a SPA (single
page application), state naturally persists across navigation without page reloads.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from nicegui import ui

from kymflow.core.state_v2 import AppState, TaskState
from kymflow.core.enums import ThemeMode
from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)


class AppContext:
    """Singleton managing shared application state across all pages.
    
    In a sub_pages SPA architecture, this context persists for the entire
    session. Pages access shared AppState, TaskState, and theme through
    this singleton.
    
    Attributes:
        app_state: Shared AppState instance for file management and selection
        home_task: TaskState for home page analysis tasks
        batch_task: TaskState for batch analysis tasks
        batch_overall_task: TaskState for overall batch progress
        dark_mode: NiceGUI dark mode controller
    """
    
    _instance: Optional[AppContext] = None
    
    def __new__(cls) -> AppContext:
        """Ensure only one instance exists (singleton pattern)."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self) -> None:
        """Initialize the context (only runs once due to singleton)."""
        if self._initialized:
            return
            
        logger.info("Initializing AppContext singleton")
        
        # Shared state instances
        self.app_state = AppState()
        self.home_task = TaskState()
        self.batch_task = TaskState()
        self.batch_overall_task = TaskState()
        
        # Theme management (delayed until first page renders)
        self._dark_mode = None
        self._theme_initialized = False
        
        # Default folder
        self.default_folder: Path = Path.home() / "data"  # Will be set by app.py
        
        self._initialized = True
        logger.info("AppContext initialized successfully")
    
    @property
    def dark_mode(self):
        """Get or create the dark mode controller (lazy initialization).
        
        Dark mode is created on first access to avoid creating UI elements
        before ui.run() is called (required for sub_pages pattern).
        """
        if self._dark_mode is None:
            self._dark_mode = ui.dark_mode()
            if not self._theme_initialized:
                self._dark_mode.value = True  # Default to dark mode
                self.app_state.set_theme(ThemeMode.DARK)
                self._theme_initialized = True
                logger.debug("Dark mode initialized (lazy)")
        return self._dark_mode
    
    def set_default_folder(self, folder: Path) -> None:
        """Set the default data folder."""
        self.default_folder = folder.expanduser()
        logger.debug(f"Default folder set to: {self.default_folder}")
    
    def toggle_theme(self) -> None:
        """Toggle between dark and light mode."""
        self.dark_mode.value = not self.dark_mode.value
        mode = ThemeMode.DARK if self.dark_mode.value else ThemeMode.LIGHT
        self.app_state.set_theme(mode)
        logger.debug(f"Theme toggled to: {mode}")
    
    def reset(self) -> None:
        """Reset the context (useful for testing or logout)."""
        logger.info("Resetting AppContext")
        self.app_state = AppState()
        self.home_task = TaskState()
        self.batch_task = TaskState()
        self.batch_overall_task = TaskState()
        
    @classmethod
    def get_instance(cls) -> AppContext:
        """Get the singleton instance (alternative to using __new__)."""
        return cls()

