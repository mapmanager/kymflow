"""Read-only preview table rows for batch analysis (GUI and scripts).

Does not create ROIs or run analysis. Skip messages match
:class:`~kymflow.core.kym_analysis_batch.kym_event_batch_strategy.KymEventBatchStrategy`
and :class:`~kymflow.core.kym_analysis_batch.radon_batch_strategy.RadonBatchStrategy`
where the same read-only checks apply.

Each :class:`~kymflow.core.kym_analysis_batch.types.AnalysisBatchKind` must be handled
explicitly in :func:`preview_batch_table_rows`; unimplemented kinds raise
:class:`NotImplementedError` (no fallback to another analysis).

:class:`~kymflow.core.kym_analysis_batch.types.BatchFileOutcome` preview uses
:func:`_prepare_channel` (``load_channel``) for parity with batch strategies;
that may touch image load state but does not create ROIs or run analysis.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.core.kym_analysis_batch.kym_event_batch import has_radon_velocity_and_time
from kymflow.core.kym_analysis_batch.roi_mode import preview_resolve_effective_roi
from kymflow.core.kym_analysis_batch.types import AnalysisBatchKind, BatchFileOutcome
from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)

PENDING_OUTCOME = "pending"
MSG_WILL_RUN = "will run"
MSG_ADD_ROI = "add roi"


def _file_label(kf: KymImage) -> str:
    return kf.path.name if getattr(kf, "path", None) is not None else "unknown"


def _prepare_channel(kf: KymImage, channel: int) -> None:
    try:
        kf.load_channel(channel)
    except Exception:
        logger.warning(
            f"batch_preview: load_channel failed for {getattr(kf, 'path', None)} ch={channel}",
            exc_info=True,
        )


def _preview_kym_event_row(
    kf: KymImage,
    *,
    roi_mode: Literal["existing", "new_full_image"],
    roi_id: int | None,
    channel: int,
) -> dict[str, str]:
    """Build one preview row for kym-event batch."""
    fl = _file_label(kf)
    kind = AnalysisBatchKind.KYM_EVENT.value
    sk = BatchFileOutcome.SKIPPED.value

    _prepare_channel(kf, channel)

    if roi_mode == "new_full_image":
        return {
            "file": fl,
            "kind": kind,
            "outcome": PENDING_OUTCOME,
            "message": MSG_ADD_ROI,
        }

    resolved = preview_resolve_effective_roi(
        kf,
        roi_mode=roi_mode,
        roi_id=roi_id,
    )
    if resolved.skip_message is not None:
        return {"file": fl, "kind": kind, "outcome": sk, "message": resolved.skip_message}

    assert resolved.roi_id is not None
    effective_roi_id = resolved.roi_id
    if not has_radon_velocity_and_time(kf, effective_roi_id, channel):
        return {
            "file": fl,
            "kind": kind,
            "outcome": sk,
            "message": f"no radon flow for ROI {effective_roi_id} ch {channel}",
        }
    return {
        "file": fl,
        "kind": kind,
        "outcome": PENDING_OUTCOME,
        "message": MSG_WILL_RUN,
    }


def _preview_radon_row(
    kf: KymImage,
    *,
    roi_mode: Literal["existing", "new_full_image"],
    roi_id: int | None,
    channel: int,
) -> dict[str, str]:
    """Build one preview row for Radon batch."""
    fl = _file_label(kf)
    kind = AnalysisBatchKind.RADON.value
    sk = BatchFileOutcome.SKIPPED.value

    _prepare_channel(kf, channel)

    if roi_mode == "new_full_image":
        ka = kf.get_kym_analysis()
        radon = ka.get_analysis_object("RadonAnalysis")
        if radon is None:
            return {
                "file": fl,
                "kind": kind,
                "outcome": sk,
                "message": "RadonAnalysis not available",
            }
        return {
            "file": fl,
            "kind": kind,
            "outcome": PENDING_OUTCOME,
            "message": MSG_ADD_ROI,
        }

    resolved = preview_resolve_effective_roi(
        kf,
        roi_mode=roi_mode,
        roi_id=roi_id,
    )
    if resolved.skip_message is not None:
        return {"file": fl, "kind": kind, "outcome": sk, "message": resolved.skip_message}

    assert resolved.roi_id is not None
    effective_roi_id = resolved.roi_id

    ka = kf.get_kym_analysis()
    radon = ka.get_analysis_object("RadonAnalysis")
    if radon is None:
        return {
            "file": fl,
            "kind": kind,
            "outcome": sk,
            "message": "RadonAnalysis not available",
        }

    if radon.has_v0_flow_analysis(effective_roi_id, channel):
        return {
            "file": fl,
            "kind": kind,
            "outcome": sk,
            "message": f"ROI {effective_roi_id} ch {channel} has v0 flow analysis",
        }
    return {
        "file": fl,
        "kind": kind,
        "outcome": PENDING_OUTCOME,
        "message": MSG_WILL_RUN,
    }


def preview_batch_table_rows(
    *,
    kind: AnalysisBatchKind,
    files: Sequence[KymImage],
    roi_mode: Literal["existing", "new_full_image"],
    roi_id: int | None,
    channel: int,
) -> list[dict[str, str]]:
    """Return one table row dict per file for the batch dialog (planned state).

    Rows use keys ``file``, ``kind``, ``outcome``, ``message``. Deterministic skips
    use :attr:`~kymflow.core.kym_analysis_batch.types.BatchFileOutcome.SKIPPED` and
    the same messages as batch strategies where checks do not require creating a ROI.
    Rows that would run analysis use ``outcome`` ``\"pending\"`` and ``\"will run\"``
    or ``\"add roi\"`` (new full-image ROI mode) in ``message``.

    Args:
        kind: Batch analysis kind. ``KYM_EVENT`` and ``RADON`` are implemented;
            ``DIAMETER`` and any future enum members raise :class:`NotImplementedError`
            until a preview is added for that kind.
        files: Snapshot of files for this dialog session (same order as execution).
        roi_mode: Existing shared ROI or new full-image ROI per file at run time.
        roi_id: ROI id when ``roi_mode == \"existing\"``.
        channel: 1-based channel index.

    Returns:
        List of row dicts, same length and order as ``files``.

    Raises:
        NotImplementedError: If ``kind`` has no preview implementation yet.
    """
    rows: list[dict[str, str]] = []
    for kf in files:
        match kind:
            case AnalysisBatchKind.KYM_EVENT:
                rows.append(
                    _preview_kym_event_row(
                        kf,
                        roi_mode=roi_mode,
                        roi_id=roi_id,
                        channel=channel,
                    )
                )
            case AnalysisBatchKind.RADON:
                rows.append(
                    _preview_radon_row(
                        kf,
                        roi_mode=roi_mode,
                        roi_id=roi_id,
                        channel=channel,
                    )
                )
            case AnalysisBatchKind.DIAMETER:
                raise NotImplementedError(
                    "Batch table preview for diameter analysis is not implemented yet; "
                    "add a diameter preview helper and dispatch it from preview_batch_table_rows."
                )
            case _:
                raise NotImplementedError(
                    f"Batch table preview is not implemented for analysis kind {kind!r}."
                )
    return rows
