"""Psygnal-powered state containers shared between GUI components."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar, List, Optional

from psygnal import EventedModel, Signal
from pydantic import ConfigDict, Field

from .kym_file import KymFile
from .repository import FolderScanResult, scan_folder
from .enums import SelectionOrigin


class TaskState(EventedModel):
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
    model_config = ConfigDict(arbitrary_types_allowed=True)

    folder: Optional[Path] = None
    files: List[KymFile] = Field(default_factory=list)
    selected_file: Optional[KymFile] = None

    file_list_changed: ClassVar[Signal] = Signal()
    selection_changed: ClassVar[Signal] = Signal(object, object)
    metadata_changed: ClassVar[Signal] = Signal(object)

    def load_folder(self, folder: Path) -> FolderScanResult:
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
        if self.selected_file is kym_file:
            return
        self.selected_file = kym_file
        self.selection_changed.emit(kym_file, origin)

    def notify_metadata_changed(self, kym_file: KymFile) -> None:
        self.metadata_changed.emit(kym_file)
