"""GUI-specific state containers with callback registries (psygnal-free).

This module provides AppState and ImageDisplayParams for managing GUI application
state, using callback registries instead of psygnal signals to avoid lifecycle
issues with NiceGUI component cleanup.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, List, Optional, TYPE_CHECKING

from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.core.image_loaders.acq_image_list import AcqImageList
from kymflow.gui_v2.events_legacy import ImageDisplayOrigin, SelectionOrigin
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
SelectionChangedHandler = Callable[[Optional[KymImage], Optional[SelectionOrigin]], None]
FileListChangedHandler = Callable[[], None]
MetadataChangedHandler = Callable[[KymImage], None]
ThemeChangedHandler = Callable[[ThemeMode], None]
ImageDisplayChangedHandler = Callable[[ImageDisplayParams], None]
if TYPE_CHECKING:
    from kymflow.core.analysis.velocity_events.velocity_events import VelocityEvent
    from kymflow.gui_v2.events import EventSelectionOptions


EventSelectionChangedHandler = Callable[
    [
        Optional[str],
        Optional[int],
        Optional[str],
        Optional["VelocityEvent"],
        Optional["EventSelectionOptions"],
        Optional[Any],
    ],
    None,
]


class AppState:
    """Shared application state for the NiceGUI GUI.
    
    Uses callback registries instead of psygnal EventedModel.
    Callbacks are registered/cleaned up with widget lifecycle.
    """
    
    def __init__(self):
        self.folder: Optional[Path] = None
        
        # Initialize with no folder - will be replaced when load_folder() is called
        # AcqImageList(path=None, ...) creates an empty, iterable container without scanning.
        self.files: AcqImageList[KymImage] = AcqImageList(
            path=None,
            image_cls=KymImage,
            file_extension=".tif",
            depth=1,
        )
        
        self.selected_file: Optional[KymImage] = None
        self.selected_roi_id: Optional[int] = None  # Currently selected ROI ID
        self.selected_event_id: Optional[str] = None
        self.selected_event_roi_id: Optional[int] = None
        self.selected_event_path: Optional[str] = None
        self.selected_event: Optional["VelocityEvent"] = None
        self.selected_event_options: Optional["EventSelectionOptions"] = None
        self.selected_event_origin: Optional[Any] = None
        self.theme_mode: ThemeMode = ThemeMode.DARK
        
        # logger.warning("declan 2026 hard coding depth to 3")
        self.folder_depth: int = 1  # 1
        
        # Callback registries (like grid_gpt.py pattern)
        self._file_list_changed_handlers: List[FileListChangedHandler] = []
        self._selection_changed_handlers: List[SelectionChangedHandler] = []
        self._metadata_changed_handlers: List[MetadataChangedHandler] = []
        self._theme_changed_handlers: List[ThemeChangedHandler] = []
        self._image_display_changed_handlers: List[ImageDisplayChangedHandler] = []
        self._roi_selection_changed_handlers: List[Callable[[Optional[int]], None]] = []
        self._event_selection_changed_handlers: List[EventSelectionChangedHandler] = []
    
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

    def on_event_selection_changed(self, handler: EventSelectionChangedHandler) -> None:
        """Register callback for event selection changes."""
        self._event_selection_changed_handlers.append(handler)
    
    # State mutation methods that trigger callbacks
    def load_folder(self, folder: Path, depth: Optional[int] = None) -> None:
        """Scan folder for kymograph files and update app state."""
        if depth is None:
            depth = self.folder_depth
        self.files = AcqImageList(
            path=folder,
            image_cls=KymImage,
            file_extension=".tif",
            depth=depth
        )
        self.folder = self.files.folder
        
        logger.info("load_folder: calling file_list_changed handlers")
        for handler in list(self._file_list_changed_handlers):
            try:
                handler()
            except Exception:
                logger.exception("Error in file_list_changed handler")
        
        if len(self.files) > 0:
            _selectFile = self.files[0]
            logger.info(f"selected file: {_selectFile}")
            self.select_file(_selectFile)
        else:
            self.select_file(None)
    
    def select_file(
        self,
        kym_file: Optional[KymImage],
        origin: Optional[SelectionOrigin] = None,
    ) -> None:
        """Select a file and notify handlers."""
        self.selected_file = kym_file
        
        # Initialize selected_roi_id to first ROI if available
        if kym_file is not None:
            # Load all available channels (idempotent - safe to call multiple times)
            channel_keys = kym_file.getChannelKeys()
            for channel in channel_keys:
                try:
                    kym_file.load_channel(channel)
                except Exception as e:
                    logger.warning(f"Failed to load channel {channel} for {kym_file.path}: {e}")
            
            roi_ids = kym_file.rois.get_roi_ids()
            if roi_ids:
                self.selected_roi_id = roi_ids[0]
            else:
                self.selected_roi_id = None
        else:
            self.selected_roi_id = None

        # Clear selected event when file changes
        self.select_event(
            event_id=None,
            roi_id=None,
            path=None,
            event=None,
            options=None,
            origin=origin,
        )
        
        logger.info(f"select_file: calling selection_changed handlers for {kym_file}, selected_roi_id={self.selected_roi_id}")
        for handler in list(self._selection_changed_handlers):
            try:
                handler(kym_file, origin)
            except Exception:
                logger.exception("Error in selection_changed handler")
    
    def refresh_file_rows(self) -> None:
        """Refresh file list (reloads current folder), preserving current file/ROI selection."""
        if not self.folder:
            return
        
        # Preserve current selection before reloading
        selected_path = None
        selected_roi_id = None
        if self.selected_file is not None and hasattr(self.selected_file, "path"):
            selected_path = str(self.selected_file.path)
            selected_roi_id = self.selected_roi_id
        
        # Reload folder (this will select first file by default)
        self.load_folder(self.folder, depth=self.folder_depth)
        
        # Restore previous selection if it still exists
        if selected_path is not None:
            for f in self.files:
                if str(f.path) == selected_path:
                    # Found the previously selected file, restore selection
                    self.select_file(f)
                    # Restore ROI selection if it still exists in the file
                    if selected_roi_id is not None:
                        roi_ids = f.rois.get_roi_ids()
                        if selected_roi_id in roi_ids:
                            self.select_roi(selected_roi_id)
                        elif roi_ids:
                            # ROI was deleted, select first available
                            self.select_roi(roi_ids[0])
                        else:
                            # No ROIs, clear selection
                            self.select_roi(None)
                    break
    
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
    
    def update_metadata(self, kym_file: KymImage) -> None:
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

    def select_event(
        self,
        event_id: Optional[str],
        roi_id: Optional[int],
        path: Optional[str],
        event: Optional["VelocityEvent"],
        options: Optional["EventSelectionOptions"] = None,
        origin: Optional[Any] = None,
    ) -> None:
        """Select a velocity event and notify handlers."""
        self.selected_event_id = event_id
        self.selected_event_roi_id = roi_id
        self.selected_event_path = path
        self.selected_event = event
        self.selected_event_options = options
        self.selected_event_origin = origin
        logger.info(
            f"select_event: calling event_selection_changed handlers for event_id={event_id}"
        )
        for handler in list(self._event_selection_changed_handlers):
            try:
                handler(event_id, roi_id, path, event, options, origin)
            except Exception:
                logger.exception("Error in event_selection_changed handler")
