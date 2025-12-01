"""High-level API for working with kymograph TIFF files.

This module provides the core data structures and functionality for loading,
managing, and analyzing kymograph files. The main entry point is the `KymFile`
class, which encapsulates raw image data, microscope metadata (Olympus txt),
experimental metadata, and analysis products.

The module is designed to support lazy loading - metadata queries do not require
loading full TIFF data, making it efficient for browsing large collections of
files. Analysis algorithms are pluggable through a consistent interface.

Example:
    Basic usage for loading and analyzing a kymograph file:

    ```python
    from kymflow.core.kym_file import KymFile

    kym = KymFile("/path/to/file.tif", load_image=False)
    info = kym.to_metadata_dict(include_analysis=False)
    image = kym.ensure_image_loaded()
    kym.analyze_flow(window_size=16)
    ```
"""

from __future__ import annotations

import json
# from dataclasses import dataclass, field, fields, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Iterator, List, Optional

import numpy as np
import pandas as pd
import tifffile
# import scipy.signal

from .metadata import ExperimentMetadata, OlympusHeader, AnalysisParameters
from .kym_flow_radon import mp_analyze_flow
from .analysis_utils import _removeOutliers, _medianFilter
from .utils.logging import get_logger

logger = get_logger(__name__)

ProgressCallback = Callable[[int, int], Any]
CancelCallback = Callable[[], bool]


def _get_analysis_folder_path(tif_path: Path) -> Path:
    """
    Get the analysis folder path for a given TIFF file.

    Pattern: parent folder + '-analysis' suffix
    Example: 20221102/Capillary1_0001.tif -> 20221102/20221102-analysis/
    """
    parent = tif_path.parent  # /Users/cudmore/Dropbox/data/declan/data/20221102
    parent_name = parent.name
    analysis_folder_name = f"{parent_name}-analysis"

    # logger.info(f'parent: {parent}')
    # logger.info(f'parent_name: {parent_name}')
    # logger.info(f'analysis_folder_name: {analysis_folder_name}')

    return parent / analysis_folder_name


def _getSavePaths(tif_path: Path) -> (Path, Path):
    """
    Get the save paths for a given TIFF file.

    Returns:
        csv_path: Path to the CSV file
        json_path: Path to the JSON file
    """
    analysis_folder = _get_analysis_folder_path(tif_path)
    base_name = tif_path.stem
    csv_path = analysis_folder / f"{base_name}.csv"
    json_path = analysis_folder / f"{base_name}.json"
    return csv_path, json_path


class KymFile:
    """Encapsulates a kymograph TIFF file with metadata and analysis.

    This class provides a unified interface for working with kymograph files,
    including lazy loading of image data, metadata management, and flow analysis.
    The class is designed to support efficient metadata-only workflows where
    full image data is not needed.

    Always use KymFile properties and methods rather than accessing internal
    data structures directly. Key properties include:

    - `duration_seconds`: Total recording duration in seconds
    - `pixels_per_line`: Number of pixels per line (spatial dimension)
    - `num_lines`: Number of lines (time dimension)
    - `acquisition_metadata`: OlympusHeader with metadata (seconds_per_line, um_per_pixel, etc.)
    - `ensure_image_loaded()`: Load and return the image array

    Attributes:
        path: Path to the TIFF file.
        experiment_metadata: User-provided experimental metadata.
        acquisition_metadata: Olympus microscope header data.
        analysis_parameters: Parameters and results from flow analysis.

    Example:
        ```python
        kym = KymFile("file.tif", load_image=False)
        duration = kym.duration_seconds
        pixels = kym.pixels_per_line
        image = kym.ensure_image_loaded()
        ```
    """

    def __init__(
        self,
        path: str | Path,
        *,
        load_image: bool = False,
    ) -> None:
        """Initialize KymFile instance.

        Loads metadata from the TIFF file and accompanying Olympus header file
        if available. Optionally loads the image data immediately if requested.
        Analysis data is automatically loaded if available.

        Args:
            path: Path to the kymograph TIFF file.
            load_image: If True, load the TIFF image data immediately. If False,
                image will be loaded lazily when needed. Defaults to False for
                efficient metadata-only workflows.
        """
        self.path = Path(path)
        self._image: Optional[np.ndarray] = None

        self._experiment_metadata: ExperimentMetadata = ExperimentMetadata()
        self._header: OlympusHeader = OlympusHeader()  # header is default values

        self._analysis_parameters: AnalysisParameters = AnalysisParameters()

        self._dfAnalysis: Optional[pd.DataFrame] = None  # full df loaded from csv file

        # try and load Olympus header from txt file if it exists
        self._header = OlympusHeader.from_tif(self.path)

        self.load_analysis()

        if load_image:
            self.ensure_image_loaded()

        self._dirty: bool = False

    def __str__(self) -> str:
        return f"KymFile(filename: {self.path.name})"

    def summary_row(self) -> Dict[str, Any]:
        """Generate tabular summary for file list views.

        Returns a dictionary with key metadata fields formatted for display
        in table views. Includes file name, folder hierarchy, analysis status,
        and key acquisition parameters.

        Returns:
            Dictionary with keys suitable for table display, including file
            name, folder names, analysis status, and metadata values.
        """
        return {
            "File Name": self.path.name,
            "Parent Folder": self.path.parent.name,
            "Grandparent Folder": self.path.parent.parent.name,
            "Analyzed": "✓" if self.analysisExists else "",
            "Saved": "✓" if not self._dirty else "",
            "Window Points": self._analysis_parameters.window_size or "-",
            "pixels": self.pixels_per_line or "-",
            "lines": self.num_lines or "-",
            "duration (s)": self.duration_seconds or "-",
            "ms/line": round(self._header.seconds_per_line * 1000, 2)
            if self._header.seconds_per_line
            else "-",
            "um/pixel": self._header.um_per_pixel or "-",
            "bits/pixel": self._header.bits_per_pixel or "-",
            "note": self.experiment_metadata.note or "-",
            "path": str(self.path),  # special case, not in any shema
        }

    @classmethod
    def table_column_schema(cls) -> Dict[str, bool]:
        """Return column visibility schema for table display.

        Generates a dictionary mapping column names from summary_row() to
        visibility flags. Reuses existing form schemas where possible to
        avoid duplication of visibility rules.

        Returns:
            Dictionary mapping column names to boolean visibility flags.
            Columns not in the mapping default to visible=True.
        """
        # Mapping from summary_row keys to (dataclass_class, field_name) for schema lookup
        # Keys not in this mapping are derived/computed fields
        schema_field_mapping = {
            "note": (ExperimentMetadata, "note"),
            "um/pixel": (OlympusHeader, "um_per_pixel"),
            # "pixels", "lines", "duration (s)", "ms/line" are derived from OlympusHeader
            # but with different names, so we'd need property mappings - keeping simple for now
        }

        # Override dict for columns not in any schema (derived/computed fields)
        # Defaults to True if not specified
        visibility_overrides = {
            "path": False,  # Always hide - used as row_key only
            # All other columns default to visible=True (don't need to list them)
        }

        result = {}

        # Look up visibility from existing form schemas
        for col_name, (dataclass_cls, field_name) in schema_field_mapping.items():
            form_schema = dataclass_cls.form_schema()
            for field_def in form_schema:
                if field_def["name"] == field_name:
                    result[col_name] = field_def.get("visible", True)
                    break

        # Apply overrides (takes precedence)
        result.update(visibility_overrides)

        return result

    # ------------------------------------------------------------------
    # Loading helpers
    # ------------------------------------------------------------------
    def ensure_header_loaded(self) -> OlympusHeader:
        # header is always created in __init__
        # so we don't need to check if it is None
        # if self._header is None:
        #     self._header = OlympusHeader.from_tif(self.path)
        return self._header

    def ensure_image_loaded(self) -> np.ndarray:
        """Load and return the kymograph image data.

        Implements lazy loading - the image is only loaded from disk when
        this method is called. Subsequent calls return the cached image.
        The image is flipped horizontally to match the expected orientation.

        Returns:
            2D numpy array with shape (time, space) where axis 0 is time
            (line scans) and axis 1 is space (pixels).
        """
        if self._image is None:
            self._image = tifffile.imread(self.path)
            # abb 20251121
            self._image = np.flip(self._image, axis=1)

        # logger.info(f'image loaded: {self._image.shape} dtype:{self._image.dtype}')

        return self._image

    # ------------------------------------------------------------------
    # Metadata exposure
    # ------------------------------------------------------------------
    # abb not used
    def to_metadata_dict(self, include_analysis: bool = True) -> Dict[str, Any]:
        """Merge all metadata into a single dictionary.

        Combines Olympus header data, experimental metadata, and optionally
        analysis parameters into a unified dictionary structure. This is the
        primary format consumed by GUI tables and CLI scripts.

        Args:
            include_analysis: If True, include analysis parameters in the
                output. Defaults to True.

        Returns:
            Dictionary containing path, filename, and all metadata fields
            from header, experiment metadata, and optionally analysis.
        """
        header = (
            self.ensure_header_loaded()
        )  # header is always loaded in __init__ (can be default)
        merged: Dict[str, Any] = {
            "path": str(self.path),
            "filename": self.path.name,
            # "filesize_bytes": self.path.stat().st_size if self.path.exists() else None,
        }
        merged.update(header.to_dict())
        merged.update(self._experiment_metadata.to_dict())
        if include_analysis:
            merged["analysis"] = self._analysis_parameters.to_dict()
        return merged

    @property
    def experiment_metadata(self) -> ExperimentMetadata:
        return self._experiment_metadata

    @property
    def acquisition_metadata(self) -> OlympusHeader:
        return self._header

    @property
    def analysis_parameters(self) -> AnalysisParameters:
        return self._analysis_parameters

    def update_experiment_metadata(self, **fields: Any) -> None:
        """Update stored experimental metadata fields.

        Updates one or more fields in the experiment metadata. Unknown fields
        are silently ignored. Marks the file as dirty (needs saving).

        Args:
            **fields: Keyword arguments mapping field names to new values.
                Only fields that exist in ExperimentMetadata are updated.
        """
        logger.info(f"fields:{fields}")
        for key, value in fields.items():
            if hasattr(self._experiment_metadata, key):
                setattr(self._experiment_metadata, key, value)
            # Unknown keys are silently ignored (strict schema-only strategy)
        self._dirty = True

    # ------------------------------------------------------------------
    # Analysis hooks
    # ------------------------------------------------------------------
    def analyze_flow(
        self,
        window_size: int,
        *,  # boundary between positional and keyword-only arguments
        start_pixel: Optional[int] = None,
        stop_pixel: Optional[int] = None,
        start_line: Optional[int] = None,
        stop_line: Optional[int] = None,
        progress_callback: Optional[ProgressCallback] = None,
        is_cancelled: Optional[CancelCallback] = None,
        use_multiprocessing: bool = True,
    ) -> None:
        """Run Radon-based flow analysis on the kymograph.

        Performs a sliding window analysis along the time axis using Radon
        transforms to detect flow direction and velocity. Results are stored
        internally and can be saved using save_analysis(). The image must
        be loaded before calling this method.

        Args:
            window_size: Number of time lines per analysis window. Must be
                a multiple of 4.
            start_pixel: Start index in space dimension (inclusive). If None,
                uses 0.
            stop_pixel: Stop index in space dimension (exclusive). If None,
                uses full width.
            start_line: Start index in time dimension (inclusive). If None,
                uses 0.
            stop_line: Stop index in time dimension (exclusive). If None,
                uses full height.
            progress_callback: Optional callback function(completed, total)
                called periodically to report progress.
            is_cancelled: Optional callback function() -> bool that returns
                True if analysis should be cancelled.
            use_multiprocessing: If True, use multiprocessing for parallel
                computation. Defaults to True.

        Raises:
            ValueError: If window_size is invalid or data dimensions are
                incompatible.
            FlowCancelled: If analysis is cancelled via is_cancelled callback.
        """
        image = self.ensure_image_loaded()

        thetas, the_t, spread = mp_analyze_flow(
            image,
            window_size,
            start_pixel=start_pixel,
            stop_pixel=stop_pixel,
            start_line=start_line,
            stop_line=stop_line,
            progress_callback=progress_callback,
            is_cancelled=is_cancelled,
            use_multiprocessing=use_multiprocessing,
        )
        # Store lightweight metadata for UI access.
        self._analysis_parameters = AnalysisParameters(
            algorithm="mpRadon",
            window_size=window_size,
            start_pixel=start_pixel,
            stop_pixel=stop_pixel,
            start_line=start_line,
            stop_line=stop_line,
            use_multiprocessing=use_multiprocessing,
            analyzed_at=datetime.now(timezone.utc),
        )

        secondsPerLine = self._header.seconds_per_line
        umPerPixel = self._header.um_per_pixel

        # convert to physical units
        drewTime = the_t * secondsPerLine

        # convert radians to angle
        _rad = np.deg2rad(thetas)
        drewVelocity = (umPerPixel / secondsPerLine) * np.tan(_rad)
        drewVelocity = drewVelocity / 1000  # mm/s

        # debug, count inf and 0 tan
        # numZeros = np.count_nonzero(drewVelocity==0)
        # logger.info(f'  1) numZeros:{numZeros}')

        # remove inf and 0 tan()
        # np.tan(90 deg) is returning 1e16 rather than inf
        logger.info("not removing inf/0 velocity -->> use this to calculate stalls")
        # tan90or0 = (drewVelocity > 1e6) | (drewVelocity == 0)
        # drewVelocity[tan90or0] = float('nan')

        # our original in kym_file_v0.py saved these columns:
        # time,velocity,parentFolder,file,algorithm,delx,delt,numLines,pntsPerLine,cleanVelocity,absVelocity

        cleanVelocity = _removeOutliers(drewVelocity)
        cleanVelocity = _medianFilter(cleanVelocity, window_size=5)

        self._dfAnalysis = pd.DataFrame(
            {
                "time": drewTime,
                "velocity": drewVelocity,
                "parentFolder": self.path.parent.name,
                "file": self.path.name,
                "algorithm": "mpRadon",
                "delx": umPerPixel,
                "delt": secondsPerLine,
                "numLines": self.num_lines,
                "pntsPerLine": self.pixels_per_line,
                "cleanVelocity": cleanVelocity,  # what were these in v0
                "absVelocity": abs(cleanVelocity),  # what were these in v0
            }
        )

        # Mark as dirty so save_analysis() will save
        self._dirty = True

        # Auto-save analysis after successful computation
        # self.save_analysis()

    def save_analysis(self) -> bool:
        """Save analysis results to CSV and JSON files.

        Saves the analysis DataFrame to a CSV file and metadata to a JSON file
        in the analysis folder (parent folder + '-analysis' suffix). Only saves
        if the file is marked as dirty (has unsaved changes).

        CSV contains: time, velocity, parentFolder, file, algorithm, delx, delt,
        numLines, pntsPerLine, cleanVelocity, absVelocity.

        JSON contains: OlympusHeader, ExperimentMetadata, AnalysisParameters.

        Returns:
            True if analysis was saved successfully, False if no analysis exists
            or file is not dirty.
        """
        if not self._dirty:
            logger.info(f"Analysis does not need to be for  {self.path.name}")
            return False

        if not self.analysisExists:
            logger.warning(f"No analysis to save for {self.path.name}")
            return False

        csv_path, json_path = _getSavePaths(self.path)

        # Create analysis folder if it doesn't exist
        analysis_folder = csv_path.parent
        analysis_folder.mkdir(parents=True, exist_ok=True)

        # our original in kym_file_v0.py saved these columns:
        # time,velocity,parentFolder,file,algorithm,delx,delt,numLines,pntsPerLine,cleanVelocity,absVelocity

        # Save CSV (no index, no header row)
        self._dfAnalysis.to_csv(csv_path, index=False)
        logger.info(f"Saved analysis CSV to {csv_path}")

        # Build JSON metadata
        metadata = {
            "olympus_header": self.ensure_header_loaded().to_dict(),
            "experiment_metadata": self._experiment_metadata.to_dict(),
            "analysis_parameters": self._analysis_parameters.to_dict(),
        }

        # Save JSON
        with open(json_path, "w") as f:
            json.dump(metadata, f, indent=2, default=str)
        logger.info(f"Saved analysis metadata to {json_path}")

        # Update analysis snapshot with result path
        self._analysis_parameters.result_path = csv_path

        self._dirty = False
        return True

    def load_metadata(self) -> bool:
        """Load metadata from saved JSON file.

        Loads Olympus header, experiment metadata, and analysis parameters
        from the JSON file in the analysis folder. Overwrites current metadata
        if the file exists.

        Returns:
            True if metadata was loaded successfully, False if the JSON file
            does not exist.
        """
        _, json_path = _getSavePaths(self.path)
        if not json_path.exists():
            logger.info(f"No metadata file found for {self.path.name}")
            return False

        # Load JSON metadata
        with open(json_path, "r") as f:
            metadata = json.load(f)

        # Restore OlympusHeader if not already loaded
        if "olympus_header" in metadata:
            header_data = metadata["olympus_header"]
            self._header = OlympusHeader(
                um_per_pixel=header_data.get("um_per_pixel"),
                seconds_per_line=header_data.get("seconds_per_line"),
                duration_seconds=header_data.get("duration_seconds"),
                pixels_per_line=header_data.get("pixels_per_line"),
                num_lines=header_data.get("num_lines"),
                bits_per_pixel=header_data.get("bits_per_pixel"),
                date_str=header_data.get("date"),
                time_str=header_data.get("time"),
            )

        # Restore ExperimentMetadata
        if "experiment_metadata" in metadata:
            bio_data = metadata["experiment_metadata"]
            self._experiment_metadata = ExperimentMetadata.from_dict(bio_data)

        # Restore AnalysisParameters
        if "analysis_parameters" in metadata:
            snap_data = metadata["analysis_parameters"]
            analyzed_at_str = snap_data.get("analyzed_at")
            analyzed_at = (
                datetime.fromisoformat(analyzed_at_str) if analyzed_at_str else None
            )
            
            # Handle backward compatibility: check for old nested structure
            if "parameters" in snap_data:
                # Old structure: extract from nested parameters dict
                params = snap_data.get("parameters", {})
                self._analysis_parameters = AnalysisParameters(
                    algorithm=snap_data.get("algorithm"),
                    window_size=params.get("window_size"),
                    start_pixel=params.get("start_pixel"),
                    stop_pixel=params.get("stop_pixel"),
                    start_line=params.get("start_line"),
                    stop_line=params.get("stop_line"),
                    use_multiprocessing=params.get("use_multiprocessing", True),
                    analyzed_at=analyzed_at,
                    result_path=Path(snap_data["result_path"])
                    if snap_data.get("result_path")
                    else None,
                )
            else:
                # New flattened structure: fields are at top level
                self._analysis_parameters = AnalysisParameters(
                    algorithm=snap_data.get("algorithm"),
                    window_size=snap_data.get("window_size"),
                    start_pixel=snap_data.get("start_pixel"),
                    stop_pixel=snap_data.get("stop_pixel"),
                    start_line=snap_data.get("start_line"),
                    stop_line=snap_data.get("stop_line"),
                    use_multiprocessing=snap_data.get("use_multiprocessing", True),
                    analyzed_at=analyzed_at,
                    result_path=Path(snap_data["result_path"])
                    if snap_data.get("result_path")
                    else None,
                )

        return True

    def load_analysis(self) -> bool:
        """Load analysis results from CSV and JSON files.

        Loads the analysis DataFrame from CSV and metadata from JSON in the
        analysis folder. This is called automatically during initialization
        if analysis files exist.

        Returns:
            True if analysis was loaded successfully, False if the CSV file
            does not exist.
        """
        csv_path, _ = _getSavePaths(self.path)

        # Check if files exist
        if not csv_path.exists():
            logger.info(f"No analysis files found for {self.path.name}")
            return False

        # Load CSV into DataFrame
        self._dfAnalysis = pd.read_csv(csv_path)

        self.load_metadata()

        # logger.info(f"Loaded analysis for {self.path.name}")
        return True

    @property
    def analysisExists(self) -> bool:
        """
        Check if analysis has been loaded.
        """
        return self._dfAnalysis is not None

    def getAnalysisValue(self, key: str) -> Any:
        """Get a value from the analysis DataFrame."""
        if self._dfAnalysis is None:
            logger.warning(f"No analysis loaded for {self.path.name}")
            return None
        if key not in self._dfAnalysis.columns:
            logger.warning(
                f"Key {key} not found in analysis DataFrame for {self.path.name}"
            )
            logger.warning(f"  Columns: {self._dfAnalysis.columns}")
            return None
        return self._dfAnalysis[key].values

    # ------------------------------------------------------------------
    # Convenience information
    # ------------------------------------------------------------------
    @property
    def num_lines(self) -> Optional[int]:
        """Number of lines (time dimension) in the kymograph."""
        header = self.ensure_header_loaded()
        return header.num_lines

    @property
    def pixels_per_line(self) -> Optional[int]:
        """Number of pixels per line (spatial dimension) in the kymograph."""
        header = self.ensure_header_loaded()
        return header.pixels_per_line

    @property
    def duration_seconds(self) -> Optional[float]:
        """Total recording duration in seconds."""
        header = self.ensure_header_loaded()
        return header.duration_seconds


# ----------------------------------------------------------------------
# Folder level utilities
# ----------------------------------------------------------------------
def iter_metadata(
    root: str | Path,
    *,
    glob: str = "*.tif",
    follow_symlinks: bool = False,
) -> Iterator[Dict[str, Any]]:
    """Iterate over metadata for all TIFF files under a root directory.

    Efficiently scans a directory tree for TIFF files and yields metadata
    dictionaries for each file. Only metadata is loaded - image pixels are
    not read, making this suitable for browsing large collections.

    Args:
        root: Root directory to search, or a single file path.
        glob: Glob pattern for matching files. Defaults to "*.tif".
        follow_symlinks: If True, follow symbolic links when searching.
            Defaults to False.

    Yields:
        Dictionary containing metadata for each TIFF file found, including
        path, filename, Olympus header data, and experiment metadata.
        Files that cannot be loaded are silently skipped.
    """
    base = Path(root)
    paths: Iterable[Path]
    if base.is_dir():
        paths = base.rglob(glob) if follow_symlinks else base.glob(f"**/{glob}")
    else:
        paths = [base]

    for tif_path in paths:
        if not tif_path.is_file():
            continue
        try:
            kym = KymFile(tif_path, load_image=False)
            yield kym.to_metadata_dict(include_analysis=False)
        except Exception:
            # Metadata collection should be resilient; callers can log errors.
            continue


def collect_metadata(root: str | Path, **kwargs: Any) -> List[Dict[str, Any]]:
    """Collect metadata for all TIFF files under a root directory.

    Convenience wrapper around iter_metadata() that collects all results
    into a list. Useful for GUI applications that need all metadata at once.

    Args:
        root: Root directory to search, or a single file path.
        **kwargs: Additional arguments passed to iter_metadata() (glob,
            follow_symlinks, etc.).

    Returns:
        List of metadata dictionaries, one per TIFF file found.
    """
    return list(iter_metadata(root, **kwargs))
