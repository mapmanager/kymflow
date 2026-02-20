"""Tests for run-marker contract helpers."""

from __future__ import annotations

import pytest

from kymflow.core.kym_dataset.run_marker import (
    RUN_MARKER_VERSION,
    make_run_marker,
    marker_matches,
    marker_n_rows,
    validate_run_marker,
)


def test_make_and_validate_run_marker() -> None:
    marker = make_run_marker(
        indexer_name="velocity_events",
        params_hash="abc",
        analysis_version="v0.1",
        n_rows=0,
        ran_utc_epoch_ns=123,
    )
    assert marker["marker_version"] == RUN_MARKER_VERSION
    validate_run_marker(marker)
    assert marker_n_rows(marker) == 0


def test_marker_matches_requires_valid_shape() -> None:
    marker = make_run_marker(
        indexer_name="velocity_events",
        params_hash="abc",
        analysis_version="v0.1",
        n_rows=2,
    )
    assert marker_matches(marker, params_hash="abc", analysis_version="v0.1") is True
    assert marker_matches(marker, params_hash="zzz", analysis_version="v0.1") is False

    bad = {"params_hash": "abc"}
    assert marker_matches(bad, params_hash="abc", analysis_version="v0.1") is False


def test_validate_run_marker_errors_on_invalid_values() -> None:
    marker = make_run_marker(
        indexer_name="velocity_events",
        params_hash="abc",
        analysis_version="v0.1",
        n_rows=1,
        ran_utc_epoch_ns=1,
    )
    marker["n_rows"] = -1
    with pytest.raises(ValueError, match="n_rows"):
        validate_run_marker(marker)
