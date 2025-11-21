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


@dataclass
class ImageDisplayParams:
    """Parameters for adjusting image display (colorscale, intensity range)."""

    colorscale: str
    zmin: Optional[int] = None
    zmax: Optional[int] = None


class TaskState(EventedModel):
    """Lightweight container for tracking long-running UI tasks."""

    running: bool = False
    progress: float = 0.0
    message: str = ""
    cancellable: bool = False

    progress_changed: ClassVar[Signal] = Signal(float)
    cancelled: ClassVar[Signal] = Signal()
    finished: ClassVar[Signal] = Signal()

    def set_progress(self, value: float, message: str = "") -> None:
        self.progress = value
        self.message = message
        self.progress_changed.emit(value)

    def request_cancel(self) -> None:
        if not self.running:
            return
        self.cancelled.emit()


class AppState(EventedModel):
    """Shared state for the NiceGUI app (selected folder, files, theme)."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    folder: Optional[Path] = None
    files: List[KymFile] = Field(default_factory=list)
    selected_file: Optional[KymFile] = None
    theme_mode: ThemeMode = ThemeMode.DARK

    file_list_changed: ClassVar[Signal] = Signal()
    selection_changed: ClassVar[Signal] = Signal(object, object)
    metadata_changed: ClassVar[Signal] = Signal(object)
    theme_changed: ClassVar[Signal] = Signal(object)
    image_display_changed: ClassVar[Signal] = Signal(object, object)

    def load_folder(self, folder: Path) -> FolderScanResult:
        """Scan folder for kymograph files and update app state."""
        result = scan_folder(folder)
        self.folder = result.folder
        self.files = result.files
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
        """Set the currently selected file and emit selection_changed signal."""
        if self.selected_file is kym_file:
            return
        self.selected_file = kym_file
        self.selection_changed.emit(kym_file, origin)

    def notify_metadata_changed(self, kym_file: KymFile) -> None:
        """Notify listeners that file metadata has been updated."""
        self.metadata_changed.emit(kym_file)

    def refresh_file_rows(self) -> None:
        """Notify listeners that file metadata changed without reloading folder."""
        self.file_list_changed.emit()

    def set_theme(self, mode: ThemeMode) -> None:
        """Set the application theme and emit theme_changed signal."""
        if self.theme_mode == mode:
            return
        self.theme_mode = mode
        self.theme_changed.emit(mode)

    def set_image_display(
        self,
        colorscale: str,
        zmin: Optional[int] = None,
        zmax: Optional[int] = None,
        origin: Optional[ImageDisplayOrigin] = None,
    ) -> None:
        """Emit signal to update image display parameters (colorscale, intensity range)."""
        if origin is None:
            origin = ImageDisplayOrigin.OTHER
        params = ImageDisplayParams(colorscale=colorscale, zmin=zmin, zmax=zmax)
        self.image_display_changed.emit(params, origin)
