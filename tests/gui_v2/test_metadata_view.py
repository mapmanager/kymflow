"""Tests for metadata widgets (views, bindings, controller, update_header)."""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pytest

from kymflow.core.image_loaders.acq_image import AcqImage
from kymflow.core.image_loaders.metadata import AcqImgHeader, ExperimentMetadata
from kymflow.gui.state import AppState
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.controllers.metadata_controller import MetadataController
from kymflow.gui_v2.events import FileSelection, MetadataUpdate, SelectionOrigin
from kymflow.gui_v2.views.metadata_experimental_bindings import MetadataExperimentalBindings
from kymflow.gui_v2.views.metadata_experimental_view import MetadataExperimentalView
from kymflow.gui_v2.views.metadata_header_bindings import MetadataHeaderBindings
from kymflow.gui_v2.views.metadata_header_view import MetadataHeaderView


def test_update_header_method() -> None:
    """Test that AcqImage.update_header() method works correctly."""
    # Create a mock AcqImage with a header
    # AcqImage requires either path or img_data, so provide dummy image data
    dummy_img = np.zeros((10, 10), dtype=np.uint8)
    acq_image = AcqImage(path=None, img_data=dummy_img)
    acq_image._header = AcqImgHeader()
    acq_image._header.voxels = [1.0, 2.0]
    acq_image._header.voxels_units = ["um", "um"]

    # Update header fields
    acq_image.update_header(voxels=[1.5, 2.5], voxels_units=["px", "px"])

    assert acq_image._header.voxels == [1.5, 2.5]
    assert acq_image._header.voxels_units == ["px", "px"]

    # Test with unknown field (should log warning but not crash)
    acq_image.update_header(unknown_field="value")
    # Should not have set unknown field
    assert not hasattr(acq_image._header, "unknown_field")


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
    mock_file._header = AcqImgHeader()
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
