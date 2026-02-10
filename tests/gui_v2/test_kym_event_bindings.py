"""Tests for KymEventBindings row-level update functionality."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.events import VelocityEventUpdate, SelectionOrigin
from kymflow.gui_v2.views.kym_event_bindings import KymEventBindings
from kymflow.gui_v2.views.kym_event_view import KymEventView


@pytest.fixture
def mock_app_context():
    """Create a mock AppContext for testing."""
    mock_context = MagicMock()
    mock_app_config = MagicMock()
    mock_app_config.get_blinded.return_value = False
    mock_context.app_config = mock_app_config
    return mock_context


@pytest.fixture
def sample_kym_file() -> KymImage:
    """Create a sample KymImage for testing."""
    import tempfile
    from pathlib import Path
    import numpy as np
    import tifffile
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        subdir = tmp_path / "a" / "b" / "c"
        subdir.mkdir(parents=True)
        test_file = subdir / "test.tif"
        test_image = np.zeros((100, 200), dtype=np.uint16)
        tifffile.imwrite(test_file, test_image)

        kym_file = KymImage(test_file, load_image=True)
        return kym_file


def test_on_velocity_event_update_uses_row_level_update(
    sample_kym_file: KymImage, mock_app_context
) -> None:
    """VelocityEventUpdate(state) for a single event should prefer row-level update over full refresh."""
    bus = EventBus("test-client")
    view = KymEventView(mock_app_context, on_selected=lambda e: None)

    # Set up: create ROI and add event
    from kymflow.core.image_loaders.roi import RoiBounds
    bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
    roi = sample_kym_file.rois.create_roi(bounds=bounds)
    kym_analysis = sample_kym_file.get_kym_analysis()
    event_id = kym_analysis.add_velocity_event(roi_id=roi.id, t_start=1.0, t_end=1.5)

    # Set events and render grid
    blinded = mock_app_context.app_config.get_blinded()
    report = kym_analysis.get_velocity_report(blinded=blinded)
    view.set_events(report)
    view.render()

    bindings = KymEventBindings(bus, view, app_state=None)
    bindings._current_file = sample_kym_file

    # Spy on view helpers
    view.update_row_for_event = MagicMock()
    view.set_events = MagicMock()
    view.set_selected_event_ids = MagicMock()

    event = VelocityEventUpdate(
        event_id=event_id,
        path=str(sample_kym_file.path),
        field="user_type",
        value="REVIEWED",
        origin=SelectionOrigin.EXTERNAL,
        phase="state",
    )

    bindings._on_velocity_event_update(event)

    # Row-level helper should be used; full refresh must not be called
    view.update_row_for_event.assert_called_once()
    # Verify the call was with a row dict containing the event_id
    call_args = view.update_row_for_event.call_args[0][0]
    assert call_args["event_id"] == event_id
    
    # set_events should NOT be called (row-level update used)
    view.set_events.assert_not_called()
    
    # Selection should be restored
    view.set_selected_event_ids.assert_called_once_with(
        [event_id],
        origin=SelectionOrigin.EXTERNAL,
    )


def test_on_velocity_event_update_falls_back_when_no_event_id(
    sample_kym_file: KymImage, mock_app_context
) -> None:
    """If event_id is None, bindings should fall back to full refresh."""
    bus = EventBus("test-client")
    view = KymEventView(mock_app_context, on_selected=lambda e: None)

    # Set up: create ROI and add event
    from kymflow.core.image_loaders.roi import RoiBounds
    bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
    roi = sample_kym_file.rois.create_roi(bounds=bounds)
    kym_analysis = sample_kym_file.get_kym_analysis()
    kym_analysis.add_velocity_event(roi_id=roi.id, t_start=1.0, t_end=1.5)

    # Set events and render grid
    blinded = mock_app_context.app_config.get_blinded()
    report = kym_analysis.get_velocity_report(blinded=blinded)
    view.set_events(report)
    view.render()

    bindings = KymEventBindings(bus, view, app_state=None)
    bindings._current_file = sample_kym_file

    view.update_row_for_event = MagicMock()
    view.set_events = MagicMock()
    view.set_selected_event_ids = MagicMock()

    # Event with event_id=None
    event = VelocityEventUpdate(
        event_id=None,
        path=str(sample_kym_file.path),
        field="user_type",
        value="REVIEWED",
        origin=SelectionOrigin.EXTERNAL,
        phase="state",
    )

    bindings._on_velocity_event_update(event)

    # Should fall back to full refresh
    view.update_row_for_event.assert_not_called()
    view.set_events.assert_called_once()
    # Selection should still be restored if event_id was provided (but it's None, so no call)
    view.set_selected_event_ids.assert_not_called()


def test_on_velocity_event_update_falls_back_when_grid_none(
    sample_kym_file: KymImage, mock_app_context
) -> None:
    """If the grid is not yet rendered, bindings should fall back to full refresh."""
    bus = EventBus("test-client")
    view = KymEventView(mock_app_context, on_selected=lambda e: None)

    # Set up: create ROI and add event
    from kymflow.core.image_loaders.roi import RoiBounds
    bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
    roi = sample_kym_file.rois.create_roi(bounds=bounds)
    kym_analysis = sample_kym_file.get_kym_analysis()
    event_id = kym_analysis.add_velocity_event(roi_id=roi.id, t_start=1.0, t_end=1.5)

    # Set events but don't render, so _grid is None
    blinded = mock_app_context.app_config.get_blinded()
    report = kym_analysis.get_velocity_report(blinded=blinded)
    view.set_events(report)
    # view.render() is NOT called

    bindings = KymEventBindings(bus, view, app_state=None)
    bindings._current_file = sample_kym_file

    view.update_row_for_event = MagicMock()
    view.set_events = MagicMock()
    view.set_selected_event_ids = MagicMock()

    event = VelocityEventUpdate(
        event_id=event_id,
        path=str(sample_kym_file.path),
        field="user_type",
        value="REVIEWED",
        origin=SelectionOrigin.EXTERNAL,
        phase="state",
    )

    bindings._on_velocity_event_update(event)

    # Should fall back to full refresh when grid is None
    view.update_row_for_event.assert_not_called()
    view.set_events.assert_called_once()


def test_on_velocity_event_update_falls_back_when_event_not_found(
    sample_kym_file: KymImage, mock_app_context
) -> None:
    """If get_velocity_event_row returns None, bindings should fall back to full refresh."""
    bus = EventBus("test-client")
    view = KymEventView(mock_app_context, on_selected=lambda e: None)

    # Set up: create ROI and add event
    from kymflow.core.image_loaders.roi import RoiBounds
    bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
    roi = sample_kym_file.rois.create_roi(bounds=bounds)
    kym_analysis = sample_kym_file.get_kym_analysis()
    kym_analysis.add_velocity_event(roi_id=roi.id, t_start=1.0, t_end=1.5)

    # Set events and render grid
    blinded = mock_app_context.app_config.get_blinded()
    report = kym_analysis.get_velocity_report(blinded=blinded)
    view.set_events(report)
    view.render()

    bindings = KymEventBindings(bus, view, app_state=None)
    bindings._current_file = sample_kym_file

    view.update_row_for_event = MagicMock()
    view.set_events = MagicMock()
    view.set_selected_event_ids = MagicMock()

    # Mock get_velocity_event_row to return None (event not found)
    original_get_row = kym_analysis.get_velocity_event_row
    kym_analysis.get_velocity_event_row = MagicMock(return_value=None)

    event = VelocityEventUpdate(
        event_id="non-existent-event-id",
        path=str(sample_kym_file.path),
        field="user_type",
        value="REVIEWED",
        origin=SelectionOrigin.EXTERNAL,
        phase="state",
    )

    bindings._on_velocity_event_update(event)

    # Should fall back to full refresh when event not found
    view.update_row_for_event.assert_not_called()
    view.set_events.assert_called_once()

    # Restore original method
    kym_analysis.get_velocity_event_row = original_get_row
