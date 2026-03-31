"""Strategy for batch velocity-event (kym event) detection."""

from __future__ import annotations

import threading
from typing import Literal

from kymflow.core.analysis.velocity_events.velocity_events import (
    BaselineDropParams,
    NanGapParams,
    ZeroGapParams,
)
from kymflow.core.batch_analysis.roi_mode import resolve_effective_roi
from kymflow.core.batch_analysis.kym_event_batch import has_radon_velocity_and_time
from kymflow.core.batch_analysis.types import (
    AnalysisBatchKind,
    BatchFileOutcome,
    BatchFileResult,
)
from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)


class KymEventBatchStrategy:
    """Run ``run_velocity_event_analysis`` per file with ROI mode and channel.

    Prerequisites: Radon ``velocity`` and ``time`` for the effective ROI/channel
    (unless skipped). ``prepare_file`` loads the selected channel when possible.

    Attributes:
        roi_mode: Use a shared ROI id or create a full-image ROI per file.
        roi_id: ROI id when ``roi_mode == \"existing\"``.
        channel: 1-based channel index.
        baseline_drop_params: Baseline-drop parameters.
        nan_gap_params: Optional NaN-gap parameters.
        zero_gap_params: Optional zero-gap parameters.
    """

    kind = AnalysisBatchKind.KYM_EVENT

    def __init__(
        self,
        *,
        roi_mode: Literal["existing", "new_full_image"],
        roi_id: int | None,
        channel: int,
        baseline_drop_params: BaselineDropParams,
        nan_gap_params: NanGapParams | None = None,
        zero_gap_params: ZeroGapParams | None = None,
    ) -> None:
        """Initialize the kym-event batch strategy.

        Args:
            roi_mode: ``existing`` or ``new_full_image`` (``create_roi()`` with no args).
            roi_id: ROI id when ``roi_mode == \"existing\"``.
            channel: 1-based channel index.
            baseline_drop_params: Baseline-drop detection parameters.
            nan_gap_params: Optional NaN-gap parameters.
            zero_gap_params: Optional zero-gap parameters.
        """
        self._roi_mode = roi_mode
        self._roi_id = roi_id
        self._channel = channel
        self._baseline_drop_params = baseline_drop_params
        self._nan_gap_params = nan_gap_params
        self._zero_gap_params = zero_gap_params

    def prepare_file(self, kf: KymImage) -> None:
        """Ensure the selected channel is loaded for image-backed operations.

        Args:
            kf: Kymograph file.
        """
        try:
            kf.load_channel(self._channel)
        except Exception:
            logger.warning(
                "KymEventBatchStrategy.prepare_file: load_channel failed for %s ch=%s",
                getattr(kf, "path", None),
                self._channel,
                exc_info=True,
            )

    def process_file(
        self,
        kf: KymImage,
        *,
        cancel_event: threading.Event,
    ) -> BatchFileResult:
        """Run one-file kym-event detection; returns status (mutates ``KymAnalysis`` on success).

        Args:
            kf: Kymograph file.
            cancel_event: When set, returns ``CANCELLED`` without running analysis.

        Returns:
            :class:`BatchFileResult` describing outcome.
        """
        file_label = kf.path.name if getattr(kf, "path", None) is not None else "unknown"

        if cancel_event.is_set():
            return BatchFileResult(
                kym_image=kf,
                kind=AnalysisBatchKind.KYM_EVENT,
                outcome=BatchFileOutcome.CANCELLED,
                message="cancelled",
            )

        self.prepare_file(kf)

        if cancel_event.is_set():
            return BatchFileResult(
                kym_image=kf,
                kind=AnalysisBatchKind.KYM_EVENT,
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
                kind=AnalysisBatchKind.KYM_EVENT,
                outcome=BatchFileOutcome.SKIPPED,
                message=resolved.skip_message,
            )
        assert resolved.roi_id is not None
        effective_roi_id = resolved.roi_id

        if not has_radon_velocity_and_time(kf, effective_roi_id, self._channel):
            return BatchFileResult(
                kym_image=kf,
                kind=AnalysisBatchKind.KYM_EVENT,
                outcome=BatchFileOutcome.SKIPPED,
                message=f"no radon flow for ROI {effective_roi_id} ch {self._channel}",
            )

        try:
            ka = kf.get_kym_analysis()
            ka.run_velocity_event_analysis(
                effective_roi_id,
                self._channel,
                remove_outliers=True,
                baseline_drop_params=self._baseline_drop_params,
                nan_gap_params=self._nan_gap_params,
                zero_gap_params=self._zero_gap_params,
            )
        except ValueError as exc:
            logger.warning(
                "Kym-event batch failed (ValueError) for %s: %s",
                file_label,
                exc,
            )
            return BatchFileResult(
                kym_image=kf,
                kind=AnalysisBatchKind.KYM_EVENT,
                outcome=BatchFileOutcome.FAILED,
                message=str(exc),
            )
        except Exception as exc:
            logger.exception("Kym-event batch failed for %s", file_label)
            return BatchFileResult(
                kym_image=kf,
                kind=AnalysisBatchKind.KYM_EVENT,
                outcome=BatchFileOutcome.FAILED,
                message=repr(exc),
            )

        return BatchFileResult(
            kym_image=kf,
            kind=AnalysisBatchKind.KYM_EVENT,
            outcome=BatchFileOutcome.OK,
            message="ok",
        )
