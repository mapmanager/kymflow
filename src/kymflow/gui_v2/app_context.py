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

from nicewidgets.utils import setUpGuiDefaults

from kymflow.gui_v2.runtime_mode import is_native_mode
from kymflow.gui_v2.state import AppState
from kymflow.core.state import TaskState
from kymflow.core.plotting.theme import ThemeMode
from kymflow.core.utils.logging import get_logger
from kymflow.core.user_config import UserConfig
from kymflow.gui_v2.app_config import AppConfig
from kymflow.gui_v2.native_ui_gate import NativeUiGate
# from kymflow.gui_v2._pywebview import install_shutdown_handlers

logger = get_logger(__name__)

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
        - native_mode: from :func:`~kymflow.gui_v2.runtime_mode.is_native_mode`
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
            return default

        native_mode = is_native_mode()
        is_remote = _env_bool("KYMFLOW_REMOTE", False)
        has_file_system_access = native_mode or not is_remote
        
        return cls(
            native_mode=native_mode,
            is_remote=is_remote,
            has_file_system_access=has_file_system_access,
        )

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
        suppress_velocity_event_cache_sync_on_detect_events: When True,
            :class:`~kymflow.gui_v2.controllers.kym_event_cache_sync_controller.KymEventCacheSyncController`
            ignores :class:`~kymflow.gui_v2.events.DetectEvents` (state) so batch runs do not
            update the in-memory velocity-event DB or emit ``VelocityEventDbUpdated`` per file.
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
            self.suppress_velocity_event_cache_sync_on_detect_events = False
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
            f"  Runtime environment: native={self.runtime_env.native_mode}, "
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
        logger.info(f"  User config loaded from: {self.user_config.path}")
        
        # Load app config
        app_config_path = os.getenv("KYMFLOW_APP_CONFIG_PATH")
        if app_config_path:
            self.app_config = AppConfig.load(config_path=Path(app_config_path))
        else:
            self.app_config = AppConfig.load()
        logger.info(f"  App config loaded from: {self.app_config.path}")
        
        app.native.on('resized', self._native_resize)
        app.native.on('moved', self._native_moved)

        # Initialize app_state.folder_depth from app_config
        self.app_state.folder_depth = self.app_config.data.folder_depth
        
        #
        # configure default classes (after app_config is loaded)
        text_size = self.app_config.get_attribute("text_size")
        setUpGuiDefaults(text_size)

        self.home_task = TaskState()
        # Dedicated TaskState for folder / CSV loads (task_type='load')
        self.load_task = TaskState()
        self.batch_task = TaskState()
        self.batch_overall_task = TaskState()
        self.suppress_velocity_event_cache_sync_on_detect_events = False

        # Default folder (used as fallback for file dialogs)
        self.default_folder: Path = Path.home()
        
        # abb 20260207 while adding global lock for pywebview. not sure the correct location ???
        self.native_ui_gate = NativeUiGate()
        
        self._install_shutdown_handlers()

        self._initialized = True
        logger.info("--> Done: AppContext initialized successfully")
    
    def _install_shutdown_handlers(self) -> None:
        """Register app shutdown handlers for GUI v2.
        
        Only installs handlers when running in native mode (native=True).
        In browser mode, configs are saved via other mechanisms.
        """
        native = getattr(app, "native", None)
        if native is None:
            logger.debug("skipping (not native mode)")
            return
        
        # logger.info("installing (native mode detected)")

        async def _persist_on_shutdown() -> None:
            """Persist user and app config on shutdown without touching native window APIs."""
            self._save_all_configs()

        app.on_shutdown(_persist_on_shutdown)


    # abb 20260323 pywebview native save png (clipboard)
    def _native_resize(self, e):# we also can do this:
        """
        NativeEventArguments(type='resized', args={'width': 1221.0, 'height': 1538.0})
        """
        args = e.args
        
        # logger.info(f"  args is: {args}")

        # cfg = AppConfig.load()
        # logger.info(f"App config loaded from: {cfg.path}")

        x, y, w, h = self.app_config.get_window_rect()

        # logger.info(f"  old window size: w:{w}, h:{h}")
        w = args['width']
        h = args['height']  
        # logger.info(f"  new window size: w:{w}, h:{h}")

        self.app_config.set_window_rect(x, y, w, h)

    def _native_moved(self, e):
        """
        NativeEventArguments(type='moved', args={'x': 2365.0, 'y': 545.0})
        """
        args = e.args

        # logger.info(f"  args is: {args}")

        # cfg = AppConfig.load()
        # logger.info(f"App config loaded from: {cfg.path}")

        x, y, w, h = self.app_config.get_window_rect()

        # logger.info(f"  old window position: x:{x}, y:{y}")
        x = args['x']
        y = args['y']  
        # logger.info(f"  new window position: x:{x}, y:{y}")

        self.app_config.set_window_rect(x, y, w, h)

    def _save_all_configs(self) -> bool:
        """Save both user_config and app_config to disk.
        
        Single source of truth for persisting all application configs.
        Used by both shutdown handler and manual save button.
        
        Args:
            context: AppContext instance containing user_config and app_config.
        
        Returns:
            True if both configs saved successfully, False otherwise.
        """
        success = True
        
        cfg = getattr(self, "user_config", None)
        if cfg is not None:
            try:
                cfg.save()
                logger.info("user_config saved successfully")
            except Exception:
                logger.exception("Failed to save user_config")
                success = False

        app_cfg = getattr(self, "app_config", None)
        if app_cfg is not None:
            try:
                app_cfg.save()
                logger.info("app_config saved successfully")
            except Exception:
                logger.exception("Failed to save app_config")
                success = False
        
        return success

    def init_dark_mode_for_page(self):
        """Initialize dark mode for current page.
        
        Creates fresh ui.dark_mode() and syncs with stored preference.
        Must be called on each page load in multi-page architecture.
        
        Returns:
            Dark mode controller for this page
        """
        dark_mode = ui.dark_mode()

        if self.app_config is None:
            dark_mode.value = True
            if self.app_state is not None:
                self.app_state.set_theme(ThemeMode.DARK)
            return dark_mode

        stored_value = self.app_config.get_kymflow_dark_mode()
        dark_mode.value = stored_value

        # Sync with AppState (single source of truth)
        mode = ThemeMode.DARK if stored_value else ThemeMode.LIGHT
        self.app_state.set_theme(mode)

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
        dark_mode.value = not dark_mode.value

        if self.app_config is not None:
            self.app_config.set_kymflow_dark_mode(dark_mode.value)
            self.app_config.save()

        # Update AppState (triggers callbacks to plotting components)
        mode = ThemeMode.DARK if dark_mode.value else ThemeMode.LIGHT
        self.app_state.set_theme(mode)
    
    def reset(self) -> None:
        """Reset the context (useful for testing or logout)."""
        logger.info("Resetting AppContext")
        self.app_state = AppState()
        self.user_config = UserConfig.load()
        self.app_config = AppConfig.load()
        self.home_task = TaskState()
        self.load_task = TaskState()
        self.batch_task = TaskState()
        self.batch_overall_task = TaskState()
        self.suppress_velocity_event_cache_sync_on_detect_events = False

    @classmethod
    def get_instance(cls) -> AppContext:
        """Get the singleton instance (alternative to using __new__)."""
        return cls()

