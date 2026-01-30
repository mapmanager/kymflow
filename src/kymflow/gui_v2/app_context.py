"""Application context singleton for shared state across pages.

This module provides a singleton AppContext that manages shared state
across all pages in the KymFlow GUI. Since sub_pages creates a SPA (single
page application), state naturally persists across navigation without page reloads.
"""

from __future__ import annotations

import multiprocessing as mp
import os
from pathlib import Path
from typing import Optional

from nicegui import ui, app

from kymflow.gui_v2.state import AppState
from kymflow.core.state import TaskState
from kymflow.core.plotting.theme import ThemeMode
from kymflow.core.utils.logging import get_logger
from kymflow.core.user_config import UserConfig

logger = get_logger(__name__)

# Storage key for theme persistence across page navigation
# Using app.storage.user (not browser) because it can be written during callbacks
THEME_STORAGE_KEY = "kymflow_dark_mode"


class AppContext:
    """Singleton managing shared application state across all pages.
    
    In a sub_pages SPA architecture, this context persists for the entire
    session. Pages access shared AppState, TaskState, and theme through
    this singleton.
    
    Attributes:
        app_state: Shared AppState instance for file management and selection
        user_config: UserConfig instance for persistent user preferences
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
        
        # CRITICAL: Do NOT initialize GUI state in worker processes
        # Workers will re-import this module during spawn, and we must not create GUI objects
        current_process = mp.current_process()
        is_main_process = current_process.name == "MainProcess"
        
        if not is_main_process:
            logger.debug(f"Skipping AppContext initialization in worker process: {current_process.name}")
            # Set initialized to True to prevent re-initialization attempts
            self._initialized = True
            # Create minimal dummy attributes to avoid AttributeError
            self.app_state = None
            self.user_config = None
            self.home_task = None
            self.batch_task = None
            self.batch_overall_task = None
            self.default_folder = Path.home() / "data"
            return
            
        logger.info("Initializing AppContext singleton")
        
        # Shared state instances
        self.app_state = AppState()
        user_config_path = os.getenv("KYMFLOW_USER_CONFIG_PATH")
        if user_config_path:
            self.user_config = UserConfig.load(config_path=Path(user_config_path))
        else:
            self.user_config = UserConfig.load()
        logger.info(f"User config loaded from: {self.user_config.path}")
        self.home_task = TaskState()
        self.batch_task = TaskState()
        self.batch_overall_task = TaskState()
        
        # Default folder
        self.default_folder: Path = Path.home() / "data"  # Will be set by app.py
        
        self._initialized = True
        logger.info("AppContext initialized successfully")
    
    def init_dark_mode_for_page(self):
        """Initialize dark mode for current page.
        
        Creates fresh ui.dark_mode() and syncs with stored preference.
        Must be called on each page load in multi-page architecture.
        
        Returns:
            Dark mode controller for this page
        """
        dark_mode = ui.dark_mode()
        
        # Restore from user storage (default: True = dark mode)
        # Using app.storage.user (not browser) because it can be written during callbacks
        stored_value = app.storage.user.get(THEME_STORAGE_KEY, True)
        dark_mode.value = stored_value
        
        # Sync with AppState (single source of truth)
        mode = ThemeMode.DARK if stored_value else ThemeMode.LIGHT
        self.app_state.set_theme(mode)
        
        # logger.debug(f"Dark mode initialized: {stored_value}")
        return dark_mode
    
    def set_default_folder(self, folder: Path) -> None:
        """Set the default data folder."""
        self.default_folder = folder.expanduser()
        # logger.debug(f"Default folder set to: {self.default_folder}")
    
    def toggle_theme(self, dark_mode) -> None:
        """Toggle theme and persist to storage.
        
        Args:
            dark_mode: Dark mode controller for current page
        """
        # Toggle UI
        dark_mode.value = not dark_mode.value
        
        # Persist to user storage (can be written during callbacks, unlike browser storage)
        app.storage.user[THEME_STORAGE_KEY] = dark_mode.value
        
        # Update AppState (triggers callbacks to plotting components)
        mode = ThemeMode.DARK if dark_mode.value else ThemeMode.LIGHT
        self.app_state.set_theme(mode)
        
        # logger.debug(f"Theme toggled: {mode}")
    
    def reset(self) -> None:
        """Reset the context (useful for testing or logout)."""
        logger.info("Resetting AppContext")
        self.app_state = AppState()
        self.user_config = UserConfig.load()
        self.home_task = TaskState()
        self.batch_task = TaskState()
        self.batch_overall_task = TaskState()
        
    @classmethod
    def get_instance(cls) -> AppContext:
        """Get the singleton instance (alternative to using __new__)."""
        return cls()

