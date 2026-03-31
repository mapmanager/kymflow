"""Batch analysis over multiple kymographs (core, GUI-agnostic)."""

from kymflow.core.batch_analysis.kym_analysis_batch import BatchAnalysisStrategy, KymAnalysisBatch
from kymflow.core.batch_analysis.radon_batch_strategy import RadonBatchStrategy
from kymflow.core.batch_analysis.kym_event_batch import (
    has_radon_velocity_and_time,
    roi_intersection_across_files,
)
from kymflow.core.batch_analysis.kym_event_batch_strategy import KymEventBatchStrategy
from kymflow.core.batch_analysis.batch_preview import preview_batch_table_rows
from kymflow.core.batch_analysis.types import (
    AnalysisBatchKind,
    BatchFileOutcome,
    BatchFileResult,
)

__all__ = [
    "AnalysisBatchKind",
    "BatchAnalysisStrategy",
    "BatchFileOutcome",
    "BatchFileResult",
    "KymAnalysisBatch",
    "KymEventBatchStrategy",
    "RadonBatchStrategy",
    "has_radon_velocity_and_time",
    "roi_intersection_across_files",
    "preview_batch_table_rows",
]
