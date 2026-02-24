"""Tests for ImageLineViewerView - event filter functionality."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import numpy as np
import pytest

from kymflow.gui_v2.views.image_line_viewer_view import ImageLineViewerView
from kymflow.core.analysis.velocity_events.velocity_events import (
    VelocityEvent,
    MachineType,
    UserType,
)


@pytest.fixture
def image_line_viewer_view() -> ImageLineViewerView:
    """Create an ImageLineViewerView instance for testing."""
    return ImageLineViewerView(
        on_kym_event_x_range=lambda e: None,
        on_set_roi_bounds=lambda e: None,
    )


def test_event_filter_initialization(image_line_viewer_view: ImageLineViewerView) -> None:
    """Test that event filter is initialized with default values."""
    # Event filter is initialized with default dict, not None
    assert image_line_viewer_view._event_filter is not None
    assert isinstance(image_line_viewer_view._event_filter, dict)
    assert image_line_viewer_view._event_filter == {
        "baseline_drop": True,
        "baseline_rise": True,
        "nan_gap": False,
        "zero_gap": True,
        "User Added": True,
    }


def test_set_event_filter_stores_filter(image_line_viewer_view: ImageLineViewerView) -> None:
    """Test that set_event_filter stores the filter state."""
    filter_dict = {
        "baseline_drop": True,
        "baseline_rise": False,
        "nan_gap": True,
        "zero_gap": False,
        "User Added": True,
    }

    # Mock _render_combined to avoid actual rendering
    with patch.object(image_line_viewer_view, "_render_combined") as mock_render:
        image_line_viewer_view.set_event_filter(filter_dict)

        # Verify filter was stored
        assert image_line_viewer_view._event_filter == filter_dict

        # Verify _render_combined was called to refresh plot
        assert mock_render.called


def test_set_event_filter_with_none(image_line_viewer_view: ImageLineViewerView) -> None:
    """Test that set_event_filter accepts None to clear filter."""
    # Set a filter first
    filter_dict = {"baseline_drop": True}
    image_line_viewer_view._event_filter = filter_dict

    # Mock _render_combined
    with patch.object(image_line_viewer_view, "_render_combined") as mock_render:
        image_line_viewer_view.set_event_filter(None)

        # Verify filter was cleared
        assert image_line_viewer_view._event_filter is None

        # Verify _render_combined was called
        assert mock_render.called


def test_render_combined_passes_event_filter(image_line_viewer_view: ImageLineViewerView) -> None:
    """Test that _render_combined passes event_filter to plot function."""
    filter_dict = {
        "baseline_drop": True,
        "baseline_rise": False,
    }
    image_line_viewer_view._event_filter = filter_dict

    # Mock plot element
    mock_plot = MagicMock()
    image_line_viewer_view._plot = mock_plot

    # Mock file with required attributes
    mock_file = MagicMock()
    mock_file.rois.numRois.return_value = 0
    image_line_viewer_view._current_file = mock_file

    # Mock plot_image_line_plotly_v3
    with patch("kymflow.gui_v2.views.image_line_viewer_view.plot_image_line_plotly_v3") as mock_plot_func:
        mock_fig = MagicMock()
        mock_plot_func.return_value = mock_fig

        image_line_viewer_view._render_combined()

        # Verify plot function was called with event_filter
        assert mock_plot_func.called
        call_kwargs = mock_plot_func.call_args[1]
        assert "event_filter" in call_kwargs
        assert call_kwargs["event_filter"] == filter_dict


def test_set_event_filter_uses_crud(image_line_viewer_view: ImageLineViewerView) -> None:
    """Test that set_event_filter uses CRUD operations when _current_figure_dict exists."""
    # Setup: Create a valid figure dict with existing shapes
    image_line_viewer_view._current_figure_dict = {
        "layout": {
            "shapes": [
                {
                    "type": "rect",
                    "xref": "x2",
                    "yref": "y2 domain",
                    "name": "event-uuid-1",
                    "x0": 1.0,
                    "x1": 2.0,
                },
                {
                    "type": "rect",
                    "xref": "x2",
                    "yref": "y2 domain",
                    "name": "event-uuid-2",
                    "x0": 3.0,
                    "x1": 4.0,
                },
            ],
        },
        "data": [],
    }
    
    # Setup: Mock file and analysis
    mock_file = MagicMock()
    mock_analysis = MagicMock()
    mock_file.get_kym_analysis.return_value = mock_analysis
    image_line_viewer_view._current_file = mock_file
    image_line_viewer_view._current_roi_id = 1
    image_line_viewer_view._selected_event_id = None
    
    # Create sample events
    event1 = VelocityEvent(
        event_type="baseline_drop",  # EventType is a Literal, use string directly
        i_start=10,
        t_start=1.0,
        i_end=20,
        t_end=2.0,
        machine_type=MachineType.STALL_CANDIDATE,
        user_type=UserType.UNREVIEWED,
    )
    object.__setattr__(event1, "_uuid", "event-uuid-1")
    
    event2 = VelocityEvent(
        event_type="nan_gap",  # EventType is a Literal, use string directly
        i_start=30,
        t_start=3.0,
        i_end=40,
        t_end=4.0,
        machine_type=MachineType.OTHER,
        user_type=UserType.UNREVIEWED,
    )
    object.__setattr__(event2, "_uuid", "event-uuid-2")
    
    # Setup analysis mocks
    mock_analysis.has_analysis.return_value = True
    mock_analysis.get_analysis_value.return_value = np.array([0.0, 1.0, 2.0, 3.0, 4.0, 5.0])
    mock_analysis.get_time_bounds.return_value = (0.0, 5.0)  # Return tuple of (time_min, time_max)
    mock_analysis.get_velocity_events_filtered.return_value = [event1]  # Only baseline_drop
    
    # Mock ui_plotly_update_figure
    image_line_viewer_view.ui_plotly_update_figure = MagicMock()
    
    # Set filter (only baseline_drop visible)
    filter_dict = {
        "baseline_drop": True,
        "baseline_rise": False,
        "nan_gap": False,
    }
    
    image_line_viewer_view.set_event_filter(filter_dict)
    
    # Verify filter was stored
    assert image_line_viewer_view._event_filter == filter_dict
    
    # Verify CRUD was used (not full render)
    # Check that shapes were cleared and re-added
    shapes = image_line_viewer_view._current_figure_dict["layout"]["shapes"]
    # Should have 1 shape (only baseline_drop event)
    assert len(shapes) == 1
    assert shapes[0]["name"] == "event-uuid-1"
    
    # Verify ui_plotly_update_figure was called
    image_line_viewer_view.ui_plotly_update_figure.assert_called_once()


def test_set_event_filter_fallback_when_dict_none(image_line_viewer_view: ImageLineViewerView) -> None:
    """Test that set_event_filter falls back to _render_combined when _current_figure_dict is None."""
    # Setup
    image_line_viewer_view._current_figure_dict = None
    
    filter_dict = {"baseline_drop": True}
    
    # Mock _render_combined
    with patch.object(image_line_viewer_view, "_render_combined") as mock_render:
        image_line_viewer_view.set_event_filter(filter_dict)
        
        # Verify filter was stored
        assert image_line_viewer_view._event_filter == filter_dict
        
        # Verify fallback was used
        mock_render.assert_called_once()


def test_set_event_filter_deselects_when_filtered_out(image_line_viewer_view: ImageLineViewerView) -> None:
    """Test that set_event_filter deselects when selected event is filtered out."""
    # Setup: Create a valid figure dict
    image_line_viewer_view._current_figure_dict = {
        "layout": {
            "shapes": [
                {
                    "type": "rect",
                    "xref": "x2",
                    "yref": "y2 domain",
                    "name": "event-uuid-1",
                    "x0": 1.0,
                    "x1": 2.0,
                    "line": {"color": "yellow", "width": 2},  # Selected
                },
            ],
        },
        "data": [],
    }
    
    # Setup: Mock file and analysis
    mock_file = MagicMock()
    mock_analysis = MagicMock()
    mock_file.get_kym_analysis.return_value = mock_analysis
    image_line_viewer_view._current_file = mock_file
    image_line_viewer_view._current_roi_id = 1
    image_line_viewer_view._selected_event_id = "event-uuid-1"  # Selected event
    
    # Setup analysis mocks - no events returned (all filtered out)
    mock_analysis.has_analysis.return_value = True
    mock_analysis.get_analysis_value.return_value = np.array([0.0, 1.0, 2.0, 3.0, 4.0, 5.0])
    mock_analysis.get_time_bounds.return_value = (0.0, 5.0)  # Return tuple of (time_min, time_max)
    mock_analysis.get_velocity_events_filtered.return_value = []  # All filtered out
    
    # Mock ui_plotly_update_figure
    image_line_viewer_view.ui_plotly_update_figure = MagicMock()
    
    # Set filter that excludes the selected event
    filter_dict = {
        "baseline_drop": False,  # Excludes event-uuid-1
        "baseline_rise": True,
    }
    
    image_line_viewer_view.set_event_filter(filter_dict)
    
    # Verify shapes were cleared
    shapes = image_line_viewer_view._current_figure_dict["layout"]["shapes"]
    assert len(shapes) == 0
    
    # Verify ui_plotly_update_figure was called
    image_line_viewer_view.ui_plotly_update_figure.assert_called_once()


def test_scroll_x_no_op_when_no_figure_dict(image_line_viewer_view: ImageLineViewerView) -> None:
    """Test that scroll_x is a no-op when _current_figure_dict is None."""
    image_line_viewer_view._current_figure_dict = None
    image_line_viewer_view._plot = MagicMock()
    image_line_viewer_view.ui_plotly_update_figure = MagicMock()
    image_line_viewer_view.scroll_x("prev")
    image_line_viewer_view.scroll_x("next")
    # No exception; ui_plotly_update_figure not called because _scroll_x_impl returns early
    image_line_viewer_view.ui_plotly_update_figure.assert_not_called()


def test_scroll_x_prev_shifts_window_left(image_line_viewer_view: ImageLineViewerView) -> None:
    """Test that scroll_x('prev') shifts the x-axis window left by one window width."""
    image_line_viewer_view._current_figure_dict = {
        "layout": {
            "xaxis": {"range": [2.0, 5.0]},
            "xaxis2": {"range": [2.0, 5.0]},
        },
    }
    image_line_viewer_view._plot = MagicMock()
    image_line_viewer_view._current_file = MagicMock()
    image_line_viewer_view._current_roi_id = 1
    mock_analysis = MagicMock()
    mock_analysis.get_time_bounds.return_value = (0.0, 10.0)
    image_line_viewer_view._current_file.get_kym_analysis.return_value = mock_analysis
    image_line_viewer_view.ui_plotly_update_figure = MagicMock()

    image_line_viewer_view._scroll_x_impl("prev")

    # Window was [2, 5], width=3. Prev -> [2-3, 2] = [-1, 2], clamped to [0, 3]
    layout = image_line_viewer_view._current_figure_dict["layout"]
    assert layout["xaxis"]["range"] == [0.0, 3.0]
    assert layout["xaxis2"]["range"] == [0.0, 3.0]
    image_line_viewer_view.ui_plotly_update_figure.assert_called_once()


def test_scroll_x_next_shifts_window_right(image_line_viewer_view: ImageLineViewerView) -> None:
    """Test that scroll_x('next') shifts the x-axis window right by one window width."""
    image_line_viewer_view._current_figure_dict = {
        "layout": {
            "xaxis": {"range": [2.0, 5.0]},
            "xaxis2": {"range": [2.0, 5.0]},
        },
    }
    image_line_viewer_view._plot = MagicMock()
    image_line_viewer_view._current_file = MagicMock()
    image_line_viewer_view._current_roi_id = 1
    mock_analysis = MagicMock()
    mock_analysis.get_time_bounds.return_value = (0.0, 10.0)
    image_line_viewer_view._current_file.get_kym_analysis.return_value = mock_analysis
    image_line_viewer_view.ui_plotly_update_figure = MagicMock()

    image_line_viewer_view._scroll_x_impl("next")

    # Window was [2, 5], width=3. Next -> [5, 8]
    layout = image_line_viewer_view._current_figure_dict["layout"]
    assert layout["xaxis"]["range"] == [5.0, 8.0]
    assert layout["xaxis2"]["range"] == [5.0, 8.0]
    image_line_viewer_view.ui_plotly_update_figure.assert_called_once()


def test_scroll_x_next_clamps_at_right_edge(image_line_viewer_view: ImageLineViewerView) -> None:
    """Test that scroll_x('next') clamps when the new window would go past time_max."""
    image_line_viewer_view._current_figure_dict = {
        "layout": {
            "xaxis": {"range": [5.0, 10.0]},
            "xaxis2": {"range": [5.0, 10.0]},
        },
    }
    image_line_viewer_view._plot = MagicMock()
    image_line_viewer_view._current_file = MagicMock()
    image_line_viewer_view._current_roi_id = 1
    mock_analysis = MagicMock()
    mock_analysis.get_time_bounds.return_value = (0.0, 10.0)
    image_line_viewer_view._current_file.get_kym_analysis.return_value = mock_analysis
    image_line_viewer_view.ui_plotly_update_figure = MagicMock()

    image_line_viewer_view._scroll_x_impl("next")

    # Window was [5, 10], width=5. Next -> [10, 15] but time_max=10, so clamp to [5, 10]
    layout = image_line_viewer_view._current_figure_dict["layout"]
    assert layout["xaxis"]["range"] == [5.0, 10.0]
    assert layout["xaxis2"]["range"] == [5.0, 10.0]
