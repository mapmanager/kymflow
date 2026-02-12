"""Application context singleton for shared state across pages.

This module provides a singleton AppContext that manages shared state
across all pages in the KymFlow GUI. Since sub_pages creates a SPA (single
page application), state naturally persists across navigation without page reloads.
"""

from __future__ import annotations

import multiprocessing as mp
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from nicegui import ui, app

from kymflow.gui_v2.state import AppState
from kymflow.core.state import TaskState
from kymflow.core.plotting.theme import ThemeMode
from kymflow.core.utils.logging import get_logger
from kymflow.core.user_config import UserConfig
from kymflow.gui_v2.app_config import AppConfig
from kymflow.gui_v2.native_ui_gate import NativeUiGate

logger = get_logger(__name__)

# Storage key for theme persistence across page navigation
# Using app.storage.user (not browser) because it can be written during callbacks
THEME_STORAGE_KEY = "kymflow_dark_mode"


@dataclass
class RuntimeEnvironment:
    """Runtime environment detection for UI feature gating.
    
    Attributes:
        native_mode: True if running in native mode (pywebview).
        is_remote: True if running in remote deployment (Docker/cloud).
        has_file_system_access: True if file dialogs and save operations are available.
    """
    native_mode: bool
    is_remote: bool
    has_file_system_access: bool
    
    @classmethod
    def detect(cls) -> "RuntimeEnvironment":
        """Detect runtime environment from env vars.
        
        Logic:
        - native_mode: from KYMFLOW_GUI_NATIVE (default: True)
        - is_remote: from KYMFLOW_REMOTE (default: False)
        - has_file_system_access: True if native_mode OR not is_remote
        """
        def _env_bool(name: str, default: bool) -> bool:
            raw = os.getenv(name)
            if raw is None:
                return default
            v = raw.strip().lower()
            if v in {"1", "true", "yes", "on"}:
                return True
            if v in {"0", "false", "no", "off"}:
                return False
            # Invalid value - fall back to default
            return default
        
        native_mode = _env_bool("KYMFLOW_GUI_NATIVE", True)
        is_remote = _env_bool("KYMFLOW_REMOTE", False)
        has_file_system_access = native_mode or not is_remote
        
        return cls(
            native_mode=native_mode,
            is_remote=is_remote,
            has_file_system_access=has_file_system_access,
        )


def _setUpGuiDefaults(app_config: AppConfig | None = None):
    """Set up default classes and props for all ui elements.
    
    Args:
        app_config: AppConfig instance to get text_size from. If None, uses default.
    """
    
    logger.info('setting default_classes() and default_props()to specify style of all ui elements')
    # logger.info(f'  ui.button and ui.label ui.checkbox')
    
    # logger.debug(f'app_config is:{app_config}')

    # Get text_size from app_config, fallback to default
    if app_config is not None:
        text_size = app_config.get_attribute('text_size')
        logger.debug(f'  app_config.get_attribute("text_size") is: {text_size}')
    else:
        logger.debug('  no app_config, default text_size is "text-sm"')
        text_size = 'text-sm'
    
    # map tailwind to quasar size
    text_size_quasar = {
        "text-xs": "xs",
        "text-sm": "sm",
        "text-base": "md",
        "text-lg": "lg",
    }[text_size]

    logger.debug(f'=== using text_size:"{text_size}" text_size_quasar:{text_size_quasar}')

    ui.label.default_classes(f"{text_size} select-text")  #  select-text allows double-click selection
    ui.label.default_props("dense")
    #
    ui.button.default_classes(text_size)
    ui.button.default_props("dense")
    #
    ui.checkbox.default_classes(text_size)
    ui.checkbox.default_props(f"dense size={text_size_quasar}")
    # ui.checkbox.default_props("dense size=xs")
    # .props('size=xs')
    #
    ui.select.default_classes(text_size)
    ui.select.default_props("dense")
    #
    ui.input.default_classes(text_size)
    ui.input.default_props("dense")
    #
    ui.number.default_classes(text_size)
    ui.number.default_props("dense")
    #
    ui.expansion.default_classes(text_size)
    ui.expansion.default_props("dense")
    #
    ui.slider.default_classes(text_size)
    ui.slider.default_props("dense")
    #
    ui.linear_progress.default_classes(text_size)
    ui.linear_progress.default_props("dense")

    ui.menu.default_classes(text_size)
    ui.menu.default_props("dense")

    ui.menu_item.default_classes(text_size)
    ui.menu_item.default_props("dense")

class AppContext:
    """Singleton managing shared application state across all pages.
    
    In a sub_pages SPA architecture, this context persists for the entire
    session. Pages access shared AppState, TaskState, and theme through
    this singleton.
    
    Attributes:
        app_state: Shared AppState instance for file management and selection
        user_config: UserConfig instance for persistent user preferences
        app_config: AppConfig instance for app-wide settings
        runtime_env: RuntimeEnvironment instance for runtime detection
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
            # logger.debug(f"Skipping AppContext initialization in worker process: {current_process.name}")
            # Set initialized to True to prevent re-initialization attempts
            self._initialized = True
            # Create minimal dummy attributes to avoid AttributeError
            self.app_state = None
            self.user_config = None
            self.app_config = None
            self.home_task = None
            self.batch_task = None
            self.batch_overall_task = None
            self.default_folder = Path.home()

            # abb 20260207: always present
            self.native_ui_gate = NativeUiGate()
            
            # Detect runtime environment (safe to detect even in workers)
            self.runtime_env = RuntimeEnvironment.detect()

            return
            
        logger.info("Initializing AppContext singleton (should happen once)")
        
        # Detect runtime environment (must happen early, before other initialization)
        self.runtime_env = RuntimeEnvironment.detect()
        logger.info(
            f"Runtime environment: native={self.runtime_env.native_mode}, "
            f"remote={self.runtime_env.is_remote}, "
            f"file_access={self.runtime_env.has_file_system_access}"
        )
        
        # Shared state instances
        self.app_state = AppState()
        user_config_path = os.getenv("KYMFLOW_USER_CONFIG_PATH")
        if user_config_path:
            self.user_config = UserConfig.load(config_path=Path(user_config_path))
        else:
            self.user_config = UserConfig.load()
        logger.info(f"User config loaded from: {self.user_config.path}")
        
        # Load app config
        app_config_path = os.getenv("KYMFLOW_APP_CONFIG_PATH")
        if app_config_path:
            self.app_config = AppConfig.load(config_path=Path(app_config_path))
        else:
            self.app_config = AppConfig.load()
        logger.info(f"App config loaded from: {self.app_config.path}")
        
        # Initialize app_state.folder_depth from app_config
        self.app_state.folder_depth = self.app_config.data.folder_depth
        
        #
        # configure default classes (after app_config is loaded)
        _setUpGuiDefaults(self.app_config)

        #
        # global css styles
        # this has to be in a page function ???
        # from kymflow.gui_v2.styles import install_global_styles
        # install_global_styles()
        
        self.home_task = TaskState()
        self.batch_task = TaskState()
        self.batch_overall_task = TaskState()
        
        # Default folder (used as fallback for file dialogs)
        self.default_folder: Path = Path.home()
        
        # abb 20260207 while adding global lock for pywebview. not sure the correct location ???
        self.native_ui_gate = NativeUiGate()
        
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
        self.app_config = AppConfig.load()
        self.home_task = TaskState()
        self.batch_task = TaskState()
        self.batch_overall_task = TaskState()
        
    @classmethod
    def get_instance(cls) -> AppContext:
        """Get the singleton instance (alternative to using __new__)."""
        return cls()

