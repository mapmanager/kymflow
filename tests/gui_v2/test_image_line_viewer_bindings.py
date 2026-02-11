"""Tests for ImageLineViewerBindings - CRUD operations for kym events."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import numpy as np
import pytest

from kymflow.gui_v2.events import AddKymEvent, DeleteKymEvent, EditPhysicalUnits, VelocityEventUpdate, SelectionOrigin
from kymflow.gui_v2.views.image_line_viewer_bindings import ImageLineViewerBindings
from kymflow.core.analysis.velocity_events.velocity_events import VelocityEvent, MachineType, UserType


@pytest.fixture
def mock_view() -> MagicMock:
    """Create a mock ImageLineViewerView for testing."""
    view = MagicMock()
    view._current_file = MagicMock()
    view._current_roi_id = 1
    view._selected_event_id = None
    view._current_figure_dict = {
        "layout": {
            "shapes": [],
            "xaxis": {"range": [0, 100]},
            "xaxis2": {"range": [0, 100]},
        },
        "data": [],
    }
    view.ui_plotly_update_figure = MagicMock()
    view.refresh_velocity_events = MagicMock()
    view.set_kym_event_range_enabled = MagicMock()
    return view


@pytest.fixture
def mock_kym_analysis() -> MagicMock:
    """Create a mock KymAnalysis for testing."""
    analysis = MagicMock()
    analysis.has_analysis.return_value = True
    analysis.get_analysis_value.return_value = np.array([0.0, 1.0, 2.0, 3.0, 4.0, 5.0])
    analysis.get_time_bounds.return_value = (0.0, 5.0)  # Return tuple of (time_min, time_max)
    return analysis


@pytest.fixture
def sample_velocity_event() -> VelocityEvent:
    """Create a sample VelocityEvent for testing."""
    event = VelocityEvent(
        event_type="baseline_drop",  # EventType is a Literal, use string directly
        i_start=10,
        t_start=1.0,
        i_end=20,
        t_end=2.0,
        machine_type=MachineType.STALL_CANDIDATE,
        user_type=UserType.UNREVIEWED,
    )
    # Set UUID using object.__setattr__ since it's a frozen dataclass
    object.__setattr__(event, "_uuid", "test-event-uuid-123")
    return event


def test_add_kym_event_uses_crud(
    mock_view: MagicMock, mock_kym_analysis: MagicMock, sample_velocity_event: VelocityEvent
) -> None:
    """Test that add_kym_event uses CRUD operations when _current_figure_dict exists."""
    # Setup
    mock_view._current_file.get_kym_analysis.return_value = mock_kym_analysis
    mock_kym_analysis.find_event_by_uuid.return_value = (1, 0, sample_velocity_event)
    
    # Create bindings
    mock_bus = MagicMock()
    bindings = ImageLineViewerBindings(mock_bus, mock_view)
    
    # Create event
    event = AddKymEvent(
        event_id="test-event-uuid-123",
        roi_id=1,
        path=None,
        t_start=1.0,
        t_end=2.0,
        origin=SelectionOrigin.EVENT_TABLE,
        phase="state",
    )
    
    # Call handler
    bindings._on_add_kym_event(event)
    
    # Verify CRUD was used (not full render)
    mock_view.refresh_velocity_events.assert_not_called()
    mock_view.ui_plotly_update_figure.assert_called_once()
    
    # Verify event was added to dict
    assert len(mock_view._current_figure_dict["layout"]["shapes"]) == 1
    shape = mock_view._current_figure_dict["layout"]["shapes"][0]
    assert shape["name"] == "test-event-uuid-123"
    assert shape["type"] == "rect"


def test_add_kym_event_fallback_when_dict_none(
    mock_view: MagicMock, mock_kym_analysis: MagicMock, sample_velocity_event: VelocityEvent
) -> None:
    """Test that add_kym_event falls back to refresh_velocity_events when _current_figure_dict is None."""
    # Setup
    mock_view._current_figure_dict = None
    mock_view._current_file.get_kym_analysis.return_value = mock_kym_analysis
    
    # Create bindings
    mock_bus = MagicMock()
    bindings = ImageLineViewerBindings(mock_bus, mock_view)
    
    # Create event
    event = AddKymEvent(
        event_id="test-event-uuid-123",
        roi_id=1,
        path=None,
        t_start=1.0,
        t_end=2.0,
        origin=SelectionOrigin.EVENT_TABLE,
        phase="state",
    )
    
    # Call handler
    bindings._on_add_kym_event(event)
    
    # Verify fallback was used
    mock_view.refresh_velocity_events.assert_called_once()
    mock_view.ui_plotly_update_figure.assert_not_called()


def test_add_kym_event_roi_mismatch(
    mock_view: MagicMock, mock_kym_analysis: MagicMock, sample_velocity_event: VelocityEvent
) -> None:
    """Test that add_kym_event logs error and skips when ROI mismatch."""
    # Setup
    mock_view._current_roi_id = 2  # Different from event roi_id
    mock_view._current_file.get_kym_analysis.return_value = mock_kym_analysis
    
    # Create bindings
    mock_bus = MagicMock()
    bindings = ImageLineViewerBindings(mock_bus, mock_view)
    
    # Create event with different ROI
    event = AddKymEvent(
        event_id="test-event-uuid-123",
        roi_id=1,  # Different from current_roi_id
        path=None,
        t_start=1.0,
        t_end=2.0,
        origin=SelectionOrigin.EVENT_TABLE,
        phase="state",
    )
    
    # Call handler
    bindings._on_add_kym_event(event)
    
    # Verify nothing was called
    mock_view.refresh_velocity_events.assert_not_called()
    mock_view.ui_plotly_update_figure.assert_not_called()


def test_delete_kym_event_uses_crud(mock_view: MagicMock) -> None:
    """Test that delete_kym_event uses CRUD operations when _current_figure_dict exists."""
    # Setup: Add a shape to the dict first
    mock_view._current_figure_dict["layout"]["shapes"] = [
        {
            "type": "rect",
            "xref": "x2",
            "yref": "y2 domain",
            "name": "test-event-uuid-123",
            "x0": 1.0,
            "x1": 2.0,
        }
    ]
    mock_view._selected_event_id = "test-event-uuid-123"
    
    # Create bindings
    mock_bus = MagicMock()
    bindings = ImageLineViewerBindings(mock_bus, mock_view)
    
    # Create event
    event = DeleteKymEvent(
        event_id="test-event-uuid-123",
        roi_id=1,
        path=None,
        origin=SelectionOrigin.EVENT_TABLE,
        phase="state",
    )
    
    # Call handler
    bindings._on_delete_kym_event(event)
    
    # Verify CRUD was used (not full render)
    mock_view.refresh_velocity_events.assert_not_called()
    mock_view.ui_plotly_update_figure.assert_called_once()
    
    # Verify event was removed from dict
    assert len(mock_view._current_figure_dict["layout"]["shapes"]) == 0


def test_delete_kym_event_fallback_when_dict_none(mock_view: MagicMock) -> None:
    """Test that delete_kym_event falls back to refresh_velocity_events when _current_figure_dict is None."""
    # Setup
    mock_view._current_figure_dict = None
    
    # Create bindings
    mock_bus = MagicMock()
    bindings = ImageLineViewerBindings(mock_bus, mock_view)
    
    # Create event
    event = DeleteKymEvent(
        event_id="test-event-uuid-123",
        roi_id=1,
        path=None,
        origin=SelectionOrigin.EVENT_TABLE,
        phase="state",
    )
    
    # Call handler
    bindings._on_delete_kym_event(event)
    
    # Verify fallback was used
    mock_view.refresh_velocity_events.assert_called_once()
    mock_view.ui_plotly_update_figure.assert_not_called()


def test_delete_kym_event_deselects_when_selected(mock_view: MagicMock) -> None:
    """Test that delete_kym_event deselects all when deleted event was selected."""
    # Setup: Add a shape to the dict first
    mock_view._current_figure_dict["layout"]["shapes"] = [
        {
            "type": "rect",
            "xref": "x2",
            "yref": "y2 domain",
            "name": "test-event-uuid-123",
            "x0": 1.0,
            "x1": 2.0,
            "line": {"color": "yellow", "width": 2},  # Selected
        }
    ]
    mock_view._selected_event_id = "test-event-uuid-123"
    
    # Create bindings
    mock_bus = MagicMock()
    bindings = ImageLineViewerBindings(mock_bus, mock_view)
    
    # Create event
    event = DeleteKymEvent(
        event_id="test-event-uuid-123",
        roi_id=1,
        path=None,
        origin=SelectionOrigin.EVENT_TABLE,
        phase="state",
    )
    
    # Call handler
    bindings._on_delete_kym_event(event)
    
    # Verify event was removed
    assert len(mock_view._current_figure_dict["layout"]["shapes"]) == 0


def test_velocity_event_update_uses_crud(
    mock_view: MagicMock, mock_kym_analysis: MagicMock, sample_velocity_event: VelocityEvent
) -> None:
    """Test that velocity_event_update uses CRUD operations when _current_figure_dict exists."""
    # Setup: Add a shape to the dict first
    mock_view._current_figure_dict["layout"]["shapes"] = [
        {
            "type": "rect",
            "xref": "x2",
            "yref": "y2 domain",
            "name": "test-event-uuid-123",
            "x0": 1.0,
            "x1": 2.0,
        }
    ]
    mock_view._current_file.get_kym_analysis.return_value = mock_kym_analysis
    mock_kym_analysis.find_event_by_uuid.return_value = (1, 0, sample_velocity_event)
    
    # Create bindings
    mock_bus = MagicMock()
    bindings = ImageLineViewerBindings(mock_bus, mock_view)
    
    # Create event
    event = VelocityEventUpdate(
        event_id="test-event-uuid-123",
        path=None,
        field="t_start",
        value=1.5,
        updates=None,
        origin=SelectionOrigin.EVENT_TABLE,
        phase="state",
    )
    
    # Call handler
    bindings._on_velocity_event_update(event)
    
    # Verify CRUD was used (not full render)
    mock_view.refresh_velocity_events.assert_not_called()
    mock_view.ui_plotly_update_figure.assert_called_once()
    
    # Verify shape coordinates were updated
    shape = mock_view._current_figure_dict["layout"]["shapes"][0]
    assert shape["x0"] == 1.0  # Updated from event
    assert shape["x1"] == 2.0  # Updated from event


def test_velocity_event_update_fallback_when_dict_none(
    mock_view: MagicMock, mock_kym_analysis: MagicMock, sample_velocity_event: VelocityEvent
) -> None:
    """Test that velocity_event_update falls back to refresh_velocity_events when _current_figure_dict is None."""
    # Setup
    mock_view._current_figure_dict = None
    mock_view._current_file.get_kym_analysis.return_value = mock_kym_analysis
    
    # Create bindings
    mock_bus = MagicMock()
    bindings = ImageLineViewerBindings(mock_bus, mock_view)
    
    # Create event
    event = VelocityEventUpdate(
        event_id="test-event-uuid-123",
        path=None,
        field="t_start",
        value=1.5,
        updates=None,
        origin=SelectionOrigin.EVENT_TABLE,
        phase="state",
    )
    
    # Call handler
    bindings._on_velocity_event_update(event)
    
    # Verify fallback was used
    mock_view.refresh_velocity_events.assert_called_once()
    mock_view.ui_plotly_update_figure.assert_not_called()


def test_velocity_event_update_roi_mismatch(
    mock_view: MagicMock, mock_kym_analysis: MagicMock, sample_velocity_event: VelocityEvent
) -> None:
    """Test that velocity_event_update logs error and skips when ROI mismatch."""
    # Setup
    mock_view._current_roi_id = 2  # Different from event roi_id
    mock_view._current_file.get_kym_analysis.return_value = mock_kym_analysis
    mock_kym_analysis.find_event_by_uuid.return_value = (1, 0, sample_velocity_event)  # roi_id=1
    
    # Create bindings
    mock_bus = MagicMock()
    bindings = ImageLineViewerBindings(mock_bus, mock_view)
    
    # Create event
    event = VelocityEventUpdate(
        event_id="test-event-uuid-123",
        path=None,
        field="t_start",
        value=1.5,
        updates=None,
        origin=SelectionOrigin.EVENT_TABLE,
        phase="state",
    )
    
    # Call handler
    bindings._on_velocity_event_update(event)
    
    # Verify nothing was called
    mock_view.refresh_velocity_events.assert_not_called()
    mock_view.ui_plotly_update_figure.assert_not_called()


def test_velocity_event_update_preserves_selection(
    mock_view: MagicMock, mock_kym_analysis: MagicMock, sample_velocity_event: VelocityEvent
) -> None:
    """Test that velocity_event_update preserves selection styling when event is selected."""
    # Setup: Add a selected shape to the dict first
    mock_view._current_figure_dict["layout"]["shapes"] = [
        {
            "type": "rect",
            "xref": "x2",
            "yref": "y2 domain",
            "name": "test-event-uuid-123",
            "x0": 1.0,
            "x1": 2.0,
            "line": {"color": "yellow", "width": 2},  # Selected
        }
    ]
    mock_view._selected_event_id = "test-event-uuid-123"
    mock_view._current_file.get_kym_analysis.return_value = mock_kym_analysis
    mock_kym_analysis.find_event_by_uuid.return_value = (1, 0, sample_velocity_event)
    
    # Create bindings
    mock_bus = MagicMock()
    bindings = ImageLineViewerBindings(mock_bus, mock_view)
    
    # Create event
    event = VelocityEventUpdate(
        event_id="test-event-uuid-123",
        path=None,
        field="t_start",
        value=1.5,
        updates=None,
        origin=SelectionOrigin.EVENT_TABLE,
        phase="state",
    )
    
    # Call handler
    bindings._on_velocity_event_update(event)
    
    # Verify selection styling was preserved
    shape = mock_view._current_figure_dict["layout"]["shapes"][0]
    assert "line" in shape
    assert shape["line"]["color"] == "yellow"


def test_image_line_viewer_bindings_handles_edit_physical_units(mock_view: MagicMock) -> None:
    """Test that ImageLineViewerBindings handles EditPhysicalUnits state events."""
    # Setup
    mock_file = MagicMock()
    mock_view._current_file = mock_file
    mock_view._render_combined = MagicMock()
    
    # Create bindings
    mock_bus = MagicMock()
    bindings = ImageLineViewerBindings(mock_bus, mock_view)
    
    # Create EditPhysicalUnits event for current file
    event = EditPhysicalUnits(
        file=mock_file,
        seconds_per_line=0.002,
        um_per_pixel=0.5,
        origin=SelectionOrigin.EXTERNAL,
        phase="state",
    )
    
    # Call handler
    bindings._on_edit_physical_units(event)
    
    # Verify plot was refreshed
    mock_view._render_combined.assert_called_once()


def test_image_line_viewer_bindings_ignores_edit_physical_units_different_file(mock_view: MagicMock) -> None:
    """Test that ImageLineViewerBindings ignores EditPhysicalUnits for different file."""
    # Setup
    mock_file1 = MagicMock()
    mock_file2 = MagicMock()
    mock_view._current_file = mock_file1
    mock_view._render_combined = MagicMock()
    
    # Create bindings
    mock_bus = MagicMock()
    bindings = ImageLineViewerBindings(mock_bus, mock_view)
    
    # Create EditPhysicalUnits event for different file
    event = EditPhysicalUnits(
        file=mock_file2,  # Different file
        seconds_per_line=0.002,
        um_per_pixel=0.5,
        origin=SelectionOrigin.EXTERNAL,
        phase="state",
    )
    
    # Call handler
    bindings._on_edit_physical_units(event)
    
    # Verify plot was NOT refreshed
    mock_view._render_combined.assert_not_called()


def test_image_line_viewer_bindings_ignores_edit_physical_units_no_file(mock_view: MagicMock) -> None:
    """Test that ImageLineViewerBindings ignores EditPhysicalUnits when no file is selected."""
    # Setup
    mock_view._current_file = None
    mock_view._render_combined = MagicMock()
    
    # Create bindings
    mock_bus = MagicMock()
    bindings = ImageLineViewerBindings(mock_bus, mock_view)
    
    # Create EditPhysicalUnits event
    mock_file = MagicMock()
    event = EditPhysicalUnits(
        file=mock_file,
        seconds_per_line=0.002,
        um_per_pixel=0.5,
        origin=SelectionOrigin.EXTERNAL,
        phase="state",
    )
    
    # Call handler
    bindings._on_edit_physical_units(event)
    
    # Verify plot was NOT refreshed
    mock_view._render_combined.assert_not_called()
