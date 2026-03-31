"""Tests for kym-event batch helpers."""

from __future__ import annotations

from unittest.mock import MagicMock

from kymflow.core.batch_analysis.kym_event_batch import (
    has_radon_velocity_and_time,
    roi_intersection_across_files,
)


def test_roi_intersection_across_files_empty() -> None:
    """Empty file list yields empty intersection."""
    assert roi_intersection_across_files([]) == []


def test_roi_intersection_across_files_common() -> None:
    """Intersection is sorted ids present in every file."""
    f1 = MagicMock()
    f1.rois.get_roi_ids.return_value = [2, 1, 3]
    f2 = MagicMock()
    f2.rois.get_roi_ids.return_value = [3, 1]
    assert roi_intersection_across_files([f1, f2]) == [1, 3]


def test_has_radon_velocity_and_time_false_without_radon() -> None:
    """Missing RadonAnalysis yields False."""
    kf = MagicMock()
    ka = MagicMock()
    ka.get_analysis_object.return_value = None
    kf.get_kym_analysis.return_value = ka
    assert has_radon_velocity_and_time(kf, 1, 1) is False


def test_has_radon_velocity_and_time_true() -> None:
    """Both velocity and time present yields True."""
    import numpy as np

    kf = MagicMock()
    radon = MagicMock()
    radon.get_analysis_value.side_effect = [np.array([1.0]), np.array([0.0])]
    ka = MagicMock()
    ka.get_analysis_object.return_value = radon
    kf.get_kym_analysis.return_value = ka
    assert has_radon_velocity_and_time(kf, 1, 1) is True
