"""Tests for metadata widgets (views, bindings, controller)."""

from __future__ import annotations

from unittest.mock import MagicMock
from kymflow.core.image_loaders.metadata import AcqImgHeader, ExperimentMetadata
from kymflow.gui_v2.state import AppState
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.controllers.metadata_controller import MetadataController
from kymflow.gui_v2.events import EditPhysicalUnits, FileSelection, MetadataUpdate, SelectionOrigin
from kymflow.gui_v2.views.metadata_experimental_bindings import MetadataExperimentalBindings
from kymflow.gui_v2.views.metadata_experimental_view import MetadataExperimentalView
from kymflow.gui_v2.views.metadata_header_bindings import MetadataHeaderBindings
from kymflow.gui_v2.views.metadata_header_view import MetadataHeaderView


def test_metadata_experimental_view_emits_intent(bus: EventBus) -> None:
    """Test that MetadataExperimentalView emits MetadataUpdate(phase="intent") on field edit."""
    received: list[MetadataUpdate] = []

    def on_update(event: MetadataUpdate) -> None:
        received.append(event)

    view = MetadataExperimentalView(on_metadata_update=on_update)
    # Create a mock file
    mock_file = MagicMock()
    mock_file.experiment_metadata = ExperimentMetadata()
    view._current_file = mock_file

    # Mock widget
    widget = MagicMock()
    widget.value = "test value"

    # Simulate field blur
    view._on_field_blur("note", widget)

    assert len(received) == 1
    assert received[0].phase == "intent"
    assert received[0].metadata_type == "experimental"
    assert received[0].fields == {"note": "test value"}
    assert received[0].file == mock_file


def test_metadata_header_view_emits_intent(bus: EventBus) -> None:
    """Test that MetadataHeaderView emits MetadataUpdate(phase="intent") on field edit."""
    received: list[MetadataUpdate] = []

    def on_update(event: MetadataUpdate) -> None:
        received.append(event)

    view = MetadataHeaderView(on_metadata_update=on_update)
    # Create a mock file
    mock_file = MagicMock()
    mock_file.header = AcqImgHeader()
    view._current_file = mock_file

    # Mock widget
    widget = MagicMock()
    widget.value = "1.5, 2.5"

    # Simulate field blur
    view._on_field_blur("voxels", widget)

    assert len(received) == 1
    assert received[0].phase == "intent"
    assert received[0].metadata_type == "header"
    assert received[0].fields == {"voxels": "1.5, 2.5"}
    assert received[0].file == mock_file


def test_metadata_experimental_bindings_subscribes_to_events(bus: EventBus) -> None:
    """Test that MetadataExperimentalBindings subscribes to correct events."""
    view = MetadataExperimentalView(on_metadata_update=lambda e: None)
    bindings = MetadataExperimentalBindings(bus, view)

    view.set_selected_file = MagicMock()

    # Emit FileSelection
    mock_file = MagicMock()
    bus.emit(
        FileSelection(
            path=None, file=mock_file, origin=SelectionOrigin.EXTERNAL, phase="state"
        )
    )
    view.set_selected_file.assert_called_once_with(mock_file)

    # Emit MetadataUpdate (experimental)
    bus.emit(
        MetadataUpdate(
            file=mock_file,
            metadata_type="experimental",
            fields={"note": "test"},
            origin=SelectionOrigin.EXTERNAL,
            phase="state",
        )
    )
    assert view.set_selected_file.call_count == 2

    # Emit MetadataUpdate (header - should not trigger)
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
    # Should not be called for header updates
    view.set_selected_file.assert_not_called()

    bindings.teardown()


def test_metadata_header_bindings_subscribes_to_events(bus: EventBus) -> None:
    """Test that MetadataHeaderBindings subscribes to correct events."""
    view = MetadataHeaderView(on_metadata_update=lambda e: None)
    bindings = MetadataHeaderBindings(bus, view)

    view.set_selected_file = MagicMock()

    # Emit FileSelection
    mock_file = MagicMock()
    bus.emit(
        FileSelection(
            path=None, file=mock_file, origin=SelectionOrigin.EXTERNAL, phase="state"
        )
    )
    view.set_selected_file.assert_called_once_with(mock_file)

    # Emit MetadataUpdate (header)
    bus.emit(
        MetadataUpdate(
            file=mock_file,
            metadata_type="header",
            fields={"voxels": [1.0, 2.0]},
            origin=SelectionOrigin.EXTERNAL,
            phase="state",
        )
    )
    assert view.set_selected_file.call_count == 2

    # Emit MetadataUpdate (experimental - should not trigger)
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
    # Should not be called for experimental updates
    view.set_selected_file.assert_not_called()

    bindings.teardown()


def test_metadata_controller_updates_file(bus: EventBus, app_state: AppState) -> None:
    """Test that MetadataController updates file and calls app_state.update_metadata()."""
    controller = MetadataController(app_state, bus)

    # Create a mock file
    mock_file = MagicMock()
    mock_file.update_experiment_metadata = MagicMock()
    mock_file.update_header = MagicMock()

    # Track calls to app_state.update_metadata
    calls = []
    original_update = app_state.update_metadata

    def track_update(file) -> None:
        calls.append(file)
        original_update(file)

    app_state.update_metadata = track_update

    # Emit experimental metadata update intent
    bus.emit(
        MetadataUpdate(
            file=mock_file,
            metadata_type="experimental",
            fields={"note": "test note"},
            origin=SelectionOrigin.EXTERNAL,
            phase="intent",
        )
    )

    mock_file.update_experiment_metadata.assert_called_once_with(note="test note")
    assert len(calls) == 1
    assert calls[0] == mock_file

    # Emit header metadata update intent
    mock_file.update_experiment_metadata.reset_mock()
    calls.clear()

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
    assert len(calls) == 1
    assert calls[0] == mock_file


def test_metadata_header_view_physical_units_validation() -> None:
    """Test that MetadataHeaderView validates physical units correctly."""
    view = MetadataHeaderView(on_metadata_update=lambda e: None)
    
    # Test valid values
    result = view._validate_physical_units(0.001, 0.284)
    assert result == (0.001, 0.284)
    
    # Test invalid - negative values
    result = view._validate_physical_units(-0.001, 0.284)
    assert result is None
    
    result = view._validate_physical_units(0.001, -0.284)
    assert result is None
    
    # Test invalid - zero values
    result = view._validate_physical_units(0.0, 0.284)
    assert result is None
    
    result = view._validate_physical_units(0.001, 0.0)
    assert result is None
    
    # Test invalid - non-numeric strings
    result = view._validate_physical_units("invalid", "0.284")
    assert result is None
    
    # Test valid - string numbers
    result = view._validate_physical_units("0.001", "0.284")
    assert result == (0.001, 0.284)


def test_metadata_header_view_is_kym_image_with_2d_voxels() -> None:
    """Test that MetadataHeaderView correctly identifies KymImage with 2D voxels."""
    view = MetadataHeaderView(on_metadata_update=lambda e: None)
    
    # Test None file
    assert view._is_kym_image_with_2d_voxels(None) is False
    
    # Test file without header property
    # Use spec=[] to create a mock without any attributes
    mock_file = MagicMock(spec=[])
    assert view._is_kym_image_with_2d_voxels(mock_file) is False
    
    # Test file with header but no voxels
    mock_file = MagicMock()
    mock_file.header = AcqImgHeader()
    mock_file.header.voxels = None
    assert view._is_kym_image_with_2d_voxels(mock_file) is False
    
    # Test file with header but wrong voxels length
    mock_file = MagicMock()
    mock_file.header = AcqImgHeader()
    mock_file.header.voxels = [1.0]  # Only 1D
    assert view._is_kym_image_with_2d_voxels(mock_file) is False
    
    mock_file.header.voxels = [1.0, 2.0, 3.0]  # 3D
    assert view._is_kym_image_with_2d_voxels(mock_file) is False
    
    # Test file with valid 2D voxels
    mock_file = MagicMock()
    mock_file.header = AcqImgHeader()
    mock_file.header.voxels = [0.001, 0.284]
    assert view._is_kym_image_with_2d_voxels(mock_file) is True


def test_metadata_header_view_emits_edit_physical_units_intent() -> None:
    """Test that MetadataHeaderView emits EditPhysicalUnits(phase="intent") on OK button."""
    received: list[EditPhysicalUnits] = []
    
    def on_edit(event: EditPhysicalUnits) -> None:
        received.append(event)
    
    view = MetadataHeaderView(
        on_metadata_update=lambda e: None,
        on_edit_physical_units=on_edit,
    )
    
    # Create a mock file with valid 2D voxels
    mock_file = MagicMock()
    mock_file.header = AcqImgHeader()
    mock_file.header.voxels = [0.001, 0.284]
    view._current_file = mock_file
    
    # Mock input widgets
    seconds_input = MagicMock()
    seconds_input.value = 0.002
    um_input = MagicMock()
    um_input.value = 0.5
    
    # Simulate OK button click
    view._on_physical_units_ok(seconds_input, um_input)
    
    assert len(received) == 1
    assert received[0].phase == "intent"
    assert received[0].seconds_per_line == 0.002
    assert received[0].um_per_pixel == 0.5
    assert received[0].file == mock_file
    assert received[0].origin == SelectionOrigin.EXTERNAL


def test_metadata_header_view_physical_units_ok_rejects_invalid() -> None:
    """Test that MetadataHeaderView rejects invalid physical units edits."""
    received: list[EditPhysicalUnits] = []
    
    def on_edit(event: EditPhysicalUnits) -> None:
        received.append(event)
    
    view = MetadataHeaderView(
        on_metadata_update=lambda e: None,
        on_edit_physical_units=on_edit,
    )
    
    # Create a mock file with valid 2D voxels
    mock_file = MagicMock()
    mock_file.header = AcqImgHeader()
    mock_file.header.voxels = [0.001, 0.284]
    view._current_file = mock_file
    
    # Test: no file selected
    view._current_file = None
    seconds_input = MagicMock()
    um_input = MagicMock()
    view._on_physical_units_ok(seconds_input, um_input)
    assert len(received) == 0
    
    # Test: file without 2D voxels
    view._current_file = mock_file
    mock_file.header.voxels = [1.0]  # 1D voxels
    view._on_physical_units_ok(seconds_input, um_input)
    assert len(received) == 0
    
    # Test: invalid values (negative)
    mock_file.header.voxels = [0.001, 0.284]  # Restore valid
    seconds_input.value = -0.001
    um_input.value = 0.5
    view._on_physical_units_ok(seconds_input, um_input)
    assert len(received) == 0
    
    # Test: invalid values (zero)
    seconds_input.value = 0.0
    um_input.value = 0.5
    view._on_physical_units_ok(seconds_input, um_input)
    assert len(received) == 0


def test_metadata_header_bindings_handles_edit_physical_units(bus: EventBus) -> None:
    """Test that MetadataHeaderBindings subscribes to and handles EditPhysicalUnits events."""
    view = MetadataHeaderView(on_metadata_update=lambda e: None)
    bindings = MetadataHeaderBindings(bus, view)
    
    view.set_selected_file = MagicMock()
    
    # Emit EditPhysicalUnits state event
    mock_file = MagicMock()
    bus.emit(
        EditPhysicalUnits(
            file=mock_file,
            seconds_per_line=0.002,
            um_per_pixel=0.5,
            origin=SelectionOrigin.EXTERNAL,
            phase="state",
        )
    )
    
    view.set_selected_file.assert_called_once_with(mock_file)
    
    bindings.teardown()
