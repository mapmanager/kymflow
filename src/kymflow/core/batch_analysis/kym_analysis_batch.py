"""Batch runner over many :class:`~kymflow.core.image_loaders.kym_image.KymImage` instances."""

from __future__ import annotations

import threading
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Protocol, runtime_checkable

from kymflow.core.batch_analysis.types import AnalysisBatchKind, BatchFileOutcome, BatchFileResult
from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)


@runtime_checkable
class BatchAnalysisStrategy(Protocol):
    """Strategy for one analysis kind (kym-event, radon, diameter, ...)."""

    kind: AnalysisBatchKind

    def process_file(
        self,
        kf: KymImage,
        *,
        cancel_event: threading.Event,
    ) -> BatchFileResult:
        """Process a single file (mutates runtime analysis state on success)."""
        ...


class KymAnalysisBatch:
    """Run a batch analysis over a list of kymographs using a :class:`BatchAnalysisStrategy`.

    File-level work uses :class:`~concurrent.futures.ThreadPoolExecutor` with
    ``max_parallel_files`` workers. Each file is independent; inner radon/diameter
    code may use multiprocessing per file as today.

    Science outputs remain on each ``KymImage`` → ``KymAnalysis``; this class
    returns a lightweight :class:`~kymflow.core.batch_analysis.types.BatchFileResult`
    list for logging, tests, and GUI progress.

    Attributes:
        _files: Files to process (order preserved in the returned list).
        _strategy: Strategy implementing ``process_file``.
        _max_parallel_files: Maximum concurrent file workers (at least 1).
    """

    def __init__(
        self,
        files: Sequence[KymImage],
        strategy: BatchAnalysisStrategy,
        *,
        max_parallel_files: int = 4,
    ) -> None:
        """Initialize the batch runner.

        Args:
            files: Kymograph files to analyze (typically a filtered table subset).
            strategy: Kind-specific strategy (params live on the strategy object).
            max_parallel_files: Upper bound on concurrent file workers; clamped to
                at least 1 and at most ``len(files)``.
        """
        self._files: list[KymImage] = list(files)
        self._strategy = strategy
        self._max_parallel_files = max(1, int(max_parallel_files))

    def run(
        self,
        *,
        cancel_event: threading.Event | None = None,
        on_file_result: Callable[[BatchFileResult], None] | None = None,
    ) -> list[BatchFileResult]:
        """Execute the batch (blocks until complete or cancelled).

        ``on_file_result`` may be called from worker threads; use a thread-safe
        queue if forwarding to a GUI.

        Args:
            cancel_event: When set, workers return ``CANCELLED`` for work not
                yet started; in-flight tasks may still complete.
            on_file_result: Optional callback after each file result completes.

        Returns:
            One :class:`~kymflow.core.batch_analysis.types.BatchFileResult` per
            input file, in the same order as ``files``.
        """
        if not self._files:
            return []

        cancel = cancel_event if cancel_event is not None else threading.Event()
        n = len(self._files)
        workers = min(self._max_parallel_files, n)

        def run_indexed(i: int, kf: KymImage) -> tuple[int, BatchFileResult]:
            if cancel.is_set():
                return i, BatchFileResult(
                    kym_image=kf,
                    kind=self._strategy.kind,
                    outcome=BatchFileOutcome.CANCELLED,
                    message="cancelled",
                )
            try:
                r = self._strategy.process_file(kf, cancel_event=cancel)
                return i, r
            except Exception as exc:
                logger.exception("Batch process_file raised for index %s", i)
                return i, BatchFileResult(
                    kym_image=kf,
                    kind=self._strategy.kind,
                    outcome=BatchFileOutcome.FAILED,
                    message=repr(exc),
                )

        if workers == 1:
            ordered: list[BatchFileResult] = []
            for i, kf in enumerate(self._files):
                _, r = run_indexed(i, kf)
                ordered.append(r)
                if on_file_result is not None:
                    on_file_result(r)
            return ordered

        results: list[BatchFileResult | None] = [None] * n
        with ThreadPoolExecutor(max_workers=workers) as ex:
            future_map = {
                ex.submit(run_indexed, i, kf): i for i, kf in enumerate(self._files)
            }
            for fut in as_completed(future_map):
                i, r = fut.result()
                results[i] = r
                if on_file_result is not None:
                    on_file_result(r)

        out: list[BatchFileResult] = []
        for i in range(n):
            assert results[i] is not None
            out.append(results[i])
        return out
