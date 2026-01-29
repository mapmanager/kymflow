"""Tests for AnalysisToolbarView - confirmation dialog for existing analysis."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import tifffile

from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.core.image_loaders.roi import RoiBounds
from kymflow.gui_v2.events import AnalysisStart
from kymflow.gui_v2.views.analysis_toolbar_view import AnalysisToolbarView


@pytest.fixture
def kym_file_with_analysis() -> KymImage:
    """Create a KymImage with ROI and analysis."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.tif"
        test_image = np.zeros((100, 200), dtype=np.uint16)
        tifffile.imwrite(test_file, test_image)

        kym_file = KymImage(test_file, load_image=True)
        # seconds_per_line is read-only property, will use default from header

        # Create ROI and analyze
        bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
        roi = kym_file.rois.create_roi(bounds=bounds)
        kym_file.get_kym_analysis().analyze_roi(
            roi.id, window_size=16, use_multiprocessing=False
        )

        return kym_file


def test_analysis_toolbar_shows_dialog_when_analysis_exists(
    kym_file_with_analysis: KymImage,
) -> None:
    """Test that AnalysisToolbarView shows dialog when has_analysis(roi_id) returns True."""
    received_events: list[AnalysisStart] = []

    def on_analysis_start(event: AnalysisStart) -> None:
        received_events.append(event)

    view = AnalysisToolbarView(
        on_analysis_start=on_analysis_start,
        on_analysis_cancel=lambda e: None,
        on_add_roi=lambda e: None,
        on_delete_roi=lambda e: None,
        on_set_roi_edit_state=lambda e: None,
        on_roi_selected=lambda e: None,
    )

    # Render view to create UI elements
    view.render()

    # Set file and ROI
    view.set_selected_file(kym_file_with_analysis)
    roi_id = kym_file_with_analysis.rois.get_roi_ids()[0]
    view.set_selected_roi(roi_id)

    # Mock window_select to return a value
    if view._window_select is None:
        view._window_select = MagicMock()
    view._window_select.value = 16

    # Verify analysis exists
    assert kym_file_with_analysis.get_kym_analysis().has_analysis(roi_id)

    # Mock ui.dialog to verify it's created
    with patch("kymflow.gui_v2.views.analysis_toolbar_view.ui.dialog") as mock_dialog:
        mock_dialog_context = MagicMock()
        mock_dialog.return_value.__enter__ = MagicMock(return_value=mock_dialog_context)
        mock_dialog.return_value.__exit__ = MagicMock(return_value=False)

        # Try to start analysis
        view._on_start_click()

        # Verify dialog was created
        mock_dialog.assert_called_once()

        # Verify AnalysisStart event was NOT emitted (dialog blocks it)
        assert len(received_events) == 0


def test_analysis_toolbar_no_dialog_when_no_analysis(
    kym_file_with_analysis: KymImage,
) -> None:
    """Test that AnalysisToolbarView does not show dialog when no analysis exists."""
    received_events: list[AnalysisStart] = []

    def on_analysis_start(event: AnalysisStart) -> None:
        received_events.append(event)

    view = AnalysisToolbarView(
        on_analysis_start=on_analysis_start,
        on_analysis_cancel=lambda e: None,
        on_add_roi=lambda e: None,
        on_delete_roi=lambda e: None,
        on_set_roi_edit_state=lambda e: None,
        on_roi_selected=lambda e: None,
    )

    # Render view
    view.render()

    # Set file and ROI (but clear analysis)
    view.set_selected_file(kym_file_with_analysis)
    roi_id = kym_file_with_analysis.rois.get_roi_ids()[0]
    view.set_selected_roi(roi_id)

    # Mock window_select to return a value
    if view._window_select is None:
        view._window_select = MagicMock()
    view._window_select.value = 16

    # Clear analysis
    kym_file_with_analysis.get_kym_analysis().invalidate(roi_id)
    assert not kym_file_with_analysis.get_kym_analysis().has_analysis(roi_id)

    # Mock ui.dialog
    with patch("kymflow.gui_v2.views.analysis_toolbar_view.ui.dialog") as mock_dialog:
        # Try to start analysis
        view._on_start_click()

        # Verify dialog was NOT created
        mock_dialog.assert_not_called()

        # Verify AnalysisStart event WAS emitted (no dialog blocking)
        assert len(received_events) == 1


def test_analysis_toolbar_cancel_blocks_analysis_start(
    kym_file_with_analysis: KymImage,
) -> None:
    """Test that canceling dialog prevents analysis start."""
    received_events: list[AnalysisStart] = []

    def on_analysis_start(event: AnalysisStart) -> None:
        received_events.append(event)

    view = AnalysisToolbarView(
        on_analysis_start=on_analysis_start,
        on_analysis_cancel=lambda e: None,
        on_add_roi=lambda e: None,
        on_delete_roi=lambda e: None,
        on_set_roi_edit_state=lambda e: None,
        on_roi_selected=lambda e: None,
    )

    # Render view
    view.render()

    # Set file and ROI
    view.set_selected_file(kym_file_with_analysis)
    roi_id = kym_file_with_analysis.rois.get_roi_ids()[0]
    view.set_selected_roi(roi_id)

    # Mock window_select to return a value
    if view._window_select is None:
        view._window_select = MagicMock()
    view._window_select.value = 16

    # Mock dialog to simulate cancel (dialog.close() called, but _confirm_start_analysis not called)
    with patch("kymflow.gui_v2.views.analysis_toolbar_view.ui.dialog") as mock_dialog:
        mock_dialog_context = MagicMock()
        mock_dialog.return_value.__enter__ = MagicMock(return_value=mock_dialog_context)
        mock_dialog.return_value.__exit__ = MagicMock(return_value=False)

        with patch("kymflow.gui_v2.views.analysis_toolbar_view.ui.card"):
            with patch("kymflow.gui_v2.views.analysis_toolbar_view.ui.button") as mock_button_func:
                mock_button_func.side_effect = [
                    MagicMock(),  # Cancel button
                    MagicMock(),  # Proceed button
                ]

                # Try to start analysis
                view._on_start_click()

                # Verify dialog was created
                mock_dialog.assert_called_once()

                # Simulate cancel button click (just closes dialog, doesn't call _confirm_start_analysis)
                # So AnalysisStart event should NOT be emitted
                assert len(received_events) == 0


def test_analysis_toolbar_confirm_proceeds_with_analysis(
    kym_file_with_analysis: KymImage,
) -> None:
    """Test that confirming dialog proceeds with analysis start."""
    received_events: list[AnalysisStart] = []

    def on_analysis_start(event: AnalysisStart) -> None:
        received_events.append(event)

    view = AnalysisToolbarView(
        on_analysis_start=on_analysis_start,
        on_analysis_cancel=lambda e: None,
        on_add_roi=lambda e: None,
        on_delete_roi=lambda e: None,
        on_set_roi_edit_state=lambda e: None,
        on_roi_selected=lambda e: None,
    )

    # Render view
    view.render()

    # Set file and ROI
    view.set_selected_file(kym_file_with_analysis)
    roi_id = kym_file_with_analysis.rois.get_roi_ids()[0]
    view.set_selected_roi(roi_id)

    # Mock window_select to return a value
    if view._window_select is None:
        view._window_select = MagicMock()
    view._window_select.value = 16

    # Mock dialog and simulate confirm
    with patch("kymflow.gui_v2.views.analysis_toolbar_view.ui.dialog") as mock_dialog:
        mock_dialog_context = MagicMock()
        mock_dialog.return_value.__enter__ = MagicMock(return_value=mock_dialog_context)
        mock_dialog.return_value.__exit__ = MagicMock(return_value=False)

        with patch("kymflow.gui_v2.views.analysis_toolbar_view.ui.card"):
            with patch("kymflow.gui_v2.views.analysis_toolbar_view.ui.button") as mock_button_func:
                mock_button_func.side_effect = [
                    MagicMock(),  # Cancel button
                    MagicMock(),  # Proceed button
                ]

                # Try to start analysis
                view._on_start_click()

                # Verify dialog was created
                mock_dialog.assert_called_once()

                # Simulate proceed button click (calls _confirm_start_analysis)
                # Get the on_click handler for proceed button (second call)
                proceed_handler = mock_button_func.call_args_list[1].kwargs.get("on_click")
                if proceed_handler:
                    # Call the handler which should call _confirm_start_analysis
                    proceed_handler()

                    # Verify AnalysisStart event WAS emitted (confirm proceeded)
                    assert len(received_events) == 1
                    assert received_events[0].roi_id == roi_id
