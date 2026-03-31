"""Tests for :class:`~kymflow.core.batch_analysis.kym_analysis_batch.KymAnalysisBatch`."""

from __future__ import annotations

import threading
from pathlib import Path
from unittest.mock import MagicMock

from kymflow.core.batch_analysis.kym_analysis_batch import KymAnalysisBatch
from kymflow.core.batch_analysis.types import (
    AnalysisBatchKind,
    BatchFileOutcome,
    BatchFileResult,
)


class _OkStrategy:
    """Minimal strategy for batch runner tests."""

    kind = AnalysisBatchKind.KYM_EVENT

    def __init__(self) -> None:
        self.calls = 0

    def process_file(self, kf: MagicMock, *, cancel_event: threading.Event) -> BatchFileResult:
        self.calls += 1
        return BatchFileResult(
            kym_image=kf,
            kind=AnalysisBatchKind.KYM_EVENT,
            outcome=BatchFileOutcome.OK,
            message="ok",
        )


def test_kym_analysis_batch_sequential_two_files() -> None:
    """Sequential mode runs process_file once per file."""
    kf1 = MagicMock()
    kf1.path = Path("a.tif")
    kf2 = MagicMock()
    kf2.path = Path("b.tif")
    strat = _OkStrategy()
    batch = KymAnalysisBatch([kf1, kf2], strat, max_parallel_files=1)
    out = batch.run()
    assert len(out) == 2
    assert strat.calls == 2
    assert all(r.outcome == BatchFileOutcome.OK for r in out)


def test_kym_analysis_batch_parallel_two_workers() -> None:
    """Parallel mode invokes strategy for each file."""
    kf1 = MagicMock()
    kf1.path = Path("a.tif")
    kf2 = MagicMock()
    kf2.path = Path("b.tif")
    strat = _OkStrategy()
    batch = KymAnalysisBatch([kf1, kf2], strat, max_parallel_files=2)
    out = batch.run()
    assert len(out) == 2
    assert strat.calls == 2


def test_kym_analysis_batch_cancel_before_run_skips_or_cancels() -> None:
    """Cancel event causes cancelled outcomes when checked in strategy."""
    kf = MagicMock()
    kf.path = Path("a.tif")

    class CancelStrategy:
        kind = AnalysisBatchKind.KYM_EVENT

        def process_file(self, kf: MagicMock, *, cancel_event: threading.Event) -> BatchFileResult:
            if cancel_event.is_set():
                return BatchFileResult(
                    kym_image=kf,
                    kind=AnalysisBatchKind.KYM_EVENT,
                    outcome=BatchFileOutcome.CANCELLED,
                    message="cancelled",
                )
            return BatchFileResult(
                kym_image=kf,
                kind=AnalysisBatchKind.KYM_EVENT,
                outcome=BatchFileOutcome.OK,
                message="ok",
            )

    ev = threading.Event()
    ev.set()
    batch = KymAnalysisBatch([kf], CancelStrategy(), max_parallel_files=1)
    out = batch.run(cancel_event=ev)
    assert len(out) == 1
    assert out[0].outcome == BatchFileOutcome.CANCELLED


def test_kym_analysis_batch_on_file_result_callback() -> None:
    """on_file_result is invoked for each completed file."""
    kf = MagicMock()
    kf.path = Path("a.tif")
    strat = _OkStrategy()
    batch = KymAnalysisBatch([kf], strat, max_parallel_files=1)
    seen: list[BatchFileResult] = []

    def cb(r: BatchFileResult) -> None:
        seen.append(r)

    batch.run(on_file_result=cb)
    assert len(seen) == 1
    assert seen[0].outcome == BatchFileOutcome.OK


def test_kym_analysis_batch_empty_files() -> None:
    """Empty file list returns empty result list."""
    strat = _OkStrategy()
    batch = KymAnalysisBatch([], strat, max_parallel_files=4)
    assert batch.run() == []
