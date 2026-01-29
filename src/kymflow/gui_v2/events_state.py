"""Event definitions for AppState change notifications.

This module defines events emitted by AppStateBridgeController when AppState
changes. These are state change notifications (not user intents), and are
used to update UI components when the underlying state changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from kymflow.core.image_loaders.kym_image import KymImage
    from kymflow.core.plotting.theme import ThemeMode
else:
    from kymflow.core.image_loaders.kym_image import KymImage
    from kymflow.core.plotting.theme import ThemeMode


@dataclass(frozen=True, slots=True)
class FileListChanged:
    """AppState file list change notification.

    Emitted by AppStateBridgeController when AppState.load_folder() completes
    and the file list is updated. Views (e.g., FileTableBindings) subscribe
    to this to update their UI when files are loaded.

    Attributes:
        files: Updated list of KymImage instances from AppState.
    """

    files: list[KymImage]


@dataclass(frozen=True, slots=True)
class ThemeChanged:
    """AppState theme change notification.

    Emitted by AppStateBridgeController when AppState.set_theme() is called
    and the theme mode changes. Views subscribe to this to update their
    UI when the theme changes.

    Attributes:
        theme: New theme mode (DARK or LIGHT).
    """

    theme: ThemeMode


@dataclass(frozen=True, slots=True)
class TaskStateChanged:
    """TaskState change notification.

    Emitted by TaskStateBridgeController when TaskState changes
    (running, progress, message, cancellable). Views subscribe to
    this to update UI (button states, progress bars).

    Attributes:
        running: Whether the task is currently running.
        progress: Progress value from 0.0 to 1.0.
        message: Status message describing current task state.
        cancellable: Whether the task can be cancelled.
        task_type: Type of task - "home", "batch", or "batch_overall".
        phase: Event phase - always "state".
    """

    running: bool
    progress: float
    message: str
    cancellable: bool
    task_type: Literal["home", "batch", "batch_overall"]
    phase: Literal["state"] = "state"


@dataclass(frozen=True, slots=True)
class AnalysisCompleted:
    """Analysis completion notification.

    Emitted by AnalysisController when a flow analysis finishes successfully.
    Views can subscribe to refresh analysis-dependent UI without relying on
    MetadataUpdate.

    Attributes:
        file: KymImage instance that was analyzed.
        roi_id: ROI ID that was analyzed.
        success: Whether analysis completed successfully.
        phase: Event phase - always "state".
    """

    file: KymImage
    roi_id: int | None
    success: bool
    phase: Literal["state"] = "state"

