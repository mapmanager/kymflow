"""Tests for :mod:`~kymflow.core.batch_analysis.batch_preview`."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import numpy as np

from kymflow.core.batch_analysis.batch_preview import (
    MSG_ADD_ROI,
    MSG_WILL_RUN,
    PENDING_OUTCOME,
    preview_batch_table_rows,
)
from kymflow.core.batch_analysis.types import AnalysisBatchKind, BatchFileOutcome


def _make_kf_radon(*, roi_ids: list[int]) -> MagicMock:
    kf = MagicMock()
    kf.path = Path("a.tif")
    kf.rois.get_roi_ids.return_value = list(roi_ids)
    kf.rois.create_roi.return_value.id = 99
    ka = MagicMock()
    radon = MagicMock()
    radon.has_v0_flow_analysis.return_value = False
    ka.get_analysis_object.return_value = radon
    kf.get_kym_analysis.return_value = ka
    return kf


def test_preview_radon_existing_skips_missing_roi() -> None:
    kf = _make_kf_radon(roi_ids=[2, 3])
    rows = preview_batch_table_rows(
        kind=AnalysisBatchKind.RADON,
        files=[kf],
        roi_mode="existing",
        roi_id=1,
        channel=1,
    )
    assert len(rows) == 1
    assert rows[0]["outcome"] == BatchFileOutcome.SKIPPED.value
    assert "not in file" in rows[0]["message"]


def test_preview_radon_existing_skips_v0() -> None:
    kf = _make_kf_radon(roi_ids=[1])
    radon = kf.get_kym_analysis.return_value.get_analysis_object.return_value
    radon.has_v0_flow_analysis.return_value = True
    rows = preview_batch_table_rows(
        kind=AnalysisBatchKind.RADON,
        files=[kf],
        roi_mode="existing",
        roi_id=1,
        channel=1,
    )
    assert rows[0]["outcome"] == BatchFileOutcome.SKIPPED.value
    assert "v0 flow analysis" in rows[0]["message"]


def test_preview_radon_existing_pending_will_run() -> None:
    kf = _make_kf_radon(roi_ids=[1])
    rows = preview_batch_table_rows(
        kind=AnalysisBatchKind.RADON,
        files=[kf],
        roi_mode="existing",
        roi_id=1,
        channel=1,
    )
    assert rows[0]["outcome"] == PENDING_OUTCOME
    assert rows[0]["message"] == MSG_WILL_RUN


def test_preview_radon_new_full_image_no_radon_object() -> None:
    kf = _make_kf_radon(roi_ids=[])
    kf.get_kym_analysis.return_value.get_analysis_object.return_value = None
    rows = preview_batch_table_rows(
        kind=AnalysisBatchKind.RADON,
        files=[kf],
        roi_mode="new_full_image",
        roi_id=None,
        channel=1,
    )
    assert rows[0]["outcome"] == BatchFileOutcome.SKIPPED.value
    assert rows[0]["message"] == "RadonAnalysis not available"


def test_preview_radon_new_full_image_pending_add_roi() -> None:
    kf = _make_kf_radon(roi_ids=[])
    rows = preview_batch_table_rows(
        kind=AnalysisBatchKind.RADON,
        files=[kf],
        roi_mode="new_full_image",
        roi_id=None,
        channel=1,
    )
    assert rows[0]["outcome"] == PENDING_OUTCOME
    assert rows[0]["message"] == MSG_ADD_ROI


def test_preview_kym_event_new_full_image_pending_add_roi() -> None:
    kf = _make_kf_radon(roi_ids=[])
    rows = preview_batch_table_rows(
        kind=AnalysisBatchKind.KYM_EVENT,
        files=[kf],
        roi_mode="new_full_image",
        roi_id=None,
        channel=1,
    )
    assert rows[0]["outcome"] == PENDING_OUTCOME
    assert rows[0]["message"] == MSG_ADD_ROI


def test_preview_kym_event_existing_skips_no_radon_velocity() -> None:
    kf = _make_kf_radon(roi_ids=[1])
    radon = MagicMock()
    radon.get_analysis_value.return_value = None
    ka = kf.get_kym_analysis.return_value
    ka.get_analysis_object.return_value = radon
    rows = preview_batch_table_rows(
        kind=AnalysisBatchKind.KYM_EVENT,
        files=[kf],
        roi_mode="existing",
        roi_id=1,
        channel=1,
    )
    assert rows[0]["outcome"] == BatchFileOutcome.SKIPPED.value
    assert "no radon flow for ROI 1 ch 1" in rows[0]["message"]


def test_preview_kym_event_existing_pending_will_run() -> None:
    kf = _make_kf_radon(roi_ids=[1])
    radon = MagicMock()
    radon.get_analysis_value.side_effect = [np.array([1.0]), np.array([0.0])]
    ka = kf.get_kym_analysis.return_value
    ka.get_analysis_object.return_value = radon
    rows = preview_batch_table_rows(
        kind=AnalysisBatchKind.KYM_EVENT,
        files=[kf],
        roi_mode="existing",
        roi_id=1,
        channel=1,
    )
    assert rows[0]["outcome"] == PENDING_OUTCOME
    assert rows[0]["message"] == MSG_WILL_RUN
