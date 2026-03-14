"""Base class for analysis components owned by KymAnalysis.

AcqAnalysisBase defines the common interface for analysis types (RadonAnalysis,
VelocityAnalysis, etc.) that KymAnalysis manages via _analysis_children.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kymflow.core.image_loaders.acq_image import AcqImage


class AcqAnalysisBase(ABC):
    """Base class for analysis components.

    Each analysis (RadonAnalysis, VelocityAnalysis, etc.) implements
    save_analysis, load_analysis, and is_dirty. KymAnalysis provides
    the folder path; the analysis knows its own file names.
    """

    analysis_name: str = "Undefined"

    def __init__(self, acq_image: "AcqImage") -> None:
        self.acq_image = acq_image

    @property
    @abstractmethod
    def is_dirty(self) -> bool:
        """Return True if this analysis has unsaved changes."""
        ...

    def save_analysis(self, folder_path: Path) -> bool:
        """Save analysis files to the given folder. Override in subclasses."""
        return False

    def load_analysis(self, folder_path: Path) -> bool:
        """Load analysis files from the given folder. Override in subclasses."""
        return False
