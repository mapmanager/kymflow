"""Phase 5/6 unit tests for ImageLineViewerV2View: reset_zoom, scroll_x, set_event_filter, ROI edit."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from kymflow.gui_v2.events import EditRoi, ROISelection, SelectionOrigin
from .test_nicewidgets_adapter import _make_synthetic_kym
from kymflow.gui_v2.views.image_line_viewer_v2_view import (
    ImageLineViewerV2View,
    _region_of_interest_to_roi_bounds,
)


@pytest.fixture
def v2_view() -> ImageLineViewerV2View:
    """Create ImageLineViewerV2View for testing (no render)."""
    return ImageLineViewerV2View()


def test_reset_zoom_calls_autorange_on_both_widgets(v2_view: ImageLineViewerV2View) -> None:
    """reset_zoom delegates to combined widget reset_view()."""
    mock_combined = MagicMock()
    v2_view._combined = mock_combined

    v2_view.reset_zoom()

    mock_combined.reset_view.assert_called_once()


def test_reset_zoom_no_op_when_widgets_none(v2_view: ImageLineViewerV2View) -> None:
    """reset_zoom is a no-op when the combined widget is not initialized."""
    v2_view._combined = None
    v2_view.reset_zoom()


def test_set_event_filter_stores_filter_and_refreshes(v2_view: ImageLineViewerV2View) -> None:
    """set_event_filter stores filter dict and triggers _update_events_for_current_roi."""
    filter_dict = {"User Added": True, "Auto Detected": False}
    with patch.object(v2_view, "_update_events_for_current_roi") as mock_refresh:
        v2_view.set_event_filter(filter_dict)

    assert v2_view._event_filter == filter_dict
    mock_refresh.assert_called_once()


def test_set_event_filter_none(v2_view: ImageLineViewerV2View) -> None:
    """set_event_filter accepts None to clear filter."""
    v2_view._event_filter = {"User Added": True}
    with patch.object(v2_view, "_update_events_for_current_roi"):
        v2_view.set_event_filter(None)

    assert v2_view._event_filter is None


def test_scroll_x_no_op_when_widgets_none(v2_view: ImageLineViewerV2View) -> None:
    """scroll_x does not crash when the combined widget is not initialized."""
    v2_view._combined = None
    v2_view._line_plot_widget = None
    v2_view._image_roi_widget = None
    v2_view.scroll_x("prev")
    v2_view.scroll_x("next")


def test_scroll_x_no_op_when_no_range(v2_view: ImageLineViewerV2View) -> None:
    """scroll_x is no-op when the figure has no xaxis range."""
    mock_combined = MagicMock()
    mock_combined.plot_dict = {"layout": {}}
    v2_view._combined = mock_combined
    v2_view._current_file = MagicMock()
    v2_view._current_roi_id = 1
    v2_view._current_file.get_kym_analysis.return_value = MagicMock(
        get_time_bounds=MagicMock(return_value=(0.0, 10.0))
    )

    v2_view._scroll_x_impl("prev")
    v2_view._scroll_x_impl("next")

    mock_combined.set_x_axis_range_fast.assert_not_called()


def test_scroll_x_prev_shifts_window_left(v2_view: ImageLineViewerV2View) -> None:
    """scroll_x('prev') shifts window left via combined fast x-range API."""
    mock_combined = MagicMock()
    mock_combined.plot_dict = {
        "layout": {
            "xaxis": {"range": [2.0, 5.0]},
        },
    }
    v2_view._combined = mock_combined
    v2_view._current_file = MagicMock()
    v2_view._current_roi_id = 1
    mock_analysis = MagicMock()
    mock_analysis.get_time_bounds.return_value = (0.0, 10.0)
    v2_view._current_file.get_kym_analysis.return_value = mock_analysis

    v2_view._scroll_x_impl("prev")

    # Window was [2, 5], width=3. Prev -> new_min=max(0, -1)=-1... no, new_min=max(0, 2-3)=max(0,-1)=0
    # new_max = 0+3=3, so range [0, 3]
    mock_combined.set_x_axis_range_fast.assert_called_once_with(0.0, 3.0)


def test_scroll_x_next_shifts_window_right(v2_view: ImageLineViewerV2View) -> None:
    """scroll_x('next') shifts the x-axis window right."""
    mock_combined = MagicMock()
    mock_combined.plot_dict = {
        "layout": {
            "xaxis": {"range": [2.0, 5.0]},
        },
    }
    v2_view._combined = mock_combined
    v2_view._current_file = MagicMock()
    v2_view._current_roi_id = 1
    mock_analysis = MagicMock()
    mock_analysis.get_time_bounds.return_value = (0.0, 10.0)
    v2_view._current_file.get_kym_analysis.return_value = mock_analysis

    v2_view._scroll_x_impl("next")

    # Window [2, 5], width=3. Next -> [5, 8]
    mock_combined.set_x_axis_range_fast.assert_called_once_with(5.0, 8.0)


def test_scroll_x_next_clamps_at_right_edge(v2_view: ImageLineViewerV2View) -> None:
    """scroll_x('next') clamps when window would exceed time_max."""
    mock_combined = MagicMock()
    mock_combined.plot_dict = {
        "layout": {
            "xaxis": {"range": [5.0, 10.0]},
        },
    }
    v2_view._combined = mock_combined
    v2_view._current_file = MagicMock()
    v2_view._current_roi_id = 1
    mock_analysis = MagicMock()
    mock_analysis.get_time_bounds.return_value = (0.0, 10.0)
    v2_view._current_file.get_kym_analysis.return_value = mock_analysis

    v2_view._scroll_x_impl("next")

    # Window [5, 10], width=5. Next would be [10, 15] but time_max=10 -> clamp to [5, 10]
    mock_combined.set_x_axis_range_fast.assert_called_once_with(5.0, 10.0)


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


def test_v2_view_accepts_on_edit_roi() -> None:
    """Phase 6: View accepts on_edit_roi callback and stores it."""
    emitted = []
    view = ImageLineViewerV2View(on_edit_roi=lambda e: emitted.append(e))
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
    view = ImageLineViewerV2View()
    assert view._suppress_roi_select_emit is False


def test_refresh_rois_for_current_file_converts_rectroi_to_region_of_interest(
    v2_view: ImageLineViewerV2View,
) -> None:
    """refresh_rois_for_current_file passes RegionOfInterest objects to widget."""
    from nicewidgets.image_line_widget.models import RegionOfInterest
    # Build synthetic KymImage with one RectROI using shared helper
    kym = _make_synthetic_kym(rois=[(1, 5, 2, 7)])

    v2_view._current_file = kym
    mock_widget = MagicMock()
    v2_view._image_roi_widget = mock_widget

    v2_view.refresh_rois_for_current_file()

    mock_widget.set_rois.assert_called_once()
    (rois_dict,) = mock_widget.set_rois.call_args.args
    assert isinstance(rois_dict, dict)
    assert rois_dict, "Expected at least one ROI in mapping"
    for name, roi in rois_dict.items():
        assert isinstance(name, str)
        assert isinstance(roi, RegionOfInterest)
        assert roi.r0 == 1
        assert roi.r1 == 5
        assert roi.c0 == 2
        assert roi.c1 == 7


def test_refresh_rois_for_current_file_preserves_selection(
    v2_view: ImageLineViewerV2View,
) -> None:
    """refresh_rois_for_current_file sets selected ROI when current id exists."""
    kym = _make_synthetic_kym(rois=[(0, 3, 0, 3)])

    v2_view._current_file = kym
    v2_view._current_roi_id = 1
    mock_widget = MagicMock()
    v2_view._image_roi_widget = mock_widget

    v2_view.refresh_rois_for_current_file()

    mock_widget.set_selected_roi.assert_called_once_with("1")


def test_refresh_rois_for_current_file_no_file_clears_widget(
    v2_view: ImageLineViewerV2View,
) -> None:
    """refresh_rois_for_current_file clears ROIs when no current file."""
    mock_widget = MagicMock()
    v2_view._image_roi_widget = mock_widget
    v2_view._current_file = None

    v2_view.refresh_rois_for_current_file()

    mock_widget.set_rois.assert_called_once_with({})
    mock_widget.set_selected_roi.assert_called_once_with(None)
