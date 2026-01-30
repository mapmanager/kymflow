"""Event definitions for file selection.

This module defines events emitted by UI components when users interact
with file selection controls (e.g., clicking rows in the file table).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Literal, Any

if TYPE_CHECKING:
    from kymflow.core.analysis.velocity_events.velocity_events import VelocityEvent
    from kymflow.core.image_loaders.kym_image import KymImage
    from kymflow.core.image_loaders.roi import RoiBounds
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
        EVENT_TABLE: Selection originated from the event table.
        ANALYSIS_TOOLBAR: Selection originated from analysis toolbar (e.g., ROI dropdown).
    """

    FILE_TABLE = "file_table"
    IMAGE_VIEWER = "image_viewer"
    EXTERNAL = "external"
    RESTORE = "restore"
    EVENT_TABLE = "event_table"
    ANALYSIS_TOOLBAR = "analysis_toolbar"


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
class EventSelectionOptions:
    """Options that accompany a velocity event selection."""

    zoom: bool
    zoom_pad_sec: float


@dataclass(frozen=True, slots=True)
class EventSelection:
    """Velocity event selection event (intent or state phase).

    Purpose:
        Communicate which velocity event is currently selected so views/controllers
        can update UI and apply event-scoped actions.
    Triggered by:
        - Intent: KymEventView when user selects an event row.
        - State: AppStateBridge when AppState changes.
    Consumed by:
        - EventSelectionController (intent -> AppState).
        - ImageLineViewerBindings (state -> zoom to event).
        - KymEventBindings (state -> sync grid selection).
    Dependencies:
        - Optional: used by SetKymEventRangeState to carry the active event context.

    Attributes:
        event_id: Selected event ID, or None if selection cleared.
        roi_id: ROI ID for the event, or None if selection cleared.
        path: File path for the event, or None if selection cleared.
        event: VelocityEvent instance, or None if selection cleared.
        options: EventSelectionOptions for view-local behaviors.
        origin: SelectionOrigin indicating where the selection came from.
        phase: Event phase - "intent" or "state".
    """

    event_id: str | None
    roi_id: int | None
    path: str | None
    event: "VelocityEvent | None"
    options: EventSelectionOptions | None
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
class VelocityEventUpdate:
    """Velocity event update event (intent or state phase).

    Purpose:
        Apply one or more field updates to a velocity event (e.g., user_type,
        t_start/t_end).
    Triggered by:
        - Intent: KymEventView (cell edit or x-range proposal acceptance).
        - State: VelocityEventUpdateController after applying the update(s).
    Consumed by:
        - VelocityEventUpdateController (intent -> KymAnalysis update).
        - Any state listeners that need to refresh UI after update.
    Dependencies:
        - May be emitted as a result of SetKymEventXRange (intent).
        - Prefer using `updates` for range edits (t_start/t_end) to avoid duplicate
          state notifications.

    Attributes:
        event_id: Unique event id string.
        path: File path for the event (optional).
        field: Field name being updated (single-field update).
        value: New value for the field (single-field update).
        updates: Multi-field updates as a dict (e.g., {"t_start": x0, "t_end": x1}).
        origin: SelectionOrigin indicating where the update came from.
        phase: Event phase - "intent" or "state".
    """

    event_id: str
    path: str | None
    field: str | None = None
    value: Any | None = None
    updates: dict[str, Any] | None = None
    origin: SelectionOrigin = SelectionOrigin.EXTERNAL
    phase: EventPhase = "intent"


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
class SetKymEventRangeState:
    """Arm/disarm the next Plotly selection for setting a kym event x-range.

    Purpose:
        Toggle a short-lived UI state where the next rectangle selection on the
        plot proposes a new t_start/t_end for a specific velocity event.
    Triggered by:
        - Intent: KymEventView when the user clicks "Set Event Start/Stop".
        - State: KymEventRangeStateController mirrors intent -> state for bindings.
    Consumed by:
        - ImageLineViewerBindings (state -> enable/disable Plotly dragmode).
    Dependencies:
        - Requires an active EventSelection context (event_id/roi_id/path) to
          associate the selection with a specific event.

    Attributes:
        enabled: Whether the range-setting state is active.
        event_id: Active velocity event id (required when enabled=True).
        roi_id: ROI id for the active event (optional, for validation).
        path: File path for the active event (optional, for validation).
        origin: SelectionOrigin indicating where the toggle came from.
        phase: Event phase - "intent" or "state".
    """

    enabled: bool
    event_id: str | None
    roi_id: int | None
    path: str | None
    origin: SelectionOrigin
    phase: EventPhase


@dataclass(frozen=True, slots=True)
class SetKymEventXRange:
    """Propose a new x-range (t_start/t_end) for the active velocity event.

    Purpose:
        Carry the x-range from a Plotly rectangle selection to the event table
        so it can update the selected velocity event.
    Triggered by:
        - Intent: ImageLineViewerView when armed and a valid rect selection occurs.
    Consumed by:
        - KymEventView (validates against current selection, then emits VelocityEventUpdate).
    Dependencies:
        - Only emitted when SetKymEventRangeState(enabled=True) is active.

    Attributes:
        event_id: Velocity event id that the range applies to.
        roi_id: ROI id for validation (optional).
        path: File path for validation (optional).
        x0: Proposed range start (seconds).
        x1: Proposed range end (seconds).
        origin: SelectionOrigin indicating where the proposal came from.
        phase: Event phase - "intent" or "state".
    """

    event_id: str | None
    roi_id: int | None
    path: str | None
    x0: float
    x1: float
    origin: SelectionOrigin
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


@dataclass(frozen=True, slots=True)
class AddKymEvent:
    """Add a new velocity event event (intent or state phase).

    Purpose:
        Create a new velocity event with specified t_start/t_end. KymAnalysis
        will fill in defaults for other fields (event_type, user_type, etc.).
    Triggered by:
        - Intent: KymEventView when user completes range selection for new event.
        - State: AddKymEventController after creating the event.
    Consumed by:
        - AddKymEventController (intent -> KymAnalysis create).
        - Any state listeners that need to refresh UI after creation.
    Dependencies:
        - Requires SetKymEventRangeState + SetKymEventXRange flow to capture t_start/t_end.
        - roi_id comes from KymEventView._roi_filter (current ROI filter).
        - path comes from AppState.selected_file in controller.

    Attributes:
        event_id: Event ID after creation (None in intent, set in state).
        roi_id: ROI ID for the new event.
        path: File path for the event (optional, for validation).
        t_start: Event start time in seconds.
        t_end: Event end time in seconds (optional).
        origin: SelectionOrigin indicating where the add came from.
        phase: Event phase - "intent" or "state".
    """

    event_id: str | None
    roi_id: int
    path: str | None
    t_start: float
    t_end: float | None
    origin: SelectionOrigin
    phase: EventPhase


@dataclass(frozen=True, slots=True)
class DeleteKymEvent:
    """Delete a velocity event event (intent or state phase).

    Purpose:
        Remove a velocity event by event_id.
    Triggered by:
        - Intent: KymEventView when user confirms deletion.
        - State: DeleteKymEventController after deleting the event.
    Consumed by:
        - DeleteKymEventController (intent -> KymAnalysis delete).
        - Any state listeners that need to refresh UI after deletion.
    Dependencies:
        - Requires an active event selection (event_id) in KymEventView.

    Attributes:
        event_id: Unique event id string to delete.
        roi_id: ROI ID for the event (optional, for validation).
        path: File path for the event (optional, for validation).
        origin: SelectionOrigin indicating where the delete came from.
        phase: Event phase - "intent" or "state".
    """

    event_id: str
    roi_id: int | None
    path: str | None
    origin: SelectionOrigin
    phase: EventPhase


@dataclass(frozen=True, slots=True)
class AddRoi:
    """Add ROI event (intent or state phase).

    Purpose: Create a new ROI with default full-image bounds.
    Triggered by: Intent from AnalysisToolbarView "Add ROI" button.
    Consumed by: AddRoiController (intent → KymImage.rois.create_roi()).

    Attributes:
        roi_id: ROI ID after creation (None in intent, set in state).
        path: File path (optional, for validation).
        origin: SelectionOrigin indicating where the add came from.
        phase: Event phase - "intent" or "state".
    """

    roi_id: int | None
    path: str | None
    origin: SelectionOrigin
    phase: EventPhase


@dataclass(frozen=True, slots=True)
class DeleteRoi:
    """Delete ROI event (intent or state phase).

    Purpose: Remove an ROI by roi_id.
    Triggered by: Intent from AnalysisToolbarView "Delete ROI" button (with confirmation).
    Consumed by: DeleteRoiController (intent → KymImage.rois.delete()).

    Attributes:
        roi_id: ROI ID to delete.
        path: File path (optional, for validation).
        origin: SelectionOrigin indicating where the delete came from.
        phase: Event phase - "intent" or "state".
    """

    roi_id: int
    path: str | None
    origin: SelectionOrigin
    phase: EventPhase


@dataclass(frozen=True, slots=True)
class EditRoi:
    """Edit ROI event (intent or state phase).

    Purpose: Update ROI bounds (and optionally other attributes).
    Triggered by: Intent from AnalysisToolbarView "Edit ROI" button → SetRoiEditState → SetRoiBounds flow.
    Consumed by: EditRoiController (intent → KymImage.rois.edit_roi()).

    Attributes:
        roi_id: ROI ID to edit.
        bounds: New RoiBounds (optional, None means unchanged).
        path: File path (optional, for validation).
        origin: SelectionOrigin indicating where the edit came from.
        phase: Event phase - "intent" or "state".
    """

    roi_id: int
    bounds: "RoiBounds | None"
    path: str | None
    origin: SelectionOrigin
    phase: EventPhase


@dataclass(frozen=True, slots=True)
class SetRoiEditState:
    """Arm/disarm the next Plotly rectangle selection for editing ROI bounds.

    Purpose: Toggle UI state where next rectangle selection proposes new ROI bounds.
    Triggered by: Intent from AnalysisToolbarView "Edit ROI" button.
    Consumed by: ImageLineViewerBindings (state → enable/disable Plotly dragmode).

    Attributes:
        enabled: Whether the edit state is active.
        roi_id: Active ROI ID (required when enabled=True).
        path: File path (optional, for validation).
        origin: SelectionOrigin indicating where the toggle came from.
        phase: Event phase - "intent" or "state".
    """

    enabled: bool
    roi_id: int | None
    path: str | None
    origin: SelectionOrigin
    phase: EventPhase


@dataclass(frozen=True, slots=True)
class SetRoiBounds:
    """Propose new bounds for the active ROI.

    Purpose: Carry rectangle bounds from Plotly selection to EditRoiController.
    Triggered by: Intent from ImageLineViewerView when armed and valid rect selection occurs.
    Consumed by: EditRoiController (validates, then emits EditRoi).

    Attributes:
        roi_id: ROI ID that the bounds apply to.
        path: File path (optional, for validation).
        x0: Left edge (dim1_start).
        x1: Right edge (dim1_stop).
        y0: Top edge (dim0_start).
        y1: Bottom edge (dim0_stop).
        origin: SelectionOrigin indicating where the proposal came from.
        phase: Event phase - "intent" or "state".
    """

    roi_id: int | None
    path: str | None
    x0: float
    x1: float
    y0: float
    y1: float
    origin: SelectionOrigin
    phase: EventPhase


@dataclass(frozen=True, slots=True)
class NextPrevFileEvent:
    """Navigate to next or previous file event (intent phase only).

    Purpose:
        Programmatically navigate to the next or previous file in the file list.
    Triggered by:
        - Intent: KymEventView buttons or keyboard shortcuts.
    Consumed by:
        - NextPrevFileController (intent → finds file → emits FileSelection).

    Attributes:
        direction: "Next File" or "Prev File".
        origin: SelectionOrigin (EXTERNAL for programmatic navigation).
        phase: Event phase - "intent" only.
    """

    direction: Literal["Next File", "Prev File"]
    origin: SelectionOrigin = SelectionOrigin.EXTERNAL
    phase: EventPhase = "intent"
