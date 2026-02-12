"""Container for a list of KymImage instances loaded from a folder, a single file, or a list of file paths.

KymImageList automatically scans a folder (and optionally subfolders up to a specified depth)
for files matching a given extension and creates KymImage instances for each one.

This is a specialized version of AcqImageList that is hardcoded to use KymImage as the image class.
It provides KymImage-specific methods for radon analysis and velocity event detection.

Modes:
- Directory scan: `path` is a directory - scans recursively based on `depth`
- Single file: `path` is a file - loads that one file if it matches filters
- File list: `file_path_list` is provided - loads specified files (mutually exclusive with `path`)
- Empty: `path` is None and `file_path_list` is None - creates empty list
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

import pandas as pd

from kymflow.core.image_loaders.acq_image_list import AcqImageList
from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.core.image_loaders.radon_report import RadonReport
from kymflow.core.utils.logging import get_logger
from kymflow.core.utils.progress import ProgressCallback

if TYPE_CHECKING:
    from kymflow.core.analysis.velocity_events.velocity_events import (
        BaselineDropParams,
        NanGapParams,
        ZeroGapParams,
    )

logger = get_logger(__name__)


class KymImageList(AcqImageList[KymImage]):
    """Container for a list of KymImage instances loaded from a folder, a file, or a list of file paths.

    Automatically scans a folder (and optionally subfolders up to a specified depth)
    for files matching a given extension and creates KymImage instances for each one.
    Files are created WITHOUT loading image data (lazy loading).

    This class is hardcoded to use KymImage as the image class - it cannot be changed.
    All images in the list are guaranteed to be KymImage instances.

    Modes:
    - Directory scan: `path` is a directory - scans recursively based on `depth`
    - Single file: `path` is a file - loads that one file if it matches filters
    - File list: `file_path_list` is provided - loads specified files (mutually exclusive with `path`)
    - Empty: `path` is None and `file_path_list` is None - creates empty list

    If `path` is a file, and its extension matches `file_extension`, then the resulting
    list contains exactly that one file.

    If `path` is None and `file_path_list` is None, the resulting list is empty (backwards-compat).
    """

    def __init__(
        self,
        path: str | Path | None = None,
        *,
        file_path_list: list[str] | list[Path] | None = None,
        file_extension: str = ".tif",
        ignore_file_stub: str | None = None,
        depth: int = 1,
        follow_symlinks: bool = False,
        cancel_event: threading.Event | None = None,
        progress_cb: ProgressCallback | None = None,
    ):
        """Initialize KymImageList and automatically load files.

        Args:
            path: Directory path to scan for files, a single file path, or None for empty list.
                Mutually exclusive with `file_path_list`.
            file_path_list: List of file paths to load. Each path should be a full path to a .tif file.
                Mutually exclusive with `path`. If provided, `path` must be None.
            file_extension: File extension to match (e.g., ".tif"). Defaults to ".tif".
                Applies to all modes (directory scan, single file, and file_path_list).
            ignore_file_stub: Stub string to ignore in filenames. If a filename contains
                this stub, the file is skipped. Checks filename only, not full path.
                Defaults to None (no filtering).
            depth: Recursive scanning depth. depth=1 includes only base folder
                (code depth 0). depth=2 includes base folder and immediate subfolders
                (code depths 0,1). depth=n includes all files from code depth 0 up to
                and including code depth (n-1). Defaults to 1.
                (Only relevant when `path` is a directory.)
            follow_symlinks: If True, follow symbolic links when searching.
                Defaults to False.
            cancel_event: Optional threading.Event for cancellation support.
            progress_cb: Optional progress callback for reporting progress.
        """
        # Hardcode image_cls=KymImage - this is a list of KymImage instances only
        super().__init__(
            path=path,
            file_path_list=file_path_list,
            image_cls=KymImage,  # Always KymImage, no parameter
            file_extension=file_extension,
            ignore_file_stub=ignore_file_stub,
            depth=depth,
            follow_symlinks=follow_symlinks,
            cancel_event=cancel_event,
            progress_cb=progress_cb,
        )

    @classmethod
    def load_from_path(
        cls,
        path: str | Path | None,
        *,
        file_extension: str = ".tif",
        ignore_file_stub: str | None = None,
        depth: int = 1,
        follow_symlinks: bool = False,
        cancel_event: threading.Event | None = None,
        progress_cb: ProgressCallback | None = None,
    ) -> "KymImageList":
        """Load from a folder, file, or CSV path.
        
        Overrides parent classmethod to hardcode image_cls=KymImage.
        The image_cls parameter is not accepted - KymImageList always uses KymImage.

        Args:
            path: Path to a folder, file, CSV, or None.
            file_extension: File extension to match (e.g., ".tif").
            ignore_file_stub: Optional filename stub to ignore.
            depth: Folder scan depth (ignored for single files and CSV).
            follow_symlinks: Whether to follow symlinks during folder scan.
            cancel_event: Optional cancellation event.
            progress_cb: Optional progress callback.
        """
        if path is None:
            return cls(
                path=None,
                file_extension=file_extension,
                ignore_file_stub=ignore_file_stub,
                depth=depth,
                follow_symlinks=follow_symlinks,
                cancel_event=cancel_event,
                progress_cb=progress_cb,
            )

        path_obj = Path(path).expanduser().resolve()

        if path_obj.is_file() and path_obj.suffix.lower() == ".csv":
            file_path_list = cls.collect_paths_from_csv(
                path_obj,
                cancel_event=cancel_event,
                progress_cb=progress_cb,
            )
            return cls(
                file_path_list=file_path_list,
                file_extension=file_extension,
                ignore_file_stub=ignore_file_stub,
                cancel_event=cancel_event,
                progress_cb=progress_cb,
            )

        if path_obj.is_file():
            return cls(
                path=path_obj,
                file_extension=file_extension,
                ignore_file_stub=ignore_file_stub,
                depth=0,
                follow_symlinks=follow_symlinks,
                cancel_event=cancel_event,
                progress_cb=progress_cb,
            )

        return cls(
            path=path_obj,
            file_extension=file_extension,
            ignore_file_stub=ignore_file_stub,
            depth=depth,
            follow_symlinks=follow_symlinks,
            cancel_event=cancel_event,
            progress_cb=progress_cb,
        )

    def any_dirty_analysis(self) -> bool:
        """Return True if any image has unsaved analysis or metadata.
        
        Checks all KymImage instances in the list for dirty analysis state.
        Since all images are guaranteed to be KymImage instances, we can directly
        call get_kym_analysis() without hasattr checks.
        
        Returns:
            True if any image has unsaved analysis or metadata, False otherwise.
        """
        for image in self.images:
            try:
                if image.get_kym_analysis().is_dirty:
                    return True
            except Exception as e:
                # Log error but continue checking other images
                logger.warning(f"Failed to check dirty state for image {image.path}: {e}")
                continue
        return False

    def total_number_of_event(self) -> int:
        """Return the total number of kym events across all loaded KymImage instances.
        
        Since all images are guaranteed to be KymImage instances, we can directly
        call get_kym_analysis() without hasattr checks.
        
        Returns:
            Total number of velocity events across all images and ROIs.
        """
        total_events = 0
        for image in self.images:
            total_events += image.get_kym_analysis().total_num_velocity_events()
        return total_events

    def detect_all_events(
        self,
        *,
        baseline_drop_params: Optional["BaselineDropParams"] = None,
        nan_gap_params: Optional["NanGapParams"] = None,
        zero_gap_params: Optional["ZeroGapParams"] = None,
    ) -> None:
        """Detect velocity events for all ROIs in all loaded KymImage instances.
        
        Iterates through all images in the list and for each image, detects velocity
        events for all ROIs in that image. Since all images are guaranteed to be
        KymImage instances, we can directly call get_kym_analysis() without hasattr checks.
        
        This method does not require image data to be loaded - it works on KymImage
        instances that have analysis data available.
        
        Args:
            baseline_drop_params: Optional BaselineDropParams instance for baseline-drop detection.
                If None, uses default BaselineDropParams().
            nan_gap_params: Optional NanGapParams instance for NaN-gap detection.
                If None, uses default NanGapParams().
            zero_gap_params: Optional ZeroGapParams instance for zero-gap detection.
                If None, uses default ZeroGapParams().
        """
        for image in self.images:
            for roi_id in image.rois.get_roi_ids():
                image.get_kym_analysis().run_velocity_event_analysis(
                    roi_id,
                    baseline_drop_params=baseline_drop_params,
                    nan_gap_params=nan_gap_params,
                    zero_gap_params=zero_gap_params,
                )
    
    def get_radon_report(self) -> List[RadonReport]:
        """Generate aggregated radon velocity analysis summary report for all KymImage files.
        
        Iterates through all images in the list and calls get_radon_report() on each
        KymImage's KymAnalysis. Combines all reports into a single master list.
        Since all images are guaranteed to be KymImage instances, we can directly
        call get_kym_analysis() without hasattr checks.
        
        Returns:
            List of RadonReport instances, one per ROI across all images. Each report
            contains velocity statistics, ROI image statistics, and file metadata including
            parent_folder and grandparent_folder.
            
        Note:
            This method does not require image data to be loaded - it works on KymImage
            instances that have analysis data available. However, ROI image statistics
            (img_min, img_max, etc.) may be None if not calculated.
        """
        master_report: List[RadonReport] = []
        
        for image in self.images:
            try:
                # Get KymAnalysis instance for this image
                kym_analysis = image.get_kym_analysis()
                
                # Get radon report for all ROIs in this image
                roi_reports = kym_analysis.get_radon_report()
                
                # Calculate parent and grandparent folder information
                if image.path is not None:
                    parent_folder = image.path.parent.name if image.path.parent else None
                    grandparent_folder = (
                        image.path.parent.parent.name 
                        if image.path.parent and image.path.parent.parent 
                        else None
                    )
                else:
                    parent_folder = None
                    grandparent_folder = None
                
                # Update each RadonReport with folder metadata
                # Since RadonReport is frozen, we need to create new instances
                for roi_report in roi_reports:
                    # Create new RadonReport with updated folder information
                    updated_report = RadonReport(
                        roi_id=roi_report.roi_id,
                        vel_min=roi_report.vel_min,
                        vel_max=roi_report.vel_max,
                        vel_mean=roi_report.vel_mean,
                        vel_std=roi_report.vel_std,
                        vel_se=roi_report.vel_se,
                        img_min=roi_report.img_min,
                        img_max=roi_report.img_max,
                        img_mean=roi_report.img_mean,
                        img_std=roi_report.img_std,
                        path=roi_report.path,
                        file_name=roi_report.file_name,
                        parent_folder=parent_folder,
                        grandparent_folder=grandparent_folder,
                    )
                    master_report.append(updated_report)
                
            except Exception as e:
                # Log error but continue processing other images
                logger.warning(
                    f"Failed to generate radon report for image {image.path}: {e}"
                )
                continue
        
        return master_report
    
    def get_radon_report_df(self) -> pd.DataFrame:
        """Get radon velocity analysis summary report as a pandas DataFrame.
        
        Convenience method that calls get_radon_report() and converts the result
        to a pandas DataFrame. Each row represents one ROI with all its statistics
        and metadata.
        
        Returns:
            pandas DataFrame with columns corresponding to RadonReport fields:
            - roi_id, vel_min, vel_max, vel_mean, vel_std, vel_se
            - img_min, img_max, img_mean, img_std
            - path, file_name, parent_folder, grandparent_folder
            
        Note:
            Requires pandas to be installed. None values in the reports are preserved
            as NaN in the DataFrame.
        """
        reports = self.get_radon_report()
        
        # Convert list of RadonReport instances to list of dicts, then to DataFrame
        # Using to_dict() method for proper serialization
        report_dicts = [report.to_dict() for report in reports]
        
        df = pd.DataFrame(report_dicts)
        return df
