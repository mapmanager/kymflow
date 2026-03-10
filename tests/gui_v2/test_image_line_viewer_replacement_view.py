"""Phase 5/6 unit tests for ImageLineViewerReplacementView: apply_filters, reset_zoom, scroll_x, set_event_filter, ROI edit."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from kymflow.gui_v2.events import EditRoi, SelectionOrigin
from kymflow.gui_v2.views.image_line_viewer_replacement_view import (
    ImageLineViewerReplacementView,
    _region_of_interest_to_roi_bounds,
)


@pytest.fixture
def replacement_view() -> ImageLineViewerReplacementView:
    """Create ImageLineViewerReplacementView for testing (no render)."""
    return ImageLineViewerReplacementView()


def test_apply_filters_stores_state_and_refreshes(replacement_view: ImageLineViewerReplacementView) -> None:
    """apply_filters updates _remove_outliers, _median_filter and triggers _update_line_for_current_roi."""
    with patch.object(replacement_view, "_update_line_for_current_roi") as mock_refresh:
        replacement_view.apply_filters(remove_outliers=True, median_filter=True)

    assert replacement_view._remove_outliers is True
    assert replacement_view._median_filter is True
    mock_refresh.assert_called_once()


def test_apply_filters_clear_both(replacement_view: ImageLineViewerReplacementView) -> None:
    """apply_filters with both False clears filter state."""
    replacement_view._remove_outliers = True
    replacement_view._median_filter = True
    with patch.object(replacement_view, "_refresh_from_state"):
        replacement_view.apply_filters(remove_outliers=False, median_filter=False)

    assert replacement_view._remove_outliers is False
    assert replacement_view._median_filter is False


def test_reset_zoom_calls_autorange_on_both_widgets(replacement_view: ImageLineViewerReplacementView) -> None:
    """reset_zoom calls set_x_axis_autorange on ImageRoiWidget and LinePlotWidget when present."""
    mock_img = MagicMock()
    mock_line = MagicMock()
    replacement_view._image_roi_widget = mock_img
    replacement_view._line_plot_widget = mock_line

    replacement_view.reset_zoom()

    mock_img.set_x_axis_autorange.assert_called_once()
    mock_line.set_x_axis_autorange.assert_called_once()


def test_reset_zoom_no_op_when_widgets_none(replacement_view: ImageLineViewerReplacementView) -> None:
    """reset_zoom does not crash when widgets are None."""
    replacement_view._image_roi_widget = None
    replacement_view._line_plot_widget = None
    replacement_view.reset_zoom()  # no exception


def test_set_event_filter_stores_filter_and_refreshes(replacement_view: ImageLineViewerReplacementView) -> None:
    """set_event_filter stores filter dict and triggers _update_events_for_current_roi."""
    filter_dict = {"User Added": True, "Auto Detected": False}
    with patch.object(replacement_view, "_update_events_for_current_roi") as mock_refresh:
        replacement_view.set_event_filter(filter_dict)

    assert replacement_view._event_filter == filter_dict
    mock_refresh.assert_called_once()


def test_set_event_filter_none(replacement_view: ImageLineViewerReplacementView) -> None:
    """set_event_filter accepts None to clear filter."""
    replacement_view._event_filter = {"User Added": True}
    with patch.object(replacement_view, "_update_events_for_current_roi"):
        replacement_view.set_event_filter(None)

    assert replacement_view._event_filter is None


def test_scroll_x_no_op_when_widgets_none(replacement_view: ImageLineViewerReplacementView) -> None:
    """scroll_x does not crash when widgets are None."""
    replacement_view._line_plot_widget = None
    replacement_view._image_roi_widget = None
    replacement_view.scroll_x("prev")
    replacement_view.scroll_x("next")


def test_scroll_x_no_op_when_no_range(replacement_view: ImageLineViewerReplacementView) -> None:
    """scroll_x is no-op when line plot has no xaxis range."""
    mock_line = MagicMock()
    mock_line.plot_dict = {"layout": {}}
    mock_img = MagicMock()
    replacement_view._line_plot_widget = mock_line
    replacement_view._image_roi_widget = mock_img
    replacement_view._current_file = MagicMock()
    replacement_view._current_roi_id = 1
    replacement_view._current_file.get_kym_analysis.return_value = MagicMock(
        get_time_bounds=MagicMock(return_value=(0.0, 10.0))
    )

    replacement_view._scroll_x_impl("prev")
    replacement_view._scroll_x_impl("next")

    mock_line.set_x_axis_range.assert_not_called()
    mock_img.set_x_axis_range.assert_not_called()


def test_scroll_x_prev_shifts_window_left(replacement_view: ImageLineViewerReplacementView) -> None:
    """scroll_x('prev') shifts the x-axis window left and updates both widgets."""
    mock_line = MagicMock()
    mock_line.plot_dict = {
        "layout": {
            "xaxis": {"range": [2.0, 5.0]},
        },
    }
    mock_img = MagicMock()
    replacement_view._line_plot_widget = mock_line
    replacement_view._image_roi_widget = mock_img
    replacement_view._current_file = MagicMock()
    replacement_view._current_roi_id = 1
    mock_analysis = MagicMock()
    mock_analysis.get_time_bounds.return_value = (0.0, 10.0)
    replacement_view._current_file.get_kym_analysis.return_value = mock_analysis

    replacement_view._scroll_x_impl("prev")

    # Window was [2, 5], width=3. Prev -> new_min=max(0, -1)=-1... no, new_min=max(0, 2-3)=max(0,-1)=0
    # new_max = 0+3=3, so range [0, 3]
    mock_line.set_x_axis_range.assert_called_once_with([0.0, 3.0])
    mock_img.set_x_axis_range.assert_called_once_with([0.0, 3.0])


def test_scroll_x_next_shifts_window_right(replacement_view: ImageLineViewerReplacementView) -> None:
    """scroll_x('next') shifts the x-axis window right."""
    mock_line = MagicMock()
    mock_line.plot_dict = {
        "layout": {
            "xaxis": {"range": [2.0, 5.0]},
        },
    }
    mock_img = MagicMock()
    replacement_view._line_plot_widget = mock_line
    replacement_view._image_roi_widget = mock_img
    replacement_view._current_file = MagicMock()
    replacement_view._current_roi_id = 1
    mock_analysis = MagicMock()
    mock_analysis.get_time_bounds.return_value = (0.0, 10.0)
    replacement_view._current_file.get_kym_analysis.return_value = mock_analysis

    replacement_view._scroll_x_impl("next")

    # Window [2, 5], width=3. Next -> [5, 8]
    mock_line.set_x_axis_range.assert_called_once_with([5.0, 8.0])
    mock_img.set_x_axis_range.assert_called_once_with([5.0, 8.0])


def test_scroll_x_next_clamps_at_right_edge(replacement_view: ImageLineViewerReplacementView) -> None:
    """scroll_x('next') clamps when window would exceed time_max."""
    mock_line = MagicMock()
    mock_line.plot_dict = {
        "layout": {
            "xaxis": {"range": [5.0, 10.0]},
        },
    }
    mock_img = MagicMock()
    replacement_view._line_plot_widget = mock_line
    replacement_view._image_roi_widget = mock_img
    replacement_view._current_file = MagicMock()
    replacement_view._current_roi_id = 1
    mock_analysis = MagicMock()
    mock_analysis.get_time_bounds.return_value = (0.0, 10.0)
    replacement_view._current_file.get_kym_analysis.return_value = mock_analysis

    replacement_view._scroll_x_impl("next")

    # Window [5, 10], width=5. Next would be [10, 15] but time_max=10 -> clamp to [5, 10]
    mock_line.set_x_axis_range.assert_called_once_with([5.0, 10.0])
    mock_img.set_x_axis_range.assert_called_once_with([5.0, 10.0])


# Phase 6: ROI edit
def test_region_of_interest_to_roi_bounds() -> None:
    """Phase 6: RegionOfInterest maps to RoiBounds (r0,r1=dim0, c0,c1=dim1)."""
    from nicewidgets.image_line_widget.models import RegionOfInterest

    roi = RegionOfInterest("ROI_1", 10, 100, 5, 50)
    bounds = _region_of_interest_to_roi_bounds(roi)
    assert bounds.dim0_start == 10
    assert bounds.dim0_stop == 100
    assert bounds.dim1_start == 5
    assert bounds.dim1_stop == 50


def test_region_of_interest_to_roi_bounds_normalizes_order() -> None:
    """Phase 6: Out-of-order r0>r1 or c0>c1 are normalized to min/max."""
    from nicewidgets.image_line_widget.models import RegionOfInterest

    roi = RegionOfInterest("ROI_0", 100, 10, 50, 5)
    bounds = _region_of_interest_to_roi_bounds(roi)
    assert bounds.dim0_start == 10
    assert bounds.dim0_stop == 100
    assert bounds.dim1_start == 5
    assert bounds.dim1_stop == 50


def test_replacement_view_accepts_on_edit_roi() -> None:
    """Phase 6: View accepts on_edit_roi callback and stores it."""
    emitted = []
    view = ImageLineViewerReplacementView(on_edit_roi=lambda e: emitted.append(e))
    assert view._on_edit_roi is not None
    # Simulate ROIEvent(UPDATE) flow: call on_edit_roi with EditRoi
    from kymflow.core.image_loaders.roi import RoiBounds

    view._on_edit_roi(
        EditRoi(
            roi_id=1,
            bounds=RoiBounds(10, 100, 5, 50),
            path="/some/path.tif",
            origin=SelectionOrigin.IMAGE_VIEWER,
            phase="intent",
        )
    )
    assert len(emitted) == 1
    assert emitted[0].roi_id == 1
    assert emitted[0].bounds.dim0_start == 10
    assert emitted[0].bounds.dim1_start == 5


def test_suppress_roi_select_emit_initialized_false() -> None:
    """Phase 6: _suppress_roi_select_emit starts False to allow user-initiated ROI selection."""
    view = ImageLineViewerReplacementView()
    assert view._suppress_roi_select_emit is False
