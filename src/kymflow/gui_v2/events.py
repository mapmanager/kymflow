"""Event definitions for file selection.

This module defines events emitted by UI components when users interact
with file selection controls (e.g., clicking rows in the file table).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Literal, Any

if TYPE_CHECKING:
    from kymflow.core.image_loaders.kym_image import KymImage
    from kymflow.gui_v2.state import ImageDisplayParams
else:
    from kymflow.gui_v2.state import ImageDisplayParams

EventPhase = Literal["intent", "state"]


class SelectionOrigin(str, Enum):
    """Origin of a selection change (prevents feedback loops).

    Used to track where a selection change originated so that components
    can avoid creating feedback loops when updating UI in response to
    state changes.

    Values:
        FILE_TABLE: Selection originated from user clicking in the file table.
        IMAGE_VIEWER: Selection originated from image/line viewer (e.g., ROI dropdown).
        EXTERNAL: Selection originated from external source (e.g., programmatic update).
        RESTORE: Selection originated from restoring saved selection on page load.
    """

    FILE_TABLE = "file_table"
    IMAGE_VIEWER = "image_viewer"
    EXTERNAL = "external"
    RESTORE = "restore"


@dataclass(frozen=True, slots=True)
class FileSelection:
    """File selection event (intent or state phase).

    This event is used for both intent (user wants to select) and state
    (selection has changed) phases. The phase field determines which handlers
    receive the event.

    For intent phase:
        - path is set (file path as string)
        - file is None
        - Emitted by views when user selects a file

    For state phase:
        - file is set (KymImage instance)
        - path can be derived from file.path
        - Emitted by AppStateBridge when AppState changes

    Attributes:
        path: File path as string, or None. Set in intent phase.
        file: KymImage instance, or None. Set in state phase.
        origin: SelectionOrigin indicating where the selection came from.
        phase: Event phase - "intent" or "state".
    """

    path: str | None
    file: "KymImage | None"
    origin: SelectionOrigin
    phase: EventPhase


@dataclass(frozen=True, slots=True)
class ROISelection:
    """ROI selection event (intent or state phase).

    This event is used for both intent (user wants to select ROI) and state
    (ROI selection has changed) phases. The phase field determines which handlers
    receive the event.

    For intent phase:
        - roi_id is set (or None to clear)
        - Emitted by views when user selects an ROI (e.g., from dropdown)

    For state phase:
        - roi_id is set (or None if cleared)
        - Emitted by AppStateBridge when AppState changes

    Attributes:
        roi_id: ROI ID, or None if selection cleared.
        origin: SelectionOrigin indicating where the selection came from.
        phase: Event phase - "intent" or "state".
    """

    roi_id: int | None
    origin: SelectionOrigin
    phase: EventPhase


@dataclass(frozen=True, slots=True)
class ImageDisplayChange:
    """Image display parameter change event (intent or state phase).

    This event is used for both intent (user wants to change display parameters)
    and state (display parameters have changed) phases. The phase field determines
    which handlers receive the event.

    For intent phase:
        - Emitted by views when user changes colorscale, zmin, or zmax
        - Handled by ImageDisplayController which updates AppState

    For state phase:
        - Emitted by AppStateBridge when AppState.set_image_display() is called
        - Subscribed to by bindings to update views

    Attributes:
        params: ImageDisplayParams containing colorscale, zmin, zmax, and origin.
        origin: SelectionOrigin indicating where the change came from.
        phase: Event phase - "intent" or "state".
    """

    params: "ImageDisplayParams"
    origin: SelectionOrigin
    phase: EventPhase


@dataclass(frozen=True, slots=True)
class MetadataUpdate:
    """Metadata update event (intent or state phase).

    This event is used for both intent (user wants to update metadata) and state
    (metadata has been updated) phases. The phase field determines which handlers
    receive the event.

    For intent phase:
        - Emitted by views when user edits a metadata field
        - Handled by MetadataController which updates the file

    For state phase:
        - Emitted by AppStateBridge when AppState.update_metadata() is called
        - Subscribed to by bindings to refresh views

    Attributes:
        file: KymImage instance whose metadata is being updated or was updated.
        metadata_type: Type of metadata - "experimental" or "header".
        fields: Dictionary mapping field names to new values.
        origin: SelectionOrigin indicating where the update came from.
        phase: Event phase - "intent" or "state".
    """

    file: "KymImage"
    metadata_type: Literal["experimental", "header"]
    fields: dict[str, Any]
    origin: SelectionOrigin
    phase: EventPhase


@dataclass(frozen=True, slots=True)
class AnalysisStart:
    """Analysis start intent event.

    Emitted by AnalysisToolbarView when user clicks "Analyze Flow" button.
    Handled by AnalysisController which starts the analysis task.

    Attributes:
        window_size: Number of time lines per analysis window.
        roi_id: ROI ID to analyze, or None to use default/selected ROI.
        phase: Event phase - "intent" or "state".
    """

    window_size: int
    roi_id: int | None
    phase: EventPhase


@dataclass(frozen=True, slots=True)
class AnalysisCancel:
    """Analysis cancel intent event.

    Emitted by AnalysisToolbarView when user clicks "Cancel" button.
    Handled by AnalysisController which cancels the analysis task.

    Attributes:
        phase: Event phase - "intent" or "state".
    """

    phase: EventPhase


@dataclass(frozen=True, slots=True)
class SaveSelected:
    """Save selected file intent event.

    Emitted by SaveButtonsView when user clicks "Save Selected".
    Handled by SaveController which saves the current file.

    Attributes:
        phase: Event phase - "intent" or "state".
    """

    phase: EventPhase


@dataclass(frozen=True, slots=True)
class SaveAll:
    """Save all files intent event.

    Emitted by SaveButtonsView when user clicks "Save All".
    Handled by SaveController which saves all files with analysis.

    Attributes:
        phase: Event phase - "intent" or "state".
    """

    phase: EventPhase
