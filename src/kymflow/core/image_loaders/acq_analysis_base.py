"""Base class for analysis components owned by KymAnalysis.

AcqAnalysisBase defines the common interface for analysis types (RadonAnalysis,
velocity/event analyses, etc.) that KymAnalysis manages via _analysis_children.

Analyses that store state keyed by (roi_id, channel) must implement the
iter_roi_channel_keys API so KymAnalysis and GUI callers can query which
analyses have data for a given (roi_id, channel) before performing ROI CRUD.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kymflow.core.image_loaders.acq_image import AcqImage


class AcqAnalysisBase(ABC):
    """Base class for analysis components.

    Each analysis (RadonAnalysis, velocity/event analyses, etc.) implements
    save_analysis, load_analysis, and is_dirty. KymAnalysis provides the
    folder path; the analysis knows its own file names.

    Analyses that store per-ROI/channel state must also implement the
    iter_roi_channel_keys method. The default get_roi_dependencies
    implementation will then report a minimal dependency record for a given
    (roi_id, channel) using a uniform dict shape:

        {"analysis_name": analysis_name, "roi_id": roi_id, "channel": channel}
    """

    analysis_name: str = "Undefined"

    def __init__(self, acq_image: "AcqImage") -> None:
        self.acq_image = acq_image

    @property
    @abstractmethod
    def is_dirty(self) -> bool:
        """Return True if this analysis has unsaved changes."""
        ...

    @abstractmethod
    def iter_roi_channel_keys(self) -> list[tuple[int, int]]:
        """Return all (roi_id, channel) keys this analysis has state for."""
        ...

    def get_roi_dependencies(self, roi_id: int, channel: int) -> list[dict]:
        """Return dependency metadata for this analysis at (roi_id, channel).

        This default implementation uses iter_roi_channel_keys to determine
        whether this analysis has any state for the given (roi_id, channel)
        and, if so, returns a single minimal dependency record.

        The dict shape is intentionally KISS and shared across all analyses:
        {"analysis_name": analysis_name, "roi_id": roi_id, "channel": channel}.
        """
        keys = self.iter_roi_channel_keys()
        if (roi_id, channel) not in keys:
            return []
        return [
            {
                "analysis_name": self.analysis_name,
                "roi_id": roi_id,
                "channel": channel,
            }
        ]

    def save_analysis(self, folder_path: Path) -> bool:
        """Save analysis files to the given folder. Override in subclasses."""
        return False

    def load_analysis(self, folder_path: Path) -> bool:
        """Load analysis files from the given folder. Override in subclasses."""
        return False
