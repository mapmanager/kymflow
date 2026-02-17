"""Tests for CRUD functions for kym event rectangles in line_plots.py."""

from __future__ import annotations

import numpy as np
import pytest

from kymflow.core.analysis.velocity_events.velocity_events import (
    MachineType,
    UserType,
    VelocityEvent,
)
from kymflow.core.plotting.line_plots import (
    _calculate_event_rect_coords,
    _find_kym_event_rect_by_uuid,
    add_kym_event_rect,
    clear_kym_event_rects,
    delete_kym_event_rect,
    move_kym_event_rect,
    select_kym_event_rect,
)


@pytest.fixture
def sample_velocity_event() -> VelocityEvent:
    """Create a sample VelocityEvent for testing."""
    event = VelocityEvent(
        event_type="baseline_drop",
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


@pytest.fixture
def sample_plotly_dict() -> dict:
    """Create a sample plotly figure dictionary for testing."""
    return {
        "layout": {
            "shapes": [],
            "xaxis": {"range": [0, 100]},
            "xaxis2": {"range": [0, 100]},
        },
        "data": [],
    }


# ============================================================================
# Tests for _calculate_event_rect_coords
# ============================================================================


def test_calculate_event_rect_coords_normal(sample_velocity_event: VelocityEvent) -> None:
    """Test _calculate_event_rect_coords with normal event."""
    time_range = (0.0, 10.0)
    x0, x1 = _calculate_event_rect_coords(sample_velocity_event, time_range)
    
    assert x0 == 1.0
    assert x1 == 2.0
    assert x0 < x1


def test_calculate_event_rect_coords_no_end(sample_velocity_event: VelocityEvent) -> None:
    """Test _calculate_event_rect_coords returns None when event has neither t_peak nor t_end."""
    # Create event without t_peak and without t_end (20260217_fix_t_peak: no rect drawn)
    event = VelocityEvent(
        event_type="baseline_drop",
        i_start=10,
        t_start=1.0,
        i_peak=None,
        i_end=None,
        t_end=None,
        machine_type=MachineType.STALL_CANDIDATE,
        user_type=UserType.UNREVIEWED,
    )
    
    time_range = (0.0, 10.0)
    result = _calculate_event_rect_coords(event, time_range, span_sec_if_no_end=0.5)
    
    assert result is None


def test_calculate_event_rect_coords_clamps_to_time_range(sample_velocity_event: VelocityEvent) -> None:
    """Test _calculate_event_rect_coords clamps t_end to time_range."""
    time_range = (0.0, 1.5)  # Max time is 1.5, but event.t_end is 2.0
    x0, x1 = _calculate_event_rect_coords(sample_velocity_event, time_range)
    
    assert x0 == 1.0
    assert x1 == 1.5  # Clamped to time_range max
    assert x0 < x1


def test_calculate_event_rect_coords_uses_t_peak(sample_velocity_event: VelocityEvent) -> None:
    """Test _calculate_event_rect_coords uses t_peak as right edge when present."""
    # Event with t_peak (takes precedence over t_end)
    event = VelocityEvent(
        event_type="baseline_drop",
        i_start=10,
        t_start=1.0,
        i_peak=15,
        t_peak=1.5,
        i_end=20,
        t_end=2.0,
        machine_type=MachineType.STALL_CANDIDATE,
        user_type=UserType.UNREVIEWED,
    )
    time_range = (0.0, 10.0)
    result = _calculate_event_rect_coords(event, time_range)
    assert result is not None
    x0, x1 = result
    assert x0 == 1.0
    assert x1 == 1.5  # t_peak, not t_end
    assert x0 < x1


def test_calculate_event_rect_coords_uses_t_end_when_no_t_peak(sample_velocity_event: VelocityEvent) -> None:
    """Test _calculate_event_rect_coords falls back to t_end for user-added events (no t_peak)."""
    # User-added event: t_start and t_end, no t_peak
    event = VelocityEvent(
        event_type="User Added",
        i_start=10,
        t_start=1.0,
        i_peak=None,
        t_peak=None,
        i_end=20,
        t_end=2.0,
        machine_type=MachineType.OTHER,
        user_type=UserType.UNREVIEWED,
    )
    time_range = (0.0, 10.0)
    result = _calculate_event_rect_coords(event, time_range)
    assert result is not None
    x0, x1 = result
    assert x0 == 1.0
    assert x1 == 2.0  # t_end fallback
    assert x0 < x1


def test_calculate_event_rect_coords_invalid_time_range(sample_velocity_event: VelocityEvent) -> None:
    """Test _calculate_event_rect_coords raises ValueError for invalid time_range."""
    with pytest.raises(ValueError, match="time_range is None"):
        _calculate_event_rect_coords(sample_velocity_event, None)
    
    with pytest.raises(ValueError, match="Invalid time_range"):
        _calculate_event_rect_coords(sample_velocity_event, (1.0, 0.0))  # min > max
    
    with pytest.raises(ValueError, match="Invalid time_range"):
        _calculate_event_rect_coords(sample_velocity_event, (np.inf, 10.0))  # inf


def test_calculate_event_rect_coords_handles_invalid_t_end(sample_velocity_event: VelocityEvent) -> None:
    """Test _calculate_event_rect_coords returns None when t_end <= t_start and no t_peak."""
    # Create event with t_end < t_start and no t_peak (20260217_fix_t_peak: neither valid)
    event = VelocityEvent(
        event_type="baseline_drop",
        i_start=10,
        t_start=2.0,
        i_peak=None,
        i_end=20,
        t_end=1.0,  # Less than t_start - treated as invalid
        machine_type=MachineType.STALL_CANDIDATE,
        user_type=UserType.UNREVIEWED,
    )
    
    time_range = (0.0, 10.0)
    result = _calculate_event_rect_coords(event, time_range, span_sec_if_no_end=0.20)
    
    assert result is None


# ============================================================================
# Tests for _find_kym_event_rect_by_uuid
# ============================================================================


def test_find_kym_event_rect_by_uuid_found(sample_plotly_dict: dict) -> None:
    """Test _find_kym_event_rect_by_uuid finds existing rect."""
    # Add a shape
    shape = {
        "type": "rect",
        "xref": "x2",
        "yref": "y2 domain",
        "name": "test-uuid-123",
        "x0": 1.0,
        "x1": 2.0,
    }
    sample_plotly_dict["layout"]["shapes"].append(shape)
    
    result = _find_kym_event_rect_by_uuid(sample_plotly_dict, "test-uuid-123", row=2)
    
    assert result is not None
    idx, found_shape = result
    assert idx == 0
    assert found_shape == shape


def test_find_kym_event_rect_by_uuid_not_found(sample_plotly_dict: dict) -> None:
    """Test _find_kym_event_rect_by_uuid returns None when not found."""
    result = _find_kym_event_rect_by_uuid(sample_plotly_dict, "nonexistent-uuid", row=2)
    assert result is None


def test_find_kym_event_rect_by_uuid_wrong_row(sample_plotly_dict: dict) -> None:
    """Test _find_kym_event_rect_by_uuid ignores shapes in different row."""
    # Add shape for row 2
    shape = {
        "type": "rect",
        "xref": "x2",
        "yref": "y2 domain",
        "name": "test-uuid-123",
    }
    sample_plotly_dict["layout"]["shapes"].append(shape)
    
    # Search in row 1 (should not find it)
    result = _find_kym_event_rect_by_uuid(sample_plotly_dict, "test-uuid-123", row=1)
    assert result is None


def test_find_kym_event_rect_by_uuid_wrong_type(sample_plotly_dict: dict) -> None:
    """Test _find_kym_event_rect_by_uuid ignores non-rect shapes."""
    # Add a line shape (not rect)
    shape = {
        "type": "line",
        "xref": "x2",
        "yref": "y2 domain",
        "name": "test-uuid-123",
    }
    sample_plotly_dict["layout"]["shapes"].append(shape)
    
    result = _find_kym_event_rect_by_uuid(sample_plotly_dict, "test-uuid-123", row=2)
    assert result is None


def test_find_kym_event_rect_by_uuid_no_layout(sample_plotly_dict: dict) -> None:
    """Test _find_kym_event_rect_by_uuid returns None when layout missing."""
    del sample_plotly_dict["layout"]
    result = _find_kym_event_rect_by_uuid(sample_plotly_dict, "test-uuid-123", row=2)
    assert result is None


def test_find_kym_event_rect_by_uuid_no_shapes(sample_plotly_dict: dict) -> None:
    """Test _find_kym_event_rect_by_uuid returns None when shapes missing."""
    del sample_plotly_dict["layout"]["shapes"]
    result = _find_kym_event_rect_by_uuid(sample_plotly_dict, "test-uuid-123", row=2)
    assert result is None


# ============================================================================
# Tests for add_kym_event_rect
# ============================================================================


def test_add_kym_event_rect_success(
    sample_plotly_dict: dict, sample_velocity_event: VelocityEvent
) -> None:
    """Test add_kym_event_rect successfully adds a rect."""
    time_range = (0.0, 10.0)
    
    add_kym_event_rect(sample_plotly_dict, sample_velocity_event, time_range, row=2)
    
    shapes = sample_plotly_dict["layout"]["shapes"]
    assert len(shapes) == 1
    
    shape = shapes[0]
    assert shape["type"] == "rect"
    assert shape["xref"] == "x2"
    assert shape["yref"] == "y2 domain"
    assert shape["name"] == "test-event-uuid-123"
    assert shape["x0"] == 1.0
    assert shape["x1"] == 2.0
    assert shape["fillcolor"] == "rgba(255, 0, 0, 0.5)"  # Red for baseline_drop


def test_add_kym_event_rect_skips_when_no_peak_no_end(sample_plotly_dict: dict) -> None:
    """Test add_kym_event_rect does not add rect when event has neither t_peak nor t_end."""
    event = VelocityEvent(
        event_type="baseline_drop",
        i_start=10,
        t_start=1.0,
        i_peak=None,
        i_end=None,
        t_end=None,
        machine_type=MachineType.STALL_CANDIDATE,
        user_type=UserType.UNREVIEWED,
    )
    object.__setattr__(event, "_uuid", "uuid-no-peak-no-end")
    time_range = (0.0, 10.0)
    add_kym_event_rect(sample_plotly_dict, event, time_range, row=2)
    assert len(sample_plotly_dict["layout"]["shapes"]) == 0


def test_add_kym_event_rect_no_uuid(
    sample_plotly_dict: dict, sample_velocity_event: VelocityEvent
) -> None:
    """Test add_kym_event_rect fails when event has no UUID."""
    # Remove UUID
    object.__setattr__(sample_velocity_event, "_uuid", None)
    
    time_range = (0.0, 10.0)
    add_kym_event_rect(sample_plotly_dict, sample_velocity_event, time_range, row=2)
    
    # Should not add shape
    assert len(sample_plotly_dict["layout"]["shapes"]) == 0


def test_add_kym_event_rect_duplicate_uuid(
    sample_plotly_dict: dict, sample_velocity_event: VelocityEvent
) -> None:
    """Test add_kym_event_rect fails when UUID already exists."""
    time_range = (0.0, 10.0)
    
    # Add first time
    add_kym_event_rect(sample_plotly_dict, sample_velocity_event, time_range, row=2)
    assert len(sample_plotly_dict["layout"]["shapes"]) == 1
    
    # Try to add again (should fail)
    add_kym_event_rect(sample_plotly_dict, sample_velocity_event, time_range, row=2)
    
    # Should still only have one shape
    assert len(sample_plotly_dict["layout"]["shapes"]) == 1


def test_add_kym_event_rect_initializes_shapes_list(
    sample_plotly_dict: dict, sample_velocity_event: VelocityEvent
) -> None:
    """Test add_kym_event_rect initializes shapes list if missing."""
    del sample_plotly_dict["layout"]["shapes"]
    
    time_range = (0.0, 10.0)
    add_kym_event_rect(sample_plotly_dict, sample_velocity_event, time_range, row=2)
    
    assert "shapes" in sample_plotly_dict["layout"]
    assert len(sample_plotly_dict["layout"]["shapes"]) == 1


def test_add_kym_event_rect_different_event_types(
    sample_plotly_dict: dict,
) -> None:
    """Test add_kym_event_rect uses correct colors for different event types."""
    time_range = (0.0, 10.0)
    
    # Test baseline_rise (green)
    event_rise = VelocityEvent(
        event_type="baseline_rise",
        i_start=10,
        t_start=1.0,
        i_end=20,
        t_end=2.0,
        machine_type=MachineType.OTHER,
        user_type=UserType.UNREVIEWED,
    )
    object.__setattr__(event_rise, "_uuid", "uuid-rise")
    add_kym_event_rect(sample_plotly_dict, event_rise, time_range, row=2)
    
    # Test nan_gap (blue)
    event_gap = VelocityEvent(
        event_type="nan_gap",
        i_start=30,
        t_start=3.0,
        i_end=40,
        t_end=4.0,
        machine_type=MachineType.OTHER,
        user_type=UserType.UNREVIEWED,
    )
    object.__setattr__(event_gap, "_uuid", "uuid-gap")
    add_kym_event_rect(sample_plotly_dict, event_gap, time_range, row=2)
    
    shapes = sample_plotly_dict["layout"]["shapes"]
    assert len(shapes) == 2
    assert shapes[0]["fillcolor"] == "rgba(0, 255, 0, 0.5)"  # Green
    assert shapes[1]["fillcolor"] == "rgba(0, 0, 255, 0.5)"  # Blue


# ============================================================================
# Tests for delete_kym_event_rect
# ============================================================================


def test_delete_kym_event_rect_success(sample_plotly_dict: dict) -> None:
    """Test delete_kym_event_rect successfully deletes a rect."""
    # Add a shape first
    shape = {
        "type": "rect",
        "xref": "x2",
        "yref": "y2 domain",
        "name": "test-uuid-123",
        "x0": 1.0,
        "x1": 2.0,
    }
    sample_plotly_dict["layout"]["shapes"].append(shape)
    
    assert len(sample_plotly_dict["layout"]["shapes"]) == 1
    
    delete_kym_event_rect(sample_plotly_dict, "test-uuid-123", row=2)
    
    assert len(sample_plotly_dict["layout"]["shapes"]) == 0


def test_delete_kym_event_rect_not_found(sample_plotly_dict: dict) -> None:
    """Test delete_kym_event_rect handles missing UUID gracefully."""
    # Should not raise, just log error
    delete_kym_event_rect(sample_plotly_dict, "nonexistent-uuid", row=2)
    
    # Shapes should remain unchanged
    assert len(sample_plotly_dict["layout"]["shapes"]) == 0


def test_delete_kym_event_rect_preserves_other_shapes(sample_plotly_dict: dict) -> None:
    """Test delete_kym_event_rect only deletes the specified rect."""
    # Add multiple shapes
    shape1 = {
        "type": "rect",
        "xref": "x2",
        "yref": "y2 domain",
        "name": "uuid-1",
    }
    shape2 = {
        "type": "rect",
        "xref": "x2",
        "yref": "y2 domain",
        "name": "uuid-2",
    }
    shape3 = {
        "type": "line",  # Different type, should be preserved
        "xref": "x2",
        "yref": "y2",
    }
    sample_plotly_dict["layout"]["shapes"].extend([shape1, shape2, shape3])
    
    delete_kym_event_rect(sample_plotly_dict, "uuid-1", row=2)
    
    shapes = sample_plotly_dict["layout"]["shapes"]
    assert len(shapes) == 2
    assert shapes[0]["name"] == "uuid-2"
    assert shapes[1]["type"] == "line"


# ============================================================================
# Tests for move_kym_event_rect
# ============================================================================


def test_move_kym_event_rect_success(
    sample_plotly_dict: dict, sample_velocity_event: VelocityEvent
) -> None:
    """Test move_kym_event_rect successfully updates coordinates."""
    time_range = (0.0, 10.0)
    
    # Add event first
    add_kym_event_rect(sample_plotly_dict, sample_velocity_event, time_range, row=2)
    
    # Update event coordinates
    updated_event = VelocityEvent(
        event_type="baseline_drop",
        i_start=15,
        t_start=3.0,  # Changed
        i_end=25,
        t_end=4.0,  # Changed
        machine_type=MachineType.STALL_CANDIDATE,
        user_type=UserType.UNREVIEWED,
    )
    object.__setattr__(updated_event, "_uuid", "test-event-uuid-123")
    
    move_kym_event_rect(sample_plotly_dict, updated_event, time_range, row=2)
    
    shape = sample_plotly_dict["layout"]["shapes"][0]
    assert shape["x0"] == 3.0
    assert shape["x1"] == 4.0
    # Other properties should be preserved
    assert shape["name"] == "test-event-uuid-123"
    assert shape["fillcolor"] == "rgba(255, 0, 0, 0.5)"


def test_move_kym_event_rect_not_found(
    sample_plotly_dict: dict, sample_velocity_event: VelocityEvent
) -> None:
    """Test move_kym_event_rect handles missing UUID gracefully."""
    time_range = (0.0, 10.0)
    
    # Should not raise, just log error
    move_kym_event_rect(sample_plotly_dict, sample_velocity_event, time_range, row=2)
    
    # No shapes should be added
    assert len(sample_plotly_dict["layout"]["shapes"]) == 0


def test_move_kym_event_rect_no_uuid(
    sample_plotly_dict: dict, sample_velocity_event: VelocityEvent
) -> None:
    """Test move_kym_event_rect fails when event has no UUID."""
    time_range = (0.0, 10.0)
    
    # Add event first
    add_kym_event_rect(sample_plotly_dict, sample_velocity_event, time_range, row=2)
    
    # Remove UUID
    object.__setattr__(sample_velocity_event, "_uuid", None)
    
    # Should not update
    move_kym_event_rect(sample_plotly_dict, sample_velocity_event, time_range, row=2)
    
    # Original coordinates should remain
    shape = sample_plotly_dict["layout"]["shapes"][0]
    assert shape["x0"] == 1.0
    assert shape["x1"] == 2.0


# ============================================================================
# Tests for clear_kym_event_rects
# ============================================================================


def test_clear_kym_event_rects_success(sample_plotly_dict: dict) -> None:
    """Test clear_kym_event_rects removes all kym event rects."""
    # Add multiple kym event rects
    for i in range(3):
        shape = {
            "type": "rect",
            "xref": "x2",
            "yref": "y2 domain",
            "name": f"uuid-{i}",
        }
        sample_plotly_dict["layout"]["shapes"].append(shape)
    
    # Add a non-event rect (no name)
    other_rect = {
        "type": "rect",
        "xref": "x2",
        "yref": "y2 domain",
        # No name - not a kym event rect
    }
    sample_plotly_dict["layout"]["shapes"].append(other_rect)
    
    # Add a line (different type)
    line = {
        "type": "line",
        "xref": "x2",
        "yref": "y2",
    }
    sample_plotly_dict["layout"]["shapes"].append(line)
    
    clear_kym_event_rects(sample_plotly_dict, row=2)
    
    shapes = sample_plotly_dict["layout"]["shapes"]
    assert len(shapes) == 2  # Only other_rect and line should remain
    assert shapes[0] == other_rect
    assert shapes[1] == line


def test_clear_kym_event_rects_different_row(sample_plotly_dict: dict) -> None:
    """Test clear_kym_event_rects only clears rects in specified row."""
    # Add rects in row 2
    shape_row2 = {
        "type": "rect",
        "xref": "x2",
        "yref": "y2 domain",
        "name": "uuid-row2",
    }
    sample_plotly_dict["layout"]["shapes"].append(shape_row2)
    
    # Add rect in row 1
    shape_row1 = {
        "type": "rect",
        "xref": "x",
        "yref": "y domain",
        "name": "uuid-row1",
    }
    sample_plotly_dict["layout"]["shapes"].append(shape_row1)
    
    clear_kym_event_rects(sample_plotly_dict, row=2)
    
    shapes = sample_plotly_dict["layout"]["shapes"]
    assert len(shapes) == 1
    assert shapes[0]["name"] == "uuid-row1"  # Row 1 rect should remain


def test_clear_kym_event_rects_empty_shapes(sample_plotly_dict: dict) -> None:
    """Test clear_kym_event_rects handles empty shapes list."""
    clear_kym_event_rects(sample_plotly_dict, row=2)
    
    # Should not raise
    assert len(sample_plotly_dict["layout"]["shapes"]) == 0


# ============================================================================
# Tests for select_kym_event_rect
# ============================================================================


def test_select_kym_event_rect_selects_one(
    sample_plotly_dict: dict, sample_velocity_event: VelocityEvent
) -> None:
    """Test select_kym_event_rect selects specified event and deselects others."""
    time_range = (0.0, 10.0)
    
    # Add multiple events
    event1 = VelocityEvent(
        event_type="baseline_drop",
        i_start=10,
        t_start=1.0,
        i_end=20,
        t_end=2.0,
        machine_type=MachineType.STALL_CANDIDATE,
        user_type=UserType.UNREVIEWED,
    )
    object.__setattr__(event1, "_uuid", "uuid-1")
    
    event2 = VelocityEvent(
        event_type="baseline_rise",
        i_start=30,
        t_start=3.0,
        i_end=40,
        t_end=4.0,
        machine_type=MachineType.OTHER,
        user_type=UserType.UNREVIEWED,
    )
    object.__setattr__(event2, "_uuid", "uuid-2")
    
    add_kym_event_rect(sample_plotly_dict, event1, time_range, row=2)
    add_kym_event_rect(sample_plotly_dict, event2, time_range, row=2)
    
    # Select event1
    select_kym_event_rect(sample_plotly_dict, event1, row=2)
    
    shapes = sample_plotly_dict["layout"]["shapes"]
    # event1 should be selected (yellow outline)
    assert shapes[0]["line"]["color"] == "yellow"
    assert shapes[0]["line"]["width"] == 2
    # event2 should be deselected (no outline)
    assert shapes[1].get("line", {}).get("width", 0) == 0


def test_select_kym_event_rect_deselects_all(
    sample_plotly_dict: dict, sample_velocity_event: VelocityEvent
) -> None:
    """Test select_kym_event_rect with None deselects all events."""
    time_range = (0.0, 10.0)
    
    # Add event and select it
    add_kym_event_rect(sample_plotly_dict, sample_velocity_event, time_range, row=2)
    select_kym_event_rect(sample_plotly_dict, sample_velocity_event, row=2)
    
    # Verify it's selected
    shape = sample_plotly_dict["layout"]["shapes"][0]
    assert shape["line"]["color"] == "yellow"
    
    # Deselect all
    select_kym_event_rect(sample_plotly_dict, None, row=2)
    
    # Should be deselected
    shape = sample_plotly_dict["layout"]["shapes"][0]
    assert shape.get("line", {}).get("width", 0) == 0


def test_select_kym_event_rect_dash_for_no_t_peak(
    sample_plotly_dict: dict,
) -> None:
    """Test select_kym_event_rect uses dotted line for events with no t_peak (e.g. user-added)."""
    time_range = (0.0, 10.0)

    # Event with t_end but no t_peak (user-added style) - rect is drawn via t_end fallback
    event = VelocityEvent(
        event_type="User Added",
        i_start=10,
        t_start=1.0,
        i_peak=None,
        t_peak=None,
        i_end=20,
        t_end=2.0,
        machine_type=MachineType.OTHER,
        user_type=UserType.UNREVIEWED,
    )
    object.__setattr__(event, "_uuid", "uuid-no-peak")

    add_kym_event_rect(sample_plotly_dict, event, time_range, row=2)
    select_kym_event_rect(sample_plotly_dict, event, row=2)

    shape = sample_plotly_dict["layout"]["shapes"][0]
    assert shape["line"]["color"] == "yellow"
    assert shape["line"]["width"] == 2
    assert shape["line"]["dash"] == "dot"  # Dotted when t_peak is None (20260217_fix_t_peak)


def test_select_kym_event_rect_ignores_different_row(
    sample_plotly_dict: dict, sample_velocity_event: VelocityEvent
) -> None:
    """Test select_kym_event_rect only affects rects in specified row."""
    time_range = (0.0, 10.0)
    
    # Add event in row 2
    add_kym_event_rect(sample_plotly_dict, sample_velocity_event, time_range, row=2)
    
    # Add shape in row 1 (different row)
    shape_row1 = {
        "type": "rect",
        "xref": "x",
        "yref": "y domain",
        "name": "uuid-row1",
        "line": {"width": 0},
    }
    sample_plotly_dict["layout"]["shapes"].append(shape_row1)
    
    # Select event in row 2
    select_kym_event_rect(sample_plotly_dict, sample_velocity_event, row=2)
    
    shapes = sample_plotly_dict["layout"]["shapes"]
    # Row 2 event should be selected
    assert shapes[0]["line"]["color"] == "yellow"
    # Row 1 shape should be unchanged
    assert shapes[1]["line"]["width"] == 0


def test_select_kym_event_rect_no_uuid(
    sample_plotly_dict: dict, sample_velocity_event: VelocityEvent
) -> None:
    """Test select_kym_event_rect handles event with no UUID."""
    time_range = (0.0, 10.0)
    
    # Add event first
    add_kym_event_rect(sample_plotly_dict, sample_velocity_event, time_range, row=2)
    
    # Remove UUID
    object.__setattr__(sample_velocity_event, "_uuid", None)
    
    # Should deselect all (treats as None)
    select_kym_event_rect(sample_plotly_dict, sample_velocity_event, row=2)
    
    shape = sample_plotly_dict["layout"]["shapes"][0]
    assert shape.get("line", {}).get("width", 0) == 0
