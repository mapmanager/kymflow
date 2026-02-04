"""Tests for ImageLineViewerView - event filter functionality."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from kymflow.gui_v2.views.image_line_viewer_view import ImageLineViewerView


@pytest.fixture
def image_line_viewer_view() -> ImageLineViewerView:
    """Create an ImageLineViewerView instance for testing."""
    return ImageLineViewerView(
        on_kym_event_x_range=lambda e: None,
        on_set_roi_bounds=lambda e: None,
    )


def test_event_filter_initialization(image_line_viewer_view: ImageLineViewerView) -> None:
    """Test that event filter is initialized as None."""
    assert image_line_viewer_view._event_filter is None


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
