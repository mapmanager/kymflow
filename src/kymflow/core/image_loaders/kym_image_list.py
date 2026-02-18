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
from dataclasses import fields, replace as dataclass_replace
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

import pandas as pd

from kymflow.core.image_loaders.acq_image_list import AcqImageList
from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.core.image_loaders.radon_report import RadonReport
from kymflow.core.image_loaders.velocity_event_db import VelocityEventDb
from kymflow.core.utils.logging import get_logger
from kymflow.core.utils.progress import CancelledError, ProgressCallback, ProgressMessage

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
        self._load_radon_report_db(progress_cb=progress_cb, cancel_event=cancel_event)
        self._velocity_event_db = VelocityEventDb(
            db_path=self._get_velocity_event_db_path(),
            base_path_provider=self._get_base_path,
        )
        self._velocity_event_db.load(
            images_provider=lambda: self.images,
            progress_cb=progress_cb,
            cancel_event=cancel_event,
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
            self.update_velocity_event_cache_only(image)

    def get_velocity_event_df(self) -> pd.DataFrame:
        """Get velocity event database as a pandas DataFrame.
        
        Returns DataFrame with _unique_row_id, path, roi_id, and event fields.
        """
        return self._velocity_event_db.get_df()

    def update_velocity_event_cache_only(self, kym_image: KymImage) -> None:
        """Update velocity event cache in memory only (e.g. after detect_all_events).
        
        Does NOT persist to CSV. Use update_velocity_event_for_image when user saves.
        """
        self._velocity_event_db.update_from_image(kym_image)

    def update_velocity_event_for_image(self, kym_image: KymImage) -> None:
        """Update velocity event cache and persist to CSV (e.g. after user saves analysis)."""
        self._velocity_event_db.update_from_image_and_persist(kym_image)

    def rebuild_velocity_event_db_and_save(self) -> bool:
        """Rebuild velocity event cache from all images and persist to CSV.

        Use after batch scripts that mutate events (e.g. remove-all).
        Returns True if saved, False if no DB path (single-file mode).
        """
        if self._velocity_event_db.get_db_path() is None:
            return False
        self._velocity_event_db.rebuild_from_images(images_provider=lambda: self.images)
        return self._velocity_event_db.save()

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

    def _get_velocity_event_db_path(self) -> Optional[Path]:
        """Path to kym_event_db.csv for current mode.
        
        Returns None for single-file mode, empty list, or file-list from in-memory list.
        """
        if self._get_mode() == "file":
            return None
        if self._get_mode() == "folder" and self._folder is not None:
            return self._folder / "kym_event_db.csv"
        if self._get_mode() == "file_list" and self._csv_source_path is not None:
            return self._csv_source_path.parent / f"{self._csv_source_path.stem}_kym_event_db.csv"
        return None

    def _load_radon_report_db(
        self,
        progress_cb: ProgressCallback | None = None,
        cancel_event: threading.Event | None = None,
    ) -> None:
        """Load radon report database from CSV if it exists; rebuild if missing or stale."""
        db_path = self._get_radon_db_path()
        if db_path is None:
            return

        need_rebuild = False
        rebuild_reason = ""
        if db_path.exists():
            try:
                df = pd.read_csv(db_path)
                expected_cols = {f.name for f in fields(RadonReport)}
                missing = expected_cols - set(df.columns)
                if missing:
                    need_rebuild = True
                    rebuild_reason = "schema was stale"
                else:
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
                need_rebuild = True
                rebuild_reason = "load failed"
        else:
            need_rebuild = True
            rebuild_reason = "no DB file"

        if need_rebuild:
            n = len(self.images)
            if progress_cb is not None:
                progress_cb(
                    ProgressMessage(
                        phase="rebuild_radon_db",
                        done=0,
                        total=n,
                        detail="Rebuilding radon database...",
                    )
                )
            self._build_reports_from_images(
                progress_cb=progress_cb,
                cancel_event=cancel_event,
            )
            if cancel_event is not None and cancel_event.is_set():
                return
            # Note: We persist to CSV after rebuild (e.g. when schema was stale or DB missing).
            # So first load with new code/schema writes CSV without explicit user save. Preferred
            # behavior would be not to save unless the user explicitly saves; leaving as-is.
            self.save_radon_report_db()
            logger.info("Radon DB load complete (rebuilt from images: %s)", rebuild_reason)
            if progress_cb is not None and n > 0:
                progress_cb(
                    ProgressMessage(
                        phase="rebuild_radon_db",
                        done=n,
                        total=n,
                        detail="Done",
                    )
                )

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
        if not df.empty and "path" in df.columns and "roi_id" in df.columns:
            df["_unique_row_id"] = df.apply(
                lambda r: f"{r['path']}|{r['roi_id']}" if pd.notna(r.get("path")) else "",
                axis=1,
            )
        logger.info("Saving radon report DB to:")
        logger.info(f"  {db_path}")
        print(df.head())

        df.to_csv(db_path, index=False)
        return True

    def update_radon_report_cache_only(self, kym_image: KymImage) -> None:
        """Update radon report cache in memory only (e.g. after Analyze Flow completes).

        Does NOT persist to CSV. Use update_radon_report_for_image when user explicitly saves.
        """
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
        except Exception as e:
            logger.warning(f"Failed to update radon report cache for {path_str}: {e}")

    def update_radon_report_for_image(self, kym_image: KymImage) -> None:
        """Update radon report cache and persist to CSV (e.g. after user saves analysis)."""
        if kym_image.path is None:
            return
        self.update_radon_report_cache_only(kym_image)
        self.save_radon_report_db()

    def _build_reports_from_images(
        self,
        progress_cb: ProgressCallback | None = None,
        cancel_event: threading.Event | None = None,
    ) -> List[RadonReport]:
        """Build radon reports from images (delegate to KymAnalysis, add rel_path). Populates cache."""
        master_report: List[RadonReport] = []
        base = self._get_base_path()
        n = len(self.images)
        progress_every = max(1, n // 20) if n > 0 else 1
        for i, image in enumerate(self.images):
            if cancel_event is not None and cancel_event.is_set():
                raise CancelledError("Cancelled during radon DB rebuild")
            try:
                roi_reports = image.get_kym_analysis().get_radon_report()
                rel_path = None
                if base is not None and image.path is not None:
                    try:
                        base_res = Path(base).resolve()
                        path_res = Path(image.path).resolve()
                        rel_path = str(path_res.relative_to(base_res))
                    except ValueError as e:
                        logger.error(f"Failed to get relative path for image {image.path}, e is: {e}")
                        rel_path = Path(image.path).name
                with_rel = [dataclass_replace(r, rel_path=rel_path) for r in roi_reports]
                if image.path is not None:
                    self._radon_report_cache[str(image.path)] = with_rel
                master_report.extend(with_rel)
            except Exception as e:
                logger.warning(f"Failed to generate radon report for image {image.path}: {e}")
            if progress_cb is not None and n > 0:
                if (i + 1) % progress_every == 0 or (i + 1) == n:
                    progress_cb(
                        ProgressMessage(
                            phase="rebuild_radon_db",
                            done=i + 1,
                            total=n,
                            detail=f"{i + 1}/{n}",
                        )
                    )
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
        
        Includes _unique_row_id (path|roi_id) for unique row identification.
        """
        reports = self.get_radon_report()
        report_dicts = [r.to_dict() for r in reports]
        df = pd.DataFrame(report_dicts)
        if not df.empty and "path" in df.columns and "roi_id" in df.columns:
            unique_id = df.apply(
                lambda r: f"{r['path']}|{r['roi_id']}" if pd.notna(r.get("path")) else "",
                axis=1,
            )
            df["_unique_row_id"] = unique_id
            df["row_id"] = unique_id
        return df
