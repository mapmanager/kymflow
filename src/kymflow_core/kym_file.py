"""
High level API to interact with kymograph files.

Goals for this module:
    * Provide a single entry point (`KymFile`) that encapsulates raw image
      data, microscope metadata (Olympus txt), biology metadata, and analysis
      products.
    * Allow callers (CLI, GUI, scripts) to load only what they need. Metadata
      queries should not read full TIFF data.
    * Offer convenience utilities to traverse folders and aggregate metadata.
    * Keep analysis hooks pluggable so future algorithms can share a consistent
      interface.

Typical usage from NiceGUI or scripting code::

    from kymflow_core.kym_file import KymFile

    kym = KymFile("/path/to/file.tif", load_image=False)
    info = kym.to_metadata_dict(include_analysis=False)
    image = kym.ensure_image_loaded()
    result = kym.analyze_flow(window_size=16)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, fields
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Iterator, List, Optional

import numpy as np
import pandas as pd
import tifffile

from .read_olympus_header import _readOlympusHeader
from .kym_flow_radon_gpt import mp_analyze_flow

from .utils.logging import get_logger
logger = get_logger(__name__)

ProgressCallback = Callable[[int, int], Any]
CancelCallback = Callable[[], bool]


def _get_analysis_folder_path(tif_path: Path) -> Path:
    """
    Get the analysis folder path for a given TIFF file.
    
    Pattern: parent folder + '-analysis' suffix
    Example: 20221102/Capillary1_0001.tif -> 20221102-analysis/
    """
    parent = tif_path.parent
    parent_name = parent.name
    analysis_folder_name = f"{parent_name}-analysis"
    return parent.parent / analysis_folder_name


@dataclass
class OlympusHeader:
    """Structured representation of Olympus txt header values."""

    um_per_pixel: Optional[float] = None
    seconds_per_line: Optional[float] = None
    duration_seconds: Optional[float] = None
    pixels_per_line: Optional[int] = None
    num_lines: Optional[int] = None
    bits_per_pixel: Optional[int] = None
    date_str: Optional[str] = None
    time_str: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_tif(cls, tif_path: Path) -> "OlympusHeader":
        """Load accompanying Olympus txt file."""
        parsed = _readOlympusHeader(str(tif_path))
        if not parsed:
            return cls()
        return cls(
            um_per_pixel=parsed.get("umPerPixel"),
            seconds_per_line=parsed.get("secondsPerLine"),
            duration_seconds=parsed.get("durImage_sec"),
            pixels_per_line=parsed.get("pixelsPerLine"),
            num_lines=parsed.get("numLines"),
            bits_per_pixel=parsed.get("bitsPerPixel"),
            date_str=parsed.get("dateStr"),
            time_str=parsed.get("timeStr"),
            raw=parsed,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Return a dict-friendly version."""
        return {
            "um_per_pixel": self.um_per_pixel,
            "seconds_per_line": self.seconds_per_line,
            "duration_seconds": self.duration_seconds,
            "pixels_per_line": self.pixels_per_line,
            "num_lines": self.num_lines,
            "bits_per_pixel": self.bits_per_pixel,
            "date": self.date_str,
            "time": self.time_str,
        }


@dataclass
class BiologyMetadata:
    """
    User provided biology metadata.

    Acts as a thin structured layer on top of a dict to ensure consumers get
    predictable keys while still allowing arbitrary extensions through
    `extra`.
    """

    species: Optional[str] = None
    cell_type: Optional[str] = None
    region: Optional[str] = None
    note: Optional[str] = None
    acquisition_date: Optional[str] = None
    acquisition_time: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: Optional[Dict[str, Any]]) -> "BiologyMetadata":
        """Create instance separating known keys from arbitrary extras."""
        payload = payload or {}
        valid = {f.name for f in fields(cls) if f.init and f.name != "extra"}
        known = {k: payload[k] for k in payload.keys() & valid}
        extra = {k: v for k, v in payload.items() if k not in valid}
        return cls(**known, extra=extra)

    def to_dict(self) -> Dict[str, Any]:
        meta = {
            "species": self.species,
            "cell_type": self.cell_type,
            "region": self.region,
            "note": self.note,
            "acq_date": self.acquisition_date,
            "acq_time": self.acquisition_time,
        }
        meta.update(self.extra)
        return meta


@dataclass
class AnalysisSnapshot:
    """Metadata describing the last performed analysis."""

    algorithm: str
    parameters: Dict[str, Any]
    analyzed_at: datetime
    result_path: Optional[Path] = None
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "algorithm": self.algorithm,
            "parameters": self.parameters,
            "analyzed_at": self.analyzed_at.isoformat(),
            "result_path": str(self.result_path) if self.result_path else None,
            "notes": self.notes,
        }


class KymFile:
    """
    Encapsulates everything about a single kymograph (TIFF + metadata).

    Parameters
    ----------
    path:
        Path to the `.tif` file.
    load_image:
        If True, load the TIFF data immediately. Set False for metadata-only
        workflows.
    biology_metadata:
        Optional dictionary of user-supplied metadata that overrides the values
        inferred from Olympus header.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        load_image: bool = False,
        biology_metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.path = Path(path)
        self._image: Optional[np.ndarray] = None
        self._header: Optional[OlympusHeader] = None
        self._analysis: Optional[AnalysisSnapshot] = None
        self._analysis_payload: Optional[Dict[str, Any]] = None
        self._biology = BiologyMetadata.from_dict(biology_metadata)

        if load_image:
            self.ensure_image_loaded()

    # ------------------------------------------------------------------
    # Loading helpers
    # ------------------------------------------------------------------
    def ensure_header_loaded(self) -> OlympusHeader:
        if self._header is None:
            self._header = OlympusHeader.from_tif(self.path)
        return self._header

    def ensure_image_loaded(self) -> np.ndarray:
        if self._image is None:
            self._image = tifffile.imread(self.path)
        logger.info(f'image loaded: {self._image.shape}')
        return self._image

    # ------------------------------------------------------------------
    # Metadata exposure
    # ------------------------------------------------------------------
    def to_metadata_dict(self, include_analysis: bool = True) -> Dict[str, Any]:
        """
        Merge Olympus header + biology metadata + derived info.

        This is the primary structure consumed by GUI tables and CLI scripts.
        """
        header = self.ensure_header_loaded()
        merged: Dict[str, Any] = {
            "path": str(self.path),
            "filename": self.path.name,
            "filesize_bytes": self.path.stat().st_size if self.path.exists() else None,
        }
        merged.update(header.to_dict())
        merged.update(self._biology.to_dict())
        if include_analysis and self._analysis:
            merged["analysis"] = self._analysis.to_dict()
        return merged

    @property
    def biology_metadata(self) -> BiologyMetadata:
        return self._biology

    def update_biology_metadata(self, **fields: Any) -> None:
        """Update stored biology metadata and merge into the `extra` dict."""
        for key, value in fields.items():
            if hasattr(self._biology, key):
                setattr(self._biology, key, value)
            else:
                self._biology.extra[key] = value

    # ------------------------------------------------------------------
    # Analysis hooks
    # ------------------------------------------------------------------
    def analyze_flow(
        self,
        window_size: int,
        *,
        start_pixel: Optional[int] = None,
        stop_pixel: Optional[int] = None,
        progress_callback: Optional[ProgressCallback] = None,
        is_cancelled: Optional[CancelCallback] = None,
        use_multiprocessing: bool = True,
    ) -> Dict[str, Any]:
        """
        Run the Radon-based flow analysis and persist the metadata snapshot.

        Returns a dictionary payload (angles, timestamps, etc.) that can be
        serialized by callers. Persistence (e.g., CSV, parquet) is explicitly
        left to higher-level services to keep this class IO-light.
        """
        image = self.ensure_image_loaded()
        result = mp_analyze_flow(
            image,
            window_size,
            start_pixel=start_pixel,
            stop_pixel=stop_pixel,
            progress_callback=progress_callback,
            is_cancelled=is_cancelled,
            use_multiprocessing=use_multiprocessing,
        )
        # Store lightweight metadata for UI access.
        self._analysis = AnalysisSnapshot(
            algorithm="radon_flow_v1",
            parameters={
                "window_size": window_size,
                "start_pixel": start_pixel,
                "stop_pixel": stop_pixel,
                "use_multiprocessing": use_multiprocessing,
            },
            analyzed_at=datetime.utcnow(),
        )
        thetas, the_t, spread = result
        self._analysis_payload = {
            "theta_degrees": thetas,
            "time_indices": the_t,
            "spread_matrix": spread,
        }
        
        # Auto-save analysis after successful computation
        # self.save_analysis()
        
        return self._analysis_payload

    def get_analysis_payload(self) -> Optional[Dict[str, Any]]:
        """
        Return the raw analysis numpy arrays from the last computation.

        Consumers can convert to pandas or save to disk. None indicates no
        analysis has been performed in this session.
        """
        return self._analysis_payload

    def save_analysis(self) -> bool:
        """
        Save analysis to CSV (data) and JSON (metadata) files.
        
        CSV contains: time, velocity, theta_degrees, time_indices
        JSON contains: OlympusHeader, BiologyMetadata, AnalysisSnapshot
        
        Returns True if successful, False otherwise.
        """
        if self._analysis_payload is None:
            logger.warning(f"No analysis to save for {self.path.name}")
            return False
        
        try:
            # Get analysis folder path and create if needed
            analysis_folder = _get_analysis_folder_path(self.path)
            analysis_folder.mkdir(parents=True, exist_ok=True)
            
            # Base filename without extension
            base_name = self.path.stem
            csv_path = analysis_folder / f"{base_name}.csv"
            json_path = analysis_folder / f"{base_name}.json"
            
            # Convert analysis payload to DataFrame
            header = self.ensure_header_loaded()
            seconds_per_line = header.seconds_per_line or 1.0
            um_per_pixel = header.um_per_pixel or 1.0
            
            time_indices = self._analysis_payload["time_indices"]
            theta_degrees = self._analysis_payload["theta_degrees"]
            
            # Calculate time and velocity
            time_axis = time_indices * seconds_per_line
            theta_rad = np.deg2rad(theta_degrees)
            velocity = (um_per_pixel / seconds_per_line) * np.tan(theta_rad) / 1000.0  # mm/s
            
            # Create DataFrame
            df = pd.DataFrame({
                "time": time_axis,
                "velocity": velocity,
                "theta_degrees": theta_degrees,
                "time_indices": time_indices,
            })
            
            # Save CSV (no index, no header row)
            df.to_csv(csv_path, index=False, header=False)
            logger.info(f"Saved analysis CSV to {csv_path}")
            
            # Build JSON metadata
            metadata = {
                "olympus_header": self.ensure_header_loaded().to_dict(),
                "biology_metadata": self._biology.to_dict(),
                "analysis_snapshot": self._analysis.to_dict() if self._analysis else None,
            }
            
            # Save JSON
            with open(json_path, "w") as f:
                json.dump(metadata, f, indent=2, default=str)
            logger.info(f"Saved analysis metadata to {json_path}")
            
            # Update analysis snapshot with result path
            if self._analysis:
                self._analysis.result_path = csv_path
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to save analysis for {self.path.name}: {e}")
            return False

    def load_analysis(self) -> bool:
        """
        Load analysis from CSV (data) and JSON (metadata) files.
        
        Restores _analysis_payload, _header, _biology, and _analysis.
        
        Returns True if successful, False otherwise.
        """
        try:
            # Get analysis folder path
            analysis_folder = _get_analysis_folder_path(self.path)
            
            # Base filename without extension
            base_name = self.path.stem
            csv_path = analysis_folder / f"{base_name}.csv"
            json_path = analysis_folder / f"{base_name}.json"
            
            # Check if files exist
            if not csv_path.exists() or not json_path.exists():
                logger.info(f"No analysis files found for {self.path.name}")
                return False
            
            # Load CSV into DataFrame
            df = pd.read_csv(csv_path, header=None, names=["time", "velocity", "theta_degrees", "time_indices"])
            
            # Restore analysis payload
            self._analysis_payload = {
                "time_indices": df["time_indices"].values,
                "theta_degrees": df["theta_degrees"].values,
                "spread_matrix": None,  # Not saved in CSV, would need to be in a different format
            }
            
            # Load JSON metadata
            with open(json_path, "r") as f:
                metadata = json.load(f)
            
            # Restore OlympusHeader if not already loaded
            if self._header is None and "olympus_header" in metadata:
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
            
            # Restore BiologyMetadata
            if "biology_metadata" in metadata:
                bio_data = metadata["biology_metadata"]
                self._biology = BiologyMetadata.from_dict(bio_data)
            
            # Restore AnalysisSnapshot
            if "analysis_snapshot" in metadata and metadata["analysis_snapshot"]:
                snap_data = metadata["analysis_snapshot"]
                self._analysis = AnalysisSnapshot(
                    algorithm=snap_data.get("algorithm", "radon_flow_v1"),
                    parameters=snap_data.get("parameters", {}),
                    analyzed_at=datetime.fromisoformat(snap_data["analyzed_at"]) if snap_data.get("analyzed_at") else datetime.utcnow(),
                    result_path=Path(snap_data["result_path"]) if snap_data.get("result_path") else None,
                    notes=snap_data.get("notes"),
                )
            
            logger.info(f"Loaded analysis for {self.path.name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load analysis for {self.path.name}: {e}")
            return False

    def get_analysis_payload_or_load(self) -> Optional[Dict[str, Any]]:
        """
        Get analysis payload, automatically loading from disk if not in memory.
        
        Returns the analysis payload if available (in-memory or loaded from disk),
        or None if no analysis exists.
        """
        # First check if we have it in memory
        if self._analysis_payload is not None:
            return self._analysis_payload
        
        # Try loading from disk
        if self.load_analysis():
            return self._analysis_payload
        
        return None

    # ------------------------------------------------------------------
    # Convenience information
    # ------------------------------------------------------------------
    @property
    def num_lines(self) -> Optional[int]:
        header = self.ensure_header_loaded()
        return header.num_lines

    @property
    def pixels_per_line(self) -> Optional[int]:
        header = self.ensure_header_loaded()
        return header.pixels_per_line

    @property
    def duration_seconds(self) -> Optional[float]:
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
    """
    Yield metadata dictionaries for every TIFF underneath `root`.

    Only Olympus/bio metadata is loaded – TIFF pixels remain untouched.
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
    """
    Read metadata for all TIFF files under `root` and return a list.

    Wrapper around :func:`iter_metadata` for GUI-friendly consumption.
    """
    return list(iter_metadata(root, **kwargs))
