"""Table row dicts for batch dialog results (emoji outcome labels, display messages).

Preview/planned rows use :func:`~kymflow.core.kym_analysis_batch.batch_preview.preview_batch_table_rows`
without these decorations. Use :func:`batch_file_result_to_table_row` only for live or final
:class:`~kymflow.core.kym_analysis_batch.types.BatchFileResult` rows.
"""

from __future__ import annotations

from kymflow.core.kym_analysis_batch.types import BatchFileOutcome, BatchFileResult


def batch_file_result_to_table_row(r: BatchFileResult) -> dict[str, str]:
    """Map a batch file result to a dialog table row with decorated outcome text.

    Outcome column uses emoji prefixes; successful rows use an empty message (core strategies
    may still report ``message=\"ok\"``).

    Args:
        r: Per-file result from a batch strategy or runner.

    Returns:
        Dict with keys ``file``, ``kind``, ``outcome``, ``message`` for ``ui.table`` rows.
    """
    file_label = (
        r.kym_image.path.name
        if getattr(r.kym_image, "path", None) is not None
        else "unknown"
    )
    kind = r.kind.value

    if r.outcome == BatchFileOutcome.OK:
        outcome_display = "✅ ok"
        message_display = ""
    elif r.outcome == BatchFileOutcome.SKIPPED:
        outcome_display = "🟡✔ skipped"
        message_display = r.message
    elif r.outcome == BatchFileOutcome.FAILED:
        outcome_display = "❌ failed"
        message_display = r.message
    elif r.outcome == BatchFileOutcome.CANCELLED:
        outcome_display = "🟡✖ cancelled"
        message_display = r.message
    else:
        outcome_display = r.outcome.value
        message_display = r.message

    return {
        "file": file_label,
        "kind": kind,
        "outcome": outcome_display,
        "message": message_display,
    }
