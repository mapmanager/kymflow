"""Psygnal-powered state containers shared between GUI components."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, List, Optional

from psygnal import EventedModel, Signal
from pydantic import ConfigDict, Field

from .kym_file import KymFile
from .repository import FolderScanResult, scan_folder
from .enums import ImageDisplayOrigin, SelectionOrigin, ThemeMode

from .utils.logging import get_logger
logger = get_logger(__name__)

@dataclass
class ImageDisplayParams:
    """Event payload for image display parameter changes.
    
    Contains all information about display parameter changes, including
    which UI element initiated the change. Used to coordinate image display
    updates across GUI components.
    
    Attributes:
        colorscale: Name of the color scale to use (e.g., "viridis", "gray").
        zmin: Minimum intensity value for display scaling. If None, uses
            data minimum.
        zmax: Maximum intensity value for display scaling. If None, uses
            data maximum.
        origin: Source of the display parameter change (for avoiding feedback loops).
    """

    colorscale: str
    zmin: Optional[int] = None
    zmax: Optional[int] = None
    origin: ImageDisplayOrigin = ImageDisplayOrigin.OTHER

    def __str__(self) -> str:
        return f"ImageDisplayParams(colorscale: {self.colorscale}, zmin: {self.zmin}, zmax: {self.zmax}, origin: {self.origin})"

class TaskState(EventedModel):
    """Container for tracking long-running UI tasks with progress.
    
    Provides signals for progress updates, cancellation, and completion.
    Used to coordinate between background threads and GUI components.
    
    Attributes:
        running: Whether a task is currently running.
        progress: Progress value between 0.0 and 1.0.
        message: Status message describing current task state.
        cancellable: Whether the task can be cancelled.
    
    Signals:
        progress_changed: Emitted when progress value changes (float).
        cancelled: Emitted when cancellation is requested.
        finished: Emitted when task completes.
    """

    running: bool = False
    progress: float = 0.0
    message: str = ""
    cancellable: bool = False

    progress_changed: ClassVar[Signal] = Signal(float)
    cancelled: ClassVar[Signal] = Signal()
    finished: ClassVar[Signal] = Signal()

    def set_progress(self, value: float, message: str = "") -> None:
        """Update task progress and emit progress_changed signal.
        
        Args:
            value: Progress value between 0.0 and 1.0.
            message: Optional status message describing current progress.
        """
        self.progress = value
        self.message = message
        self.progress_changed.emit(value)

    def request_cancel(self) -> None:
        """Request cancellation of the current task.
        
        Emits the cancelled signal if a task is currently running.
        The task implementation should check for cancellation and stop
        processing when this is called.
        """
        if not self.running:
            return
        self.cancelled.emit()


class AppState(EventedModel):
    """Shared application state for the NiceGUI GUI.
    
    Manages the current folder, file list, selected file, theme, and image
    display parameters. Provides signals for state changes to coordinate
    updates across GUI components.
    
    Attributes:
        folder: Currently selected folder path.
        files: List of KymFile instances in the current folder.
        selected_file: Currently selected KymFile, or None.
        theme_mode: Current UI theme (dark or light).
    
    Signals:
        file_list_changed: Emitted when the file list is updated.
        selection_changed: Emitted when the selected file changes
            (kym_file, origin).
        metadata_changed: Emitted when file metadata is updated (kym_file).
        theme_changed: Emitted when theme changes (ThemeMode).
        image_display_changed: Emitted when image display parameters change
            (ImageDisplayParams).
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    folder: Optional[Path] = None
    files: List[KymFile] = Field(default_factory=list)
    selected_file: Optional[KymFile] = None
    theme_mode: ThemeMode = ThemeMode.DARK

    file_list_changed: ClassVar[Signal] = Signal()
    selection_changed: ClassVar[Signal] = Signal(object, object)
    metadata_changed: ClassVar[Signal] = Signal(object)
    theme_changed: ClassVar[Signal] = Signal(object)
    image_display_changed: ClassVar[Signal] = Signal(object)

    def load_folder(self, folder: Path) -> FolderScanResult:
        """Scan folder for kymograph files and update app state.
        
        Scans the specified folder for TIFF files, creates KymFile instances,
        and updates the app state. Automatically selects the first file if
        files are found. Emits file_list_changed signal.
        
        Args:
            folder: Path to the folder to scan.
        
        Returns:
            FolderScanResult containing the scanned folder and file list.
        """
        result = scan_folder(folder)
        self.folder = result.folder
        self.files = result.files
        
        logger.info(f"--> emit file_list_changed")
        self.file_list_changed.emit()
        
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
        """Set the currently selected file and emit selection_changed signal.
        
        Updates the selected file and emits a signal to notify GUI components.
        If the file is already selected, no signal is emitted.
        
        Args:
            kym_file: KymFile to select, or None to clear selection.
            origin: Source of the selection change (for avoiding feedback loops).
                Defaults to None.
        """
        if self.selected_file is kym_file:
            return
        self.selected_file = kym_file

        logger.info(f"--> emit selection_changed kym_file: {kym_file} origin: {origin}")
        self.selection_changed.emit(kym_file, origin)

    def notify_metadata_changed(self, kym_file: KymFile) -> None:
        """Notify listeners that file metadata has been updated.
        
        Emits metadata_changed signal to notify GUI components that metadata
        for the specified file has been modified.
        
        Args:
            kym_file: KymFile whose metadata was updated.
        """
        logger.info(f"--> emit metadata_changed kym_file: {kym_file}")
        self.metadata_changed.emit(kym_file)

    def refresh_file_rows(self) -> None:
        """Notify listeners that file metadata changed without reloading folder.
        
        Emits file_list_changed signal to refresh file table displays without
        re-scanning the folder. Useful when metadata is updated but the file
        list itself hasn't changed.
        """
        logger.info(f"--> emit file_list_changed")
        self.file_list_changed.emit()

    def set_theme(self, mode: ThemeMode) -> None:
        """Set the application theme and emit theme_changed signal.
        
        Updates the theme mode and notifies GUI components. If the theme
        is already set to the specified mode, no signal is emitted.
        
        Args:
            mode: Theme mode to set (DARK or LIGHT).
        """
        if self.theme_mode == mode:
            return
        self.theme_mode = mode
        logger.info(f"--> emit theme_changed mode: {mode}")
        self.theme_changed.emit(mode)

    def set_image_display(self, params: ImageDisplayParams) -> None:
        """Emit signal to update image display parameters (colorscale, intensity range).
        
        Args:
            params: Complete event payload containing colorscale, zmin, zmax, and origin.
        """
        logger.info(f"--> emit image_display_changed {params}")
        self.image_display_changed.emit(params)
