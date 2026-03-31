"""Tests for :class:`~kymflow.core.batch_analysis.radon_batch_strategy.RadonBatchStrategy`."""

from __future__ import annotations

import threading
from pathlib import Path
from unittest.mock import MagicMock

from kymflow.core.batch_analysis.radon_batch_strategy import RadonBatchStrategy
from kymflow.core.batch_analysis.types import BatchFileOutcome


def _make_kf(*, roi_ids: list[int]) -> MagicMock:
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


def test_radon_batch_strategy_ok_existing_roi() -> None:
    kf = _make_kf(roi_ids=[1, 2])
    strategy = RadonBatchStrategy(
        roi_mode="existing",
        roi_id=1,
        channel=1,
        window_size=16,
    )
    out = strategy.process_file(kf, cancel_event=threading.Event())
    assert out.outcome == BatchFileOutcome.OK
    radon = kf.get_kym_analysis.return_value.get_analysis_object.return_value
    radon.analyze_roi.assert_called_once()


def test_radon_batch_strategy_skips_missing_roi_existing_mode() -> None:
    kf = _make_kf(roi_ids=[2, 3])
    strategy = RadonBatchStrategy(
        roi_mode="existing",
        roi_id=1,
        channel=1,
        window_size=16,
    )
    out = strategy.process_file(kf, cancel_event=threading.Event())
    assert out.outcome == BatchFileOutcome.SKIPPED
    assert "not in file" in out.message


def test_radon_batch_strategy_skips_v0() -> None:
    kf = _make_kf(roi_ids=[1])
    radon = kf.get_kym_analysis.return_value.get_analysis_object.return_value
    radon.has_v0_flow_analysis.return_value = True
    strategy = RadonBatchStrategy(
        roi_mode="existing",
        roi_id=1,
        channel=1,
        window_size=16,
    )
    out = strategy.process_file(kf, cancel_event=threading.Event())
    assert out.outcome == BatchFileOutcome.SKIPPED
    assert "v0 flow analysis" in out.message
    radon.analyze_roi.assert_not_called()


def test_radon_batch_strategy_new_full_image_creates_roi() -> None:
    kf = _make_kf(roi_ids=[])
    strategy = RadonBatchStrategy(
        roi_mode="new_full_image",
        roi_id=None,
        channel=1,
        window_size=16,
    )
    out = strategy.process_file(kf, cancel_event=threading.Event())
    assert out.outcome == BatchFileOutcome.OK
    kf.rois.create_roi.assert_called_once()


def test_radon_batch_strategy_cancelled_returns_cancelled() -> None:
    kf = _make_kf(roi_ids=[1])
    strategy = RadonBatchStrategy(
        roi_mode="existing",
        roi_id=1,
        channel=1,
        window_size=16,
    )
    ev = threading.Event()
    ev.set()
    out = strategy.process_file(kf, cancel_event=ev)
    assert out.outcome == BatchFileOutcome.CANCELLED
