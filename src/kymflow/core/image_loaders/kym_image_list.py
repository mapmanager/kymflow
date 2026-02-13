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
from typing import TYPE_CHECKING, Dict, List, Optional

import pandas as pd
from dataclasses import replace as dataclass_replace

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
        csv_source_path: Path | None = None,
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
            csv_source_path=csv_source_path,
            image_cls=KymImage,  # Always KymImage, no parameter
            file_extension=file_extension,
            ignore_file_stub=ignore_file_stub,
            depth=depth,
            follow_symlinks=follow_symlinks,
            cancel_event=cancel_event,
            progress_cb=progress_cb,
        )
        self._radon_report_cache: Dict[str, List[RadonReport]] = {}
        self._load_radon_report_db()

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
                csv_source_path=path_obj,
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
    
    def _get_radon_db_path(self) -> Optional[Path]:
        """Path to radon_report_db.csv for current mode.
        
        Returns None for single-file mode, empty list, or file-list from in-memory list.
        """
        if self._get_mode() == "file":
            return None
        if self._get_mode() == "folder" and self._folder is not None:
            return self._folder / "radon_report_db.csv"
        if self._get_mode() == "file_list" and self._csv_source_path is not None:
            return self._csv_source_path.parent / f"{self._csv_source_path.stem}_radon_report_db.csv"
        return None

    def _load_radon_report_db(self) -> None:
        """Load radon report database from CSV if it exists."""
        db_path = self._get_radon_db_path()
        if db_path is None or not db_path.exists():
            self._radon_report_cache = {}
            return
        try:
            df = pd.read_csv(db_path)
            base = self._get_base_path()
            cache: Dict[str, List[RadonReport]] = {}
            for _, row in df.iterrows():
                d = row.to_dict()
                path_val = d.get("path")
                if pd.isna(path_val) or path_val is None or path_val == "":
                    if base is not None and "rel_path" in d and d.get("rel_path"):
                        path_val = str(base / str(d["rel_path"]))
                    else:
                        continue
                path_str = str(path_val)
                report = RadonReport.from_dict(d)
                if path_str not in cache:
                    cache[path_str] = []
                cache[path_str].append(report)
            self._radon_report_cache = cache
        except Exception as e:
            logger.warning(f"Failed to load radon report DB from {db_path}: {e}")
            self._radon_report_cache = {}

    def save_radon_report_db(self) -> bool:
        """Persist radon report cache to CSV. Returns True if saved, False if no DB path."""
        db_path = self._get_radon_db_path()
        if db_path is None:
            return False
        reports = self.get_radon_report()
        if not reports:
            return False
        report_dicts = [r.to_dict() for r in reports]
        df = pd.DataFrame(report_dicts)
        df.to_csv(db_path, index=False)
        return True

    def update_radon_report_for_image(self, kym_image: KymImage) -> None:
        """Update radon report cache for one KymImage (e.g. after user saves analysis)."""
        if kym_image.path is None:
            return
        path_str = str(kym_image.path)
        try:
            roi_reports = kym_image.get_kym_analysis().get_radon_report()
            base = self._get_base_path()
            rel_path = None
            if base is not None and kym_image.path is not None:
                try:
                    base_res = Path(base).resolve()
                    path_res = Path(kym_image.path).resolve()
                    rel_path = str(path_res.relative_to(base_res))
                except ValueError:
                    rel_path = Path(kym_image.path).name
            with_rel = [dataclass_replace(r, rel_path=rel_path) for r in roi_reports]
            self._radon_report_cache[path_str] = with_rel
            self.save_radon_report_db()
        except Exception as e:
            logger.warning(f"Failed to update radon report for {path_str}: {e}")

    def _build_reports_from_images(self) -> List[RadonReport]:
        """Build radon reports from images (delegate to KymAnalysis, add rel_path). Populates cache."""
        master_report: List[RadonReport] = []
        base = self._get_base_path()
        for image in self.images:
            try:
                roi_reports = image.get_kym_analysis().get_radon_report()
                rel_path = None
                if base is not None and image.path is not None:
                    try:
                        base_res = Path(base).resolve()
                        path_res = Path(image.path).resolve()
                        rel_path = str(path_res.relative_to(base_res))
                    except ValueError:
                        rel_path = Path(image.path).name
                with_rel = [dataclass_replace(r, rel_path=rel_path) for r in roi_reports]
                if image.path is not None:
                    self._radon_report_cache[str(image.path)] = with_rel
                master_report.extend(with_rel)
            except Exception as e:
                logger.warning(f"Failed to generate radon report for image {image.path}: {e}")
        return master_report

    def get_radon_report(self) -> List[RadonReport]:
        """Generate aggregated radon velocity analysis summary report for all KymImage files.
        
        Uses cached reports when available; otherwise builds from KymAnalysis per image
        and adds rel_path. Order follows self.images.
        
        Returns:
            List of RadonReport instances, one per ROI across all images.
        """
        if self._radon_report_cache:
            master: List[RadonReport] = []
            for image in self.images:
                if image.path is None:
                    continue
                reports = self._radon_report_cache.get(str(image.path), [])
                master.extend(reports)
            return master
        return self._build_reports_from_images()

    def get_radon_report_df(self) -> pd.DataFrame:
        """Get radon velocity analysis summary report as a pandas DataFrame.
        
        Includes row_id column (path|roi_id) for unique row identification.
        """
        reports = self.get_radon_report()
        report_dicts = [r.to_dict() for r in reports]
        df = pd.DataFrame(report_dicts)
        if not df.empty and "path" in df.columns and "roi_id" in df.columns:
            df["row_id"] = df.apply(
                lambda r: f"{r['path']}|{r['roi_id']}" if pd.notna(r.get("path")) else "",
                axis=1,
            )
        return df
