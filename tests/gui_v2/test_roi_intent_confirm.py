"""Tests for ROI delete/edit confirmation and analysis clearing (gui_v2 Phase 5)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np

from kymflow.core.image_loaders.roi import RoiBounds
from kymflow.gui_v2.events import DeleteRoi, EditRoi, SelectionOrigin
from kymflow.gui_v2.roi_intent_confirm import (
    build_roi_mutation_message,
    confirm_delete_roi_intent,
    confirm_edit_roi_intent,
    resolve_kym_image_for_viewer_intent,
)
from kymflow.core.image_loaders.kym_image import KymImage


def _kym_with_path(tmp_path: Path) -> KymImage:
    data = np.zeros((40, 40), dtype=np.uint16)
    kym = KymImage(img_data=data, load_image=False)
    tif_path = tmp_path / "unit.tif"
    kym._file_path_dict[1] = tif_path
    kym.rois.create_roi(
        bounds=RoiBounds(dim0_start=5, dim0_stop=20, dim1_start=5, dim1_stop=20),
        channel=1,
    )
    return kym


def test_resolve_kym_image_matching_path(tmp_path: Path) -> None:
    kym = _kym_with_path(tmp_path)
    app_state = MagicMock()
    app_state.selected_file = kym
    assert resolve_kym_image_for_viewer_intent(app_state, str(kym.path)) is kym


def test_resolve_kym_image_mismatch_returns_none(tmp_path: Path) -> None:
    kym = _kym_with_path(tmp_path)
    app_state = MagicMock()
    app_state.selected_file = kym
    assert resolve_kym_image_for_viewer_intent(app_state, "/other/file.tif") is None


def test_resolve_no_selected_file() -> None:
    app_state = MagicMock()
    app_state.selected_file = None
    assert resolve_kym_image_for_viewer_intent(app_state, "/a.tif") is None


def test_build_roi_mutation_message_with_dependencies() -> None:
    deps = [
        {"analysis_name": "RadonAnalysis", "roi_id": 1, "channel": 1},
        {"analysis_name": "RadonEventAnalysis", "roi_id": 1, "channel": 1},
    ]
    title, body = build_roi_mutation_message(operation="delete", roi_id=1, deps=deps)
    assert "Delete ROI 1" in title
    assert "RadonAnalysis" in body
    assert "RadonEventAnalysis" in body


def test_build_roi_mutation_message_empty_dependencies() -> None:
    title, body = build_roi_mutation_message(operation="edit", roi_id=2, deps=[])
    assert "2" in title
    assert "No analysis" in body


def test_confirm_delete_non_viewer_origin_emits_immediately(tmp_path: Path) -> None:
    kym = _kym_with_path(tmp_path)
    app_state = MagicMock()
    app_state.selected_file = kym
    bus = MagicMock()
    roi_id = kym.rois.get_roi_ids()[0]
    e = DeleteRoi(
        roi_id=roi_id,
        path=str(kym.path),
        origin=SelectionOrigin.FILE_TABLE,
        phase="intent",
    )
    with patch("kymflow.gui_v2.roi_intent_confirm.ui.dialog") as mock_dialog:
        confirm_delete_roi_intent(app_state, bus, e)
    mock_dialog.assert_not_called()
    bus.emit.assert_called_once_with(e)


def test_confirm_edit_non_viewer_origin_emits_immediately(tmp_path: Path) -> None:
    kym = _kym_with_path(tmp_path)
    app_state = MagicMock()
    app_state.selected_file = kym
    bus = MagicMock()
    roi_id = kym.rois.get_roi_ids()[0]
    bounds = RoiBounds(dim0_start=6, dim0_stop=18, dim1_start=6, dim1_stop=18)
    e = EditRoi(
        roi_id=roi_id,
        bounds=bounds,
        path=str(kym.path),
        origin=SelectionOrigin.EXTERNAL,
        phase="intent",
    )
    with patch("kymflow.gui_v2.roi_intent_confirm.ui.dialog") as mock_dialog:
        confirm_edit_roi_intent(app_state, bus, e)
    mock_dialog.assert_not_called()
    bus.emit.assert_called_once_with(e)


def test_confirm_delete_viewer_opens_dialog_without_immediate_emit(tmp_path: Path) -> None:
    kym = _kym_with_path(tmp_path)
    app_state = MagicMock()
    app_state.selected_file = kym
    bus = MagicMock()
    roi_id = kym.rois.get_roi_ids()[0]
    e = DeleteRoi(
        roi_id=roi_id,
        path=str(kym.path),
        origin=SelectionOrigin.IMAGE_VIEWER,
        phase="intent",
    )
    with (
        patch("kymflow.gui_v2.roi_intent_confirm.ui.dialog") as mock_dialog,
        patch("kymflow.gui_v2.roi_intent_confirm.ui.card"),
        patch("kymflow.gui_v2.roi_intent_confirm.ui.row"),
        patch("kymflow.gui_v2.roi_intent_confirm.ui.label") as mock_label,
    ):
        mock_ctx = MagicMock()
        mock_dialog.return_value.__enter__ = MagicMock(return_value=mock_ctx)
        mock_dialog.return_value.__exit__ = MagicMock(return_value=False)
        mock_label.return_value = MagicMock()
        confirm_delete_roi_intent(app_state, bus, e)
    mock_dialog.assert_called_once()
    mock_ctx.open.assert_called_once()
    bus.emit.assert_not_called()


def test_ok_handler_clears_analysis_and_emits(tmp_path: Path) -> None:
    """Simulate dialog OK: analysis cleared then bus receives intent."""
    kym = _kym_with_path(tmp_path)
    kym_analysis = kym.get_kym_analysis()
    roi_id = kym.rois.get_roi_ids()[0]
    kym_analysis.get_analysis_object("RadonAnalysis").analyze_roi(
        roi_id, 1, window_size=8, use_multiprocessing=False
    )
    assert kym_analysis.has_any_analysis_for_roi(roi_id)

    app_state = MagicMock()
    app_state.selected_file = kym
    bus = MagicMock()
    e = DeleteRoi(
        roi_id=roi_id,
        path=str(kym.path),
        origin=SelectionOrigin.IMAGE_VIEWER,
        phase="intent",
    )

    on_ok = None
    with (
        patch("kymflow.gui_v2.roi_intent_confirm.ui.dialog") as mock_dialog,
        patch("kymflow.gui_v2.roi_intent_confirm.ui.card"),
        patch("kymflow.gui_v2.roi_intent_confirm.ui.row"),
        patch("kymflow.gui_v2.roi_intent_confirm.ui.label") as mock_label,
    ):
        mock_ctx = MagicMock()
        mock_dialog.return_value.__enter__ = MagicMock(return_value=mock_ctx)
        mock_dialog.return_value.__exit__ = MagicMock(return_value=False)
        mock_label.return_value = MagicMock()

        def button_capture(*args, **kwargs):
            nonlocal on_ok
            if kwargs.get("on_click") and args and "Delete" in args[0]:
                on_ok = kwargs["on_click"]
            return MagicMock()

        with patch("kymflow.gui_v2.roi_intent_confirm.ui.button", side_effect=button_capture):
            confirm_delete_roi_intent(app_state, bus, e)

    assert on_ok is not None
    on_ok()
    assert not kym_analysis.has_any_analysis_for_roi(roi_id)
    bus.emit.assert_called_once_with(e)
