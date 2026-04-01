"""Strategy for batch Radon flow analysis."""

from __future__ import annotations

import threading
from typing import Literal

from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.core.kym_analysis_batch.roi_mode import resolve_effective_roi
from kymflow.core.kym_analysis_batch.types import (
    AnalysisBatchKind,
    BatchFileOutcome,
    BatchFileResult,
)
from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)


class RadonBatchStrategy:
    """Run ``RadonAnalysis.analyze_roi`` per file with shared ROI mode and channel."""

    kind = AnalysisBatchKind.RADON

    def __init__(
        self,
        *,
        roi_mode: Literal["existing", "new_full_image"],
        roi_id: int | None,
        channel: int,
        window_size: int,
    ) -> None:
        """Initialize Radon batch strategy.

        Args:
            roi_mode: ``existing`` or ``new_full_image``.
            roi_id: ROI id when ``roi_mode == "existing"``.
            channel: 1-based channel index.
            window_size: Radon window size.
        """
        self._roi_mode = roi_mode
        self._roi_id = roi_id
        self._channel = channel
        self._window_size = int(window_size)

    def prepare_file(self, kf: KymImage) -> None:
        """Ensure selected channel is loaded for image-backed operations."""
        try:
            kf.load_channel(self._channel)
        except Exception:
            logger.warning(
                f"RadonBatchStrategy.prepare_file: load_channel failed for {getattr(kf, 'path', None)} ch={self._channel}",
                exc_info=True,
            )

    def process_file(
        self,
        kf: KymImage,
        *,
        cancel_event: threading.Event,
    ) -> BatchFileResult:
        """Run one-file Radon analysis; mutates ``KymAnalysis`` on success."""
        file_label = kf.path.name if getattr(kf, "path", None) is not None else "unknown"

        if cancel_event.is_set():
            return BatchFileResult(
                kym_image=kf,
                kind=AnalysisBatchKind.RADON,
                outcome=BatchFileOutcome.CANCELLED,
                message="cancelled",
            )

        self.prepare_file(kf)
        if cancel_event.is_set():
            return BatchFileResult(
                kym_image=kf,
                kind=AnalysisBatchKind.RADON,
                outcome=BatchFileOutcome.CANCELLED,
                message="cancelled",
            )

        resolved = resolve_effective_roi(
            kf,
            roi_mode=self._roi_mode,
            roi_id=self._roi_id,
        )
        if resolved.skip_message is not None:
            return BatchFileResult(
                kym_image=kf,
                kind=AnalysisBatchKind.RADON,
                outcome=BatchFileOutcome.SKIPPED,
                message=resolved.skip_message,
            )
        assert resolved.roi_id is not None
        effective_roi_id = resolved.roi_id

        ka = kf.get_kym_analysis()
        radon = ka.get_analysis_object("RadonAnalysis")
        if radon is None:
            return BatchFileResult(
                kym_image=kf,
                kind=AnalysisBatchKind.RADON,
                outcome=BatchFileOutcome.SKIPPED,
                message="RadonAnalysis not available",
            )

        if radon.has_v0_flow_analysis(effective_roi_id, self._channel):
            return BatchFileResult(
                kym_image=kf,
                kind=AnalysisBatchKind.RADON,
                outcome=BatchFileOutcome.SKIPPED,
                message=f"ROI {effective_roi_id} ch {self._channel} has v0 flow analysis",
            )

        try:
            radon.analyze_roi(
                effective_roi_id,
                self._channel,
                self._window_size,
                is_cancelled=cancel_event.is_set,
                use_multiprocessing=True,
            )
        except Exception as exc:
            logger.exception(f"Radon batch failed for {file_label}")
            return BatchFileResult(
                kym_image=kf,
                kind=AnalysisBatchKind.RADON,
                outcome=BatchFileOutcome.FAILED,
                message=repr(exc),
            )

        return BatchFileResult(
            kym_image=kf,
            kind=AnalysisBatchKind.RADON,
            outcome=BatchFileOutcome.OK,
            message="ok",
        )
