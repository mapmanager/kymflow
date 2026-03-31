"""Read-only preview table rows for batch analysis (GUI and scripts).

Does not create ROIs or run analysis. Skip messages match
:class:`~kymflow.core.batch_analysis.kym_event_batch_strategy.KymEventBatchStrategy`
and :class:`~kymflow.core.batch_analysis.radon_batch_strategy.RadonBatchStrategy`
where the same read-only checks apply.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from kymflow.core.batch_analysis.kym_event_batch import has_radon_velocity_and_time
from kymflow.core.batch_analysis.roi_mode import preview_resolve_effective_roi
from kymflow.core.batch_analysis.types import AnalysisBatchKind, BatchFileOutcome
from kymflow.core.image_loaders.kym_image import KymImage
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
            "batch_preview: load_channel failed for %s ch=%s",
            getattr(kf, "path", None),
            channel,
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
    use :attr:`~kymflow.core.batch_analysis.types.BatchFileOutcome.SKIPPED` and
    the same messages as batch strategies where checks do not require creating a ROI.
    Rows that would run analysis use ``outcome`` ``\"pending\"`` and ``\"will run\"``
    or ``\"add roi\"`` (new full-image ROI mode) in ``message``.

    Args:
        kind: Kym-event or Radon batch.
        files: Snapshot of files for this dialog session (same order as execution).
        roi_mode: Existing shared ROI or new full-image ROI per file at run time.
        roi_id: ROI id when ``roi_mode == \"existing\"``.
        channel: 1-based channel index.

    Returns:
        List of row dicts, same length and order as ``files``.
    """
    rows: list[dict[str, str]] = []
    for kf in files:
        if kind == AnalysisBatchKind.RADON:
            rows.append(
                _preview_radon_row(
                    kf,
                    roi_mode=roi_mode,
                    roi_id=roi_id,
                    channel=channel,
                )
            )
        else:
            rows.append(
                _preview_kym_event_row(
                    kf,
                    roi_mode=roi_mode,
                    roi_id=roi_id,
                    channel=channel,
                )
            )
    return rows
