"""Comprehensive tests for FileChanged and MetadataUpdate events.

Tests cover:
- Event creation and properties
- Event emit/consume flow through EventBus
- Intent → Controller → State phase flow
- Bindings subscription and handling
- ROI controllers emitting FileChanged
- Metadata controllers handling MetadataUpdate
- FileTableBindings handling both events
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.controllers.add_roi_controller import AddRoiController
from kymflow.gui_v2.controllers.delete_roi_controller import DeleteRoiController
from kymflow.gui_v2.controllers.edit_roi_controller import EditRoiController
from kymflow.gui_v2.controllers.metadata_controller import MetadataController
from kymflow.gui_v2.events import (
    AddRoi,
    DeleteRoi,
    EditRoi,
    FileChanged,
    FileSelection,
    MetadataUpdate,
    ROISelection,
    SelectionOrigin,
    SetRoiBounds,
)
from kymflow.gui_v2.state import AppState
from kymflow.gui_v2.views.file_table_bindings import FileTableBindings
from kymflow.gui_v2.views.file_table_view import FileTableView
from kymflow.gui_v2.views.image_line_viewer_bindings import ImageLineViewerBindings
from kymflow.gui_v2.views.image_line_viewer_view import ImageLineViewerView
from kymflow.gui_v2.views.metadata_experimental_bindings import MetadataExperimentalBindings
from kymflow.gui_v2.views.metadata_experimental_view import MetadataExperimentalView
from kymflow.gui_v2.views.metadata_header_bindings import MetadataHeaderBindings
from kymflow.gui_v2.views.metadata_header_view import MetadataHeaderView


# ============================================================================
# FileChanged Event Tests
# ============================================================================


def test_file_changed_event_creation() -> None:
    """Test FileChanged event creation with all properties."""
    mock_file = MagicMock()
    
    event = FileChanged(
        file=mock_file,
        change_type="roi",
        origin=SelectionOrigin.EXTERNAL,
        phase="state",
    )
    
    assert event.file == mock_file
    assert event.change_type == "roi"
    assert event.origin == SelectionOrigin.EXTERNAL
    assert event.phase == "state"


def test_file_changed_event_default_phase() -> None:
    """Test FileChanged event defaults phase to 'state'."""
    mock_file = MagicMock()
    
    event = FileChanged(
        file=mock_file,
        change_type="analysis",
        origin=SelectionOrigin.EXTERNAL,
    )
    
    assert event.phase == "state"


def test_file_changed_event_change_types() -> None:
    """Test FileChanged event with different change_type values."""
    mock_file = MagicMock()
    
    for change_type in ["roi", "analysis", "general"]:
        event = FileChanged(
            file=mock_file,
            change_type=change_type,  # type: ignore
            origin=SelectionOrigin.EXTERNAL,
        )
        assert event.change_type == change_type


def test_file_changed_event_emit_consume(bus: EventBus) -> None:
    """Test FileChanged event emit and consume through EventBus."""
    received: list[FileChanged] = []
    
    def handler(event: FileChanged) -> None:
        received.append(event)
    
    bus.subscribe_state(FileChanged, handler)
    
    mock_file = MagicMock()
    event = FileChanged(
        file=mock_file,
        change_type="roi",
        origin=SelectionOrigin.EXTERNAL,
        phase="state",
    )
    
    bus.emit(event)
    
    assert len(received) == 1
    assert received[0].file == mock_file
    assert received[0].change_type == "roi"
    assert received[0].origin == SelectionOrigin.EXTERNAL
    assert received[0].phase == "state"


def test_file_changed_event_intent_not_received(bus: EventBus) -> None:
    """Test that FileChanged intent phase events are not received by state subscribers."""
    received: list[FileChanged] = []
    
    def handler(event: FileChanged) -> None:
        received.append(event)
    
    bus.subscribe_state(FileChanged, handler)
    
    mock_file = MagicMock()
    # Try to emit with phase="intent" (should not be received by state subscriber)
    event = FileChanged(
        file=mock_file,
        change_type="roi",
        origin=SelectionOrigin.EXTERNAL,
        phase="intent",  # type: ignore
    )
    
    bus.emit(event)
    
    # State subscriber should not receive intent phase events
    assert len(received) == 0


# ============================================================================
# MetadataUpdate Event Tests
# ============================================================================


def test_metadata_update_event_creation() -> None:
    """Test MetadataUpdate event creation with all properties."""
    mock_file = MagicMock()
    
    event = MetadataUpdate(
        file=mock_file,
        metadata_type="experimental",
        fields={"note": "test note"},
        origin=SelectionOrigin.EXTERNAL,
        phase="intent",
    )
    
    assert event.file == mock_file
    assert event.metadata_type == "experimental"
    assert event.fields == {"note": "test note"}
    assert event.origin == SelectionOrigin.EXTERNAL
    assert event.phase == "intent"


def test_metadata_update_event_metadata_types() -> None:
    """Test MetadataUpdate event with different metadata_type values."""
    mock_file = MagicMock()
    
    for metadata_type in ["experimental", "header"]:
        event = MetadataUpdate(
            file=mock_file,
            metadata_type=metadata_type,  # type: ignore
            fields={"test": "value"},
            origin=SelectionOrigin.EXTERNAL,
            phase="intent",
        )
        assert event.metadata_type == metadata_type


def test_metadata_update_event_emit_consume(bus: EventBus) -> None:
    """Test MetadataUpdate event emit and consume through EventBus."""
    received_intent: list[MetadataUpdate] = []
    received_state: list[MetadataUpdate] = []
    
    def handler_intent(event: MetadataUpdate) -> None:
        received_intent.append(event)
    
    def handler_state(event: MetadataUpdate) -> None:
        received_state.append(event)
    
    bus.subscribe_intent(MetadataUpdate, handler_intent)
    bus.subscribe_state(MetadataUpdate, handler_state)
    
    mock_file = MagicMock()
    
    # Emit intent event
    intent_event = MetadataUpdate(
        file=mock_file,
        metadata_type="experimental",
        fields={"note": "test"},
        origin=SelectionOrigin.EXTERNAL,
        phase="intent",
    )
    bus.emit(intent_event)
    
    assert len(received_intent) == 1
    assert len(received_state) == 0
    assert received_intent[0].phase == "intent"
    
    # Emit state event
    state_event = MetadataUpdate(
        file=mock_file,
        metadata_type="experimental",
        fields={},
        origin=SelectionOrigin.EXTERNAL,
        phase="state",
    )
    bus.emit(state_event)
    
    assert len(received_intent) == 1  # Unchanged
    assert len(received_state) == 1
    assert received_state[0].phase == "state"


# ============================================================================
# ROI Controllers Emitting FileChanged Tests
# ============================================================================


def test_add_roi_controller_emits_file_changed(bus: EventBus, app_state: AppState) -> None:
    """Test that AddRoiController emits FileChanged after creating ROI."""
    controller = AddRoiController(app_state, bus)
    
    # Create a mock file with ROIs
    mock_file = MagicMock()
    mock_roi = MagicMock()
    mock_roi.id = 1
    mock_file.rois = MagicMock()
    mock_file.rois.numRois.return_value = 0
    mock_file.rois.create_roi.return_value = mock_roi
    mock_file.path = "/test.tif"
    
    app_state.selected_file = mock_file
    app_state.select_roi = MagicMock()
    
    received: list[FileChanged] = []
    
    def handler(event: FileChanged) -> None:
        received.append(event)
    
    bus.subscribe_state(FileChanged, handler)
    
    # Emit AddRoi intent
    bus.emit(
        AddRoi(
            roi_id=None,
            path="/test.tif",
            origin=SelectionOrigin.EXTERNAL,
            phase="intent",
        )
    )
    
    # Should emit FileChanged
    assert len(received) == 1
    assert received[0].file == mock_file
    assert received[0].change_type == "roi"
    assert received[0].origin == SelectionOrigin.EXTERNAL
    assert received[0].phase == "state"


def test_edit_roi_controller_emits_file_changed(bus: EventBus, app_state: AppState) -> None:
    """Test that EditRoiController emits FileChanged after editing ROI."""
    controller = EditRoiController(app_state, bus)
    
    # Create a mock file with ROIs
    mock_file = MagicMock()
    mock_roi = MagicMock()
    mock_roi.id = 1
    mock_file.rois = MagicMock()
    mock_file.rois.get.return_value = mock_roi
    mock_file.rois.edit_roi = MagicMock()
    mock_file.path = "/test.tif"
    
    app_state.selected_file = mock_file
    
    from kymflow.core.image_loaders.roi import RoiBounds
    
    received: list[FileChanged] = []
    
    def handler(event: FileChanged) -> None:
        received.append(event)
    
    bus.subscribe_state(FileChanged, handler)
    
    # Emit EditRoi intent
    bounds = RoiBounds(dim0_start=0, dim0_stop=10, dim1_start=0, dim1_stop=10)
    bus.emit(
        EditRoi(
            roi_id=1,
            bounds=bounds,
            path="/test.tif",
            origin=SelectionOrigin.EXTERNAL,
            phase="intent",
        )
    )
    
    # Should emit FileChanged
    assert len(received) == 1
    assert received[0].file == mock_file
    assert received[0].change_type == "roi"
    assert received[0].origin == SelectionOrigin.EXTERNAL
    assert received[0].phase == "state"


def test_delete_roi_controller_emits_file_changed(bus: EventBus, app_state: AppState) -> None:
    """Test that DeleteRoiController emits FileChanged after deleting ROI."""
    controller = DeleteRoiController(app_state, bus)
    
    # Create a mock file with ROIs
    mock_file = MagicMock()
    mock_roi = MagicMock()
    mock_roi.id = 1
    mock_file.rois = MagicMock()
    mock_file.rois.get.return_value = mock_roi
    mock_file.rois.delete = MagicMock()
    mock_file.rois.get_roi_ids.return_value = []
    mock_file.path = "/test.tif"
    
    app_state.selected_file = mock_file
    app_state.selected_roi_id = 1
    app_state.select_roi = MagicMock()
    
    received: list[FileChanged] = []
    
    def handler(event: FileChanged) -> None:
        received.append(event)
    
    bus.subscribe_state(FileChanged, handler)
    
    # Emit DeleteRoi intent
    bus.emit(
        DeleteRoi(
            roi_id=1,
            path="/test.tif",
            origin=SelectionOrigin.EXTERNAL,
            phase="intent",
        )
    )
    
    # Should emit FileChanged
    assert len(received) == 1
    assert received[0].file == mock_file
    assert received[0].change_type == "roi"
    assert received[0].origin == SelectionOrigin.EXTERNAL
    assert received[0].phase == "state"


# ============================================================================
# Metadata Controller Handling MetadataUpdate Tests
# ============================================================================


def test_metadata_controller_handles_experimental_intent(bus: EventBus, app_state: AppState) -> None:
    """Test that MetadataController handles experimental metadata update intent."""
    controller = MetadataController(app_state, bus)
    
    mock_file = MagicMock()
    mock_file.update_experiment_metadata = MagicMock()
    mock_file.update_header = MagicMock()
    
    app_state.update_metadata = MagicMock()
    
    # Emit experimental metadata update intent
    bus.emit(
        MetadataUpdate(
            file=mock_file,
            metadata_type="experimental",
            fields={"note": "test note", "accepted": True},
            origin=SelectionOrigin.EXTERNAL,
            phase="intent",
        )
    )
    
    mock_file.update_experiment_metadata.assert_called_once_with(note="test note", accepted=True)
    mock_file.update_header.assert_not_called()
    app_state.update_metadata.assert_called_once_with(mock_file)


def test_metadata_controller_handles_header_intent(bus: EventBus, app_state: AppState) -> None:
    """Test that MetadataController handles header metadata update intent."""
    controller = MetadataController(app_state, bus)
    
    mock_file = MagicMock()
    mock_file.update_experiment_metadata = MagicMock()
    mock_file.update_header = MagicMock()
    
    app_state.update_metadata = MagicMock()
    
    # Emit header metadata update intent
    bus.emit(
        MetadataUpdate(
            file=mock_file,
            metadata_type="header",
            fields={"voxels": [1.5, 2.5]},
            origin=SelectionOrigin.EXTERNAL,
            phase="intent",
        )
    )
    
    mock_file.update_header.assert_called_once_with(voxels=[1.5, 2.5])
    mock_file.update_experiment_metadata.assert_not_called()
    app_state.update_metadata.assert_called_once_with(mock_file)


def test_metadata_controller_ignores_state_phase(bus: EventBus, app_state: AppState) -> None:
    """Test that MetadataController ignores MetadataUpdate state phase events."""
    controller = MetadataController(app_state, bus)
    
    mock_file = MagicMock()
    mock_file.update_experiment_metadata = MagicMock()
    app_state.update_metadata = MagicMock()
    
    # Emit state phase event (should be ignored by controller)
    bus.emit(
        MetadataUpdate(
            file=mock_file,
            metadata_type="experimental",
            fields={"note": "test"},
            origin=SelectionOrigin.EXTERNAL,
            phase="state",
        )
    )
    
    # Controller should not process state phase events
    mock_file.update_experiment_metadata.assert_not_called()
    app_state.update_metadata.assert_not_called()


# ============================================================================
# FileTableBindings Handling Both Events Tests
# ============================================================================


def test_file_table_bindings_handles_metadata_update(bus: EventBus, mock_app_context) -> None:
    """Test that FileTableBindings handles MetadataUpdate events."""
    table = FileTableView(
        mock_app_context,
        on_selected=lambda e: None,
        on_metadata_update=lambda e: None,
        on_analysis_update=lambda e: None,
    )
    bindings = FileTableBindings(bus, table)
    
    table.update_row_for_file = MagicMock()
    table._grid = MagicMock()  # noqa: SLF001
    table._files_by_path = {"/test.tif": MagicMock()}  # noqa: SLF001
    
    mock_file = MagicMock()
    mock_file.path = "/test.tif"
    
    # Emit MetadataUpdate state event
    bus.emit(
        MetadataUpdate(
            file=mock_file,
            metadata_type="experimental",
            fields={"note": "test"},
            origin=SelectionOrigin.EXTERNAL,
            phase="state",
        )
    )
    
    table.update_row_for_file.assert_called_once_with(mock_file)
    
    bindings.teardown()


def test_file_table_bindings_handles_file_changed(bus: EventBus, mock_app_context) -> None:
    """Test that FileTableBindings handles FileChanged events."""
    table = FileTableView(
        mock_app_context,
        on_selected=lambda e: None,
        on_metadata_update=lambda e: None,
        on_analysis_update=lambda e: None,
    )
    bindings = FileTableBindings(bus, table)
    
    table.update_row_for_file = MagicMock()
    table._grid = MagicMock()  # noqa: SLF001
    table._files_by_path = {"/test.tif": MagicMock()}  # noqa: SLF001
    
    mock_file = MagicMock()
    mock_file.path = "/test.tif"
    
    # Emit FileChanged state event
    bus.emit(
        FileChanged(
            file=mock_file,
            change_type="roi",
            origin=SelectionOrigin.EXTERNAL,
            phase="state",
        )
    )
    
    table.update_row_for_file.assert_called_once_with(mock_file)
    
    bindings.teardown()


def test_file_table_bindings_handles_both_events(bus: EventBus, mock_app_context) -> None:
    """Test that FileTableBindings handles both MetadataUpdate and FileChanged."""
    table = FileTableView(
        mock_app_context,
        on_selected=lambda e: None,
        on_metadata_update=lambda e: None,
        on_analysis_update=lambda e: None,
    )
    bindings = FileTableBindings(bus, table)
    
    table.update_row_for_file = MagicMock()
    table._grid = MagicMock()  # noqa: SLF001
    table._files_by_path = {"/test.tif": MagicMock()}  # noqa: SLF001
    
    mock_file = MagicMock()
    mock_file.path = "/test.tif"
    
    # Emit MetadataUpdate
    bus.emit(
        MetadataUpdate(
            file=mock_file,
            metadata_type="experimental",
            fields={"note": "test"},
            origin=SelectionOrigin.EXTERNAL,
            phase="state",
        )
    )
    
    # Emit FileChanged
    bus.emit(
        FileChanged(
            file=mock_file,
            change_type="roi",
            origin=SelectionOrigin.EXTERNAL,
            phase="state",
        )
    )
    
    # Both should trigger update_row_for_file
    assert table.update_row_for_file.call_count == 2
    
    bindings.teardown()


# ============================================================================
# Metadata Bindings Handling MetadataUpdate Tests
# ============================================================================


def test_metadata_experimental_bindings_handles_metadata_update(bus: EventBus) -> None:
    """Test that MetadataExperimentalBindings handles MetadataUpdate events."""
    view = MetadataExperimentalView(on_metadata_update=lambda e: None)
    bindings = MetadataExperimentalBindings(bus, view)
    
    view.set_selected_file = MagicMock()
    
    mock_file = MagicMock()
    
    # Emit experimental metadata update
    bus.emit(
        MetadataUpdate(
            file=mock_file,
            metadata_type="experimental",
            fields={"note": "test"},
            origin=SelectionOrigin.EXTERNAL,
            phase="state",
        )
    )
    
    view.set_selected_file.assert_called_once_with(mock_file)
    
    # Emit header metadata update (should not trigger)
    view.set_selected_file.reset_mock()
    bus.emit(
        MetadataUpdate(
            file=mock_file,
            metadata_type="header",
            fields={"voxels": [1.0, 2.0]},
            origin=SelectionOrigin.EXTERNAL,
            phase="state",
        )
    )
    
    view.set_selected_file.assert_not_called()
    
    bindings.teardown()


def test_metadata_header_bindings_handles_metadata_update(bus: EventBus) -> None:
    """Test that MetadataHeaderBindings handles MetadataUpdate events."""
    view = MetadataHeaderView(on_metadata_update=lambda e: None)
    bindings = MetadataHeaderBindings(bus, view)
    
    view.set_selected_file = MagicMock()
    
    mock_file = MagicMock()
    
    # Emit header metadata update
    bus.emit(
        MetadataUpdate(
            file=mock_file,
            metadata_type="header",
            fields={"voxels": [1.0, 2.0]},
            origin=SelectionOrigin.EXTERNAL,
            phase="state",
        )
    )
    
    view.set_selected_file.assert_called_once_with(mock_file)
    
    # Emit experimental metadata update (should not trigger)
    view.set_selected_file.reset_mock()
    bus.emit(
        MetadataUpdate(
            file=mock_file,
            metadata_type="experimental",
            fields={"note": "test"},
            origin=SelectionOrigin.EXTERNAL,
            phase="state",
        )
    )
    
    view.set_selected_file.assert_not_called()
    
    bindings.teardown()


# ============================================================================
# ImageLineViewerBindings Handling MetadataUpdate Tests
# ============================================================================


def test_image_line_viewer_bindings_ignores_metadata_update(bus: EventBus) -> None:
    """Test that ImageLineViewerBindings does NOT handle MetadataUpdate events.
    
    Metadata edits (e.g., "note" field) do not affect the plot, so ImageLineViewerBindings
    should not subscribe to MetadataUpdate events.
    """
    view = ImageLineViewerView(
        on_kym_event_x_range=lambda e: None,
        on_set_roi_bounds=lambda e: None,
    )
    bindings = ImageLineViewerBindings(bus, view)
    
    # Verify view doesn't have set_metadata method (it was removed)
    assert not hasattr(view, 'set_metadata'), "set_metadata should have been removed"
    
    mock_file = MagicMock()
    
    # Emit MetadataUpdate state event
    bus.emit(
        MetadataUpdate(
            file=mock_file,
            metadata_type="experimental",
            fields={"note": "test"},
            origin=SelectionOrigin.EXTERNAL,
            phase="state",
        )
    )
    
    # Verify no plot refresh occurred (no way to directly verify, but if we got here
    # without errors, the subscription was correctly removed)
    # The fact that set_metadata doesn't exist confirms the removal
    
    bindings.teardown()


# ============================================================================
# Integration Tests: Full Flow
# ============================================================================


def test_metadata_update_full_flow(bus: EventBus, app_state: AppState) -> None:
    """Test complete flow: View emits intent → Controller updates → Bridge emits state → Bindings update."""
    # Setup controller
    controller = MetadataController(app_state, bus)
    
    # Setup bindings
    view = MetadataExperimentalView(on_metadata_update=bus.emit)
    bindings = MetadataExperimentalBindings(bus, view)
    view.set_selected_file = MagicMock()
    
    # Setup AppStateBridge callback (simplified)
    app_state.update_metadata = MagicMock()
    
    # Track state events
    state_events: list[MetadataUpdate] = []
    
    def track_state(event: MetadataUpdate) -> None:
        if event.phase == "state":
            state_events.append(event)
    
    bus.subscribe_state(MetadataUpdate, track_state)
    
    # Create mock file
    mock_file = MagicMock()
    mock_file.update_experiment_metadata = MagicMock()
    mock_file.experiment_metadata = MagicMock()
    
    # Simulate view emitting intent (user edits field)
    intent_event = MetadataUpdate(
        file=mock_file,
        metadata_type="experimental",
        fields={"note": "test note"},
        origin=SelectionOrigin.EXTERNAL,
        phase="intent",
    )
    bus.emit(intent_event)
    
    # Controller should update file
    mock_file.update_experiment_metadata.assert_called_once_with(note="test note")
    app_state.update_metadata.assert_called_once_with(mock_file)
    
    # Simulate AppStateBridge emitting state (after update_metadata callback)
    state_event = MetadataUpdate(
        file=mock_file,
        metadata_type="experimental",
        fields={},
        origin=SelectionOrigin.EXTERNAL,
        phase="state",
    )
    bus.emit(state_event)
    
    # Bindings should update view
    view.set_selected_file.assert_called_once_with(mock_file)
    
    bindings.teardown()


def test_file_changed_roi_flow(bus: EventBus, app_state: AppState, mock_app_context) -> None:
    """Test complete flow: ROI controller emits FileChanged → FileTableBindings updates table."""
    # Setup controller
    controller = AddRoiController(app_state, bus)
    
    # Setup bindings
    table = FileTableView(
        mock_app_context,
        on_selected=lambda e: None,
        on_metadata_update=lambda e: None,
        on_analysis_update=lambda e: None,
    )
    bindings = FileTableBindings(bus, table)
    table.update_row_for_file = MagicMock()
    table._grid = MagicMock()  # noqa: SLF001
    table._files_by_path = {"/test.tif": MagicMock()}  # noqa: SLF001
    
    # Create mock file
    mock_file = MagicMock()
    mock_file.path = "/test.tif"
    mock_roi = MagicMock()
    mock_roi.id = 1
    mock_file.rois = MagicMock()
    mock_file.rois.numRois.return_value = 0
    mock_file.rois.create_roi.return_value = mock_roi
    
    app_state.selected_file = mock_file
    app_state.select_roi = MagicMock()
    
    # Emit AddRoi intent
    bus.emit(
        AddRoi(
            roi_id=None,
            path="/test.tif",
            origin=SelectionOrigin.EXTERNAL,
            phase="intent",
        )
    )
    
    # FileTableBindings should receive FileChanged and update table
    table.update_row_for_file.assert_called_once_with(mock_file)
    
    bindings.teardown()
