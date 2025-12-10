"""GUI-specific state containers with callback registries (psygnal-free).

This module provides AppState and ImageDisplayParams for managing GUI application
state, using callback registries instead of psygnal signals to avoid lifecycle
issues with NiceGUI component cleanup.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

from kymflow.core.kym_file import KymFile
from kymflow.core.repository import FolderScanResult, scan_folder
from kymflow.gui.events import ImageDisplayOrigin, SelectionOrigin
from kymflow.core.plotting.theme import ThemeMode
from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ImageDisplayParams:
    """Event payload for image display parameter changes."""
    colorscale: str
    zmin: Optional[int] = None
    zmax: Optional[int] = None
    origin: ImageDisplayOrigin = ImageDisplayOrigin.OTHER

    def __str__(self) -> str:
        return f"ImageDisplayParams(colorscale: {self.colorscale}, zmin: {self.zmin}, zmax: {self.zmax}, origin: {self.origin})"


# Type aliases for callbacks
SelectionChangedHandler = Callable[[Optional[KymFile], Optional[SelectionOrigin]], None]
FileListChangedHandler = Callable[[], None]
MetadataChangedHandler = Callable[[KymFile], None]
ThemeChangedHandler = Callable[[ThemeMode], None]
ImageDisplayChangedHandler = Callable[[ImageDisplayParams], None]


class AppState:
    """Shared application state for the NiceGUI GUI.
    
    Uses callback registries instead of psygnal EventedModel.
    Callbacks are registered/cleaned up with widget lifecycle.
    """
    
    def __init__(self):
        self.folder: Optional[Path] = None
        self.files: List[KymFile] = []
        self.selected_file: Optional[KymFile] = None
        self.selected_roi_id: Optional[int] = None  # Currently selected ROI ID
        self.theme_mode: ThemeMode = ThemeMode.DARK
        self.folder_depth: int = 1
        
        # Callback registries (like grid_gpt.py pattern)
        self._file_list_changed_handlers: List[FileListChangedHandler] = []
        self._selection_changed_handlers: List[SelectionChangedHandler] = []
        self._metadata_changed_handlers: List[MetadataChangedHandler] = []
        self._theme_changed_handlers: List[ThemeChangedHandler] = []
        self._image_display_changed_handlers: List[ImageDisplayChangedHandler] = []
        self._roi_selection_changed_handlers: List[Callable[[Optional[int]], None]] = []
    
    # Registration methods
    def on_file_list_changed(self, handler: FileListChangedHandler) -> None:
        """Register callback for file list updates."""
        self._file_list_changed_handlers.append(handler)
    
    def on_selection_changed(self, handler: SelectionChangedHandler) -> None:
        """Register callback for selection changes."""
        self._selection_changed_handlers.append(handler)
    
    def on_metadata_changed(self, handler: MetadataChangedHandler) -> None:
        """Register callback for metadata updates."""
        self._metadata_changed_handlers.append(handler)
    
    def on_theme_changed(self, handler: ThemeChangedHandler) -> None:
        """Register callback for theme changes."""
        self._theme_changed_handlers.append(handler)
    
    def on_image_display_changed(self, handler: ImageDisplayChangedHandler) -> None:
        """Register callback for image display parameter changes."""
        self._image_display_changed_handlers.append(handler)
    
    def on_roi_selection_changed(self, handler: Callable[[Optional[int]], None]) -> None:
        """Register callback for ROI selection changes."""
        self._roi_selection_changed_handlers.append(handler)
    
    # State mutation methods that trigger callbacks
    def load_folder(self, folder: Path, depth: Optional[int] = None) -> FolderScanResult:
        """Scan folder for kymograph files and update app state."""
        if depth is None:
            depth = self.folder_depth
        result = scan_folder(folder, depth=depth)
        self.folder = result.folder
        self.files = result.files
        
        logger.info("load_folder: calling file_list_changed handlers")
        for handler in list(self._file_list_changed_handlers):
            try:
                handler()
            except Exception:
                logger.exception("Error in file_list_changed handler")
        
        if self.files:
            self.select_file(self.files[0])
        else:
            self.select_file(None)
        return result
    
    def select_file(
        self,
        kym_file: Optional[KymFile],
        origin: Optional[SelectionOrigin] = None,
    ) -> None:
        """Select a file and notify handlers."""
        self.selected_file = kym_file
        
        # Initialize selected_roi_id to first ROI if available
        if kym_file is not None and kym_file.kymanalysis is not None:
            all_rois = kym_file.kymanalysis.get_all_rois()
            if all_rois:
                self.selected_roi_id = all_rois[0].roi_id
            else:
                self.selected_roi_id = None
        else:
            self.selected_roi_id = None
        
        logger.info(f"select_file: calling selection_changed handlers for {kym_file}, selected_roi_id={self.selected_roi_id}")
        for handler in list(self._selection_changed_handlers):
            try:
                handler(kym_file, origin)
            except Exception:
                logger.exception("Error in selection_changed handler")
    
    def refresh_file_rows(self) -> None:
        """Refresh file list (reloads current folder)."""
        if self.folder:
            self.load_folder(self.folder, depth=self.folder_depth)
    
    def set_theme(self, mode: ThemeMode) -> None:
        """Set theme mode and notify handlers."""
        self.theme_mode = mode
        for handler in list(self._theme_changed_handlers):
            try:
                handler(mode)
            except Exception:
                logger.exception("Error in theme_changed handler")
    
    def set_image_display(self, params: ImageDisplayParams) -> None:
        """Set image display parameters and notify handlers."""
        for handler in list(self._image_display_changed_handlers):
            try:
                handler(params)
            except Exception:
                logger.exception("Error in image_display_changed handler")
    
    def update_metadata(self, kym_file: KymFile) -> None:
        """Notify handlers that metadata was updated."""
        for handler in list(self._metadata_changed_handlers):
            try:
                handler(kym_file)
            except Exception:
                logger.exception("Error in metadata_changed handler")
    
    def select_roi(self, roi_id: Optional[int]) -> None:
        """Select an ROI and notify handlers."""
        self.selected_roi_id = roi_id
        logger.info(f"select_roi: calling roi_selection_changed handlers for roi_id={roi_id}")
        for handler in list(self._roi_selection_changed_handlers):
            try:
                handler(roi_id)
            except Exception:
                logger.exception("Error in roi_selection_changed handler")

