"""Shared types for :class:`~kymflow.core.kym_analysis_batch.kym_analysis_batch.KymAnalysisBatch`."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from kymflow.core.image_loaders.kym_image import KymImage


class AnalysisBatchKind(str, Enum):
    """Kind of analysis run in a batch."""

    KYM_EVENT = "kym_event"
    RADON = "radon"
    DIAMETER = "diameter"


class BatchFileOutcome(str, Enum):
    """Per-file result of a batch step."""

    OK = "ok"
    SKIPPED = "skipped"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class BatchFileResult:
    """Lightweight per-file outcome (results remain on ``KymImage`` / ``KymAnalysis``)."""

    kym_image: KymImage
    kind: AnalysisBatchKind
    outcome: BatchFileOutcome
    message: str
