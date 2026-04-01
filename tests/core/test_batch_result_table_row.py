"""Tests for :mod:`~kymflow.core.kym_analysis_batch.batch_result_table_row`."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from kymflow.core.kym_analysis_batch.batch_result_table_row import batch_file_result_to_table_row
from kymflow.core.kym_analysis_batch.types import AnalysisBatchKind, BatchFileOutcome, BatchFileResult


def _make_result(
    *,
    outcome: BatchFileOutcome,
    message: str,
) -> BatchFileResult:
    kf = MagicMock()
    kf.path = Path("test.tif")
    return BatchFileResult(
        kym_image=kf,
        kind=AnalysisBatchKind.KYM_EVENT,
        outcome=outcome,
        message=message,
    )


def test_ok_row_has_emoji_and_empty_message() -> None:
    row = batch_file_result_to_table_row(_make_result(outcome=BatchFileOutcome.OK, message="ok"))
    assert row["outcome"] == "✅ ok"
    assert row["message"] == ""
    assert row["file"] == "test.tif"


def test_skipped_row() -> None:
    row = batch_file_result_to_table_row(
        _make_result(outcome=BatchFileOutcome.SKIPPED, message="ROI 1 not in file")
    )
    assert "🟡✔" in row["outcome"]
    assert "skipped" in row["outcome"]
    assert row["message"] == "ROI 1 not in file"


def test_failed_row() -> None:
    row = batch_file_result_to_table_row(
        _make_result(outcome=BatchFileOutcome.FAILED, message="boom")
    )
    assert "❌" in row["outcome"]
    assert row["message"] == "boom"


def test_cancelled_row() -> None:
    row = batch_file_result_to_table_row(
        _make_result(outcome=BatchFileOutcome.CANCELLED, message="cancelled")
    )
    assert "🟡✖" in row["outcome"]
    assert row["message"] == "cancelled"
