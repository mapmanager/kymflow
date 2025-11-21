"""
High level API to interact with kymograph files.

Goals for this module:
    * Provide a single entry point (`KymFile`) that encapsulates raw image
      data, microscope metadata (Olympus txt), experimental metadata, and analysis
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
from dataclasses import dataclass, field, fields, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Iterator, List, Optional

import numpy as np
import pandas as pd
import tifffile
import scipy.signal

from .read_olympus_header import _readOlympusHeader
from .kym_flow_radon_gpt import mp_analyze_flow

from .utils.logging import get_logger
logger = get_logger(__name__)

ProgressCallback = Callable[[int, int], Any]
CancelCallback = Callable[[], bool]


@dataclass
class FieldMetadata:
    """Structured metadata for form field definitions.
    
    Provides type-safe field metadata to avoid typos in metadata dictionaries.
    """
    editable: bool = True
    label: str = ""
    widget_type: str = "text"
    grid_span: int = 1
    order: Optional[int] = None
    visible: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for use in field(metadata=...)."""
        result = {
            "editable": self.editable,
            "label": self.label,
            "widget_type": self.widget_type,
            "grid_span": self.grid_span,
            "visible": self.visible,
        }
        if self.order is not None:
            result["order"] = self.order
        return result


def field_metadata(
    editable: bool = True,
    label: str = "",
    widget_type: str = "text",
    grid_span: int = 1,
    order: Optional[int] = None,
    visible: bool = True,
) -> Dict[str, Any]:
    """Helper function to create field metadata dict.
    
    Convenience function that creates a FieldMetadata instance and converts to dict.
    """
    return FieldMetadata(
        editable=editable,
        label=label,
        widget_type=widget_type,
        grid_span=grid_span,
        order=order,
        visible=visible,
    ).to_dict()


def _removeOutliers(y: np.ndarray) -> np.ndarray:
    """Nan out values +/- 2*std.
    """
    
    # trying to fix plotly refresh bug
    #_y = y.copy()
    _y = y

    _mean = np.nanmean(_y)
    _std = np.nanstd(_y)
    
    _greater = _y > (_mean + 2*_std)
    _y[_greater] = np.nan #float('nan')
    
    _less = _y < (_mean - 2*_std)
    _y[_less] = np.nan #float('nan')

    # _greaterLess = (_y > (_mean + 2*_std)) | (_y < (_mean - 2*_std))
    # _y[_greaterLess] = np.nan #float('nan')

    return _y

def _medianFilter(y: np.ndarray, window_size: int = 5) -> np.ndarray:
    """Apply a median filter to the array.
    """
    return scipy.signal.medfilt(y, window_size)

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

@dataclass
class OlympusHeader:
    """Structured representation of Olympus txt header values.
    """

    # OlympusHeader needs defaults in case corresponding Olympus txt file is not found
    um_per_pixel: Optional[float] = field(
        default=1.0,
        metadata=field_metadata(
            editable=False,
            label="um/pixel",
            widget_type="text",
            grid_span=1,
        )
    )
    seconds_per_line: Optional[float] = field(
        default=0.001,  # 1 ms
        metadata=field_metadata(
            editable=False,
            label="seconds/line",
            widget_type="text",
            grid_span=1,
        )
    )
    duration_seconds: Optional[float] = field(
        default=None,
        metadata=field_metadata(
            editable=False,
            label="Duration (s)",
            widget_type="text",
            grid_span=1,
        )
    )
    pixels_per_line: Optional[int] = field(
        default=None,
        metadata=field_metadata(
            editable=False,
            label="Pixels/Line",
            widget_type="text",
            grid_span=1,
        )
    )
    num_lines: Optional[int] = field(
        default=None,
        metadata=field_metadata(
            editable=False,
            label="Lines",
            widget_type="text",
            grid_span=1,
        )
    )
    bits_per_pixel: Optional[int] = field(
        default=None,
        metadata=field_metadata(
            editable=False,
            label="Bits/Pixel",
            widget_type="text",
            grid_span=1,
        )
    )
    date_str: Optional[str] = field(
        default=None,
        metadata=field_metadata(
            editable=False,
            label="Date",
            widget_type="text",
            grid_span=1,
        )
    )
    time_str: Optional[str] = field(
        default=None,
        metadata=field_metadata(
            editable=False,
            label="Time",
            widget_type="text",
            grid_span=1,
        )
    )
    raw: Dict[str, Any] = field(
        default_factory=dict,
        metadata=field_metadata(
            editable=False,
            label="Raw",
            widget_type="text",
            grid_span=2,  # Full width for raw dict
            visible=False,  # Hide raw dict from form display
        )
    )

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
        d = asdict(self)
        # Rename keys
        d["date"] = d.pop("date_str", None)
        d["time"] = d.pop("time_str", None)
        return d

    @classmethod
    def form_schema(cls) -> List[Dict[str, Any]]:
        """
        Return field schema for form generation.
        
        Returns list of field definitions with metadata.
        Backend-only, no UI framework knowledge.
        """
        schema = []
        for field_obj in fields(cls):
            meta = field_obj.metadata
            schema.append({
                "name": field_obj.name,
                "label": meta.get("label", field_obj.name.replace("_", " ").title()),
                "editable": meta.get("editable", True),
                "widget_type": meta.get("widget_type", "text"),
                "order": meta.get("order", 999),
                "grid_span": meta.get("grid_span", 1),
                "visible": meta.get("visible", True),
                "field_type": str(field_obj.type),
            })
        
        # Order is determined by the order of the fields in the dataclass
        return schema

    def get_editable_values(self) -> Dict[str, str]:
        """Return current values for editable fields only."""
        schema = self.form_schema()
        values = {}
        for field_def in schema:
            if field_def["editable"]:
                field_name = field_def["name"]
                value = getattr(self, field_name)
                # Convert to string, handling None and dict types
                if value is None:
                    values[field_name] = ""
                elif isinstance(value, dict):
                    values[field_name] = str(value)
                else:
                    values[field_name] = str(value)
        return values

@dataclass
class ExperimentMetadata:
    """
    User provided experimental metadata.

    Acts as a thin structured layer on top of a dict to ensure consumers get
    predictable keys while still allowing arbitrary extensions through
    `extra`.
    """

    species: Optional[str] = field(
        default='',
        metadata=field_metadata(
            editable=True,
            label="Species",
            widget_type="text",
            grid_span=1,
        )
    )
    cell_type: Optional[str] = field(
        default='',
        metadata=field_metadata(
            editable=True,
            label="Cell type",
            widget_type="text",
            grid_span=1,
        )
    )
    region: Optional[str] = field(
        default='',
        metadata=field_metadata(
            editable=True,
            label="Region",
            widget_type="text",
            grid_span=1,
        )
    )
    sex: Optional[str] = field(
        default='',
        metadata=field_metadata(
            editable=True,
            label="Sex",
            widget_type="text",
            grid_span=1,
        )
    )
    genotype: Optional[str] = field(
        default='',
        metadata=field_metadata(
            editable=True,
            label="Genotype",
            widget_type="text",
            grid_span=1,
        )
    )
    condition: Optional[str] = field(
        default='',
        metadata=field_metadata(
            editable=True,
            label="Condition",
            widget_type="text",
            grid_span=1,
        )
    )
    acquisition_date: Optional[str] = field(
        default='',
        metadata=field_metadata(
            editable=False,
            label="Acquisition Date",
            widget_type="text",
            grid_span=1,
        )
    )
    acquisition_time: Optional[str] = field(
        default='',
        metadata=field_metadata(
            editable=False,
            label="Acquisition Time",
            widget_type="text",
            grid_span=1,
        )
    )
    note: Optional[str] = field(
        default='',
        metadata=field_metadata(
            editable=True,
            label="Note",
            widget_type="text",
            grid_span=2,
        )
    )

    @classmethod
    def from_dict(cls, payload: Optional[Dict[str, Any]]) -> "ExperimentMetadata":
        """Create instance from dictionary, ignoring unknown keys."""
        payload = payload or {}
        valid = {f.name for f in fields(cls) if f.init}
        known = {k: payload[k] for k in payload.keys() & valid}
        # Unknown keys are silently ignored (strict schema-only strategy)
        return cls(**known)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "species": self.species,
            "cell_type": self.cell_type,
            "region": self.region,
            "sex": self.sex,
            "genotype": self.genotype,
            "condition": self.condition,
            "note": self.note,
            "acq_date": self.acquisition_date,
            "acq_time": self.acquisition_time,
        }

    @classmethod
    def form_schema(cls) -> List[Dict[str, Any]]:
        """
        Return field schema for form generation.
        
        Returns list of field definitions with metadata.
        Backend-only, no UI framework knowledge.
        """
        schema = []
        for field_obj in fields(cls):
            meta = field_obj.metadata
            schema.append({
                "name": field_obj.name,
                "label": meta.get("label", field_obj.name.replace("_", " ").title()),
                "editable": meta.get("editable", True),
                "widget_type": meta.get("widget_type", "text"),
                "order": meta.get("order", 999),
                "grid_span": meta.get("grid_span", 1),
                "visible": meta.get("visible", True),
                "field_type": str(field_obj.type),
            })
        
        # order is determined by the order of the fields in the dataclass
        # # Sort by order
        # schema.sort(key=lambda x: x["order"])
        return schema

    def get_editable_values(self) -> Dict[str, str]:
        """Return current values for editable fields only."""
        schema = self.form_schema()
        values = {}
        for field_def in schema:
            if field_def["editable"]:
                field_name = field_def["name"]
                values[field_name] = getattr(self, field_name) or ""
        return values


@dataclass
class AnalysisParameters:
    """Metadata describing the last performed analysis.
    """

    algorithm: str = field(
        default='',
        metadata=field_metadata(
            editable=False,
            label="Algorithm",
            widget_type="text",
            grid_span=1,
        )
    )
    parameters: Dict[str, Any] = field(
        default_factory=dict,
        metadata=field_metadata(
            editable=False,
            label="Parameters",
            widget_type="text",
            grid_span=2,
        )
    )
    analyzed_at: Optional[datetime] = field(
        default=None,
        metadata=field_metadata(
            editable=False,
            label="Analyzed At",
            widget_type="text",
            grid_span=1,
        )
    )
    result_path: Optional[Path] = field(
        default=None,
        metadata=field_metadata(
            editable=False,
            label="Result Path",
            widget_type="text",
            grid_span=2,
        )
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "algorithm": self.algorithm,
            "parameters": self.parameters,
            "analyzed_at": self.analyzed_at.isoformat() if self.analyzed_at else None,
            "result_path": str(self.result_path) if self.result_path else None,
        }

    @classmethod
    def form_schema(cls) -> List[Dict[str, Any]]:
        """
        Return field schema for form generation.
        
        Returns list of field definitions with metadata.
        Backend-only, no UI framework knowledge.
        """
        schema = []
        for field_obj in fields(cls):
            meta = field_obj.metadata
            schema.append({
                "name": field_obj.name,
                "label": meta.get("label", field_obj.name.replace("_", " ").title()),
                "editable": meta.get("editable", True),
                "widget_type": meta.get("widget_type", "text"),
                "order": meta.get("order", 999),
                "grid_span": meta.get("grid_span", 1),
                "visible": meta.get("visible", True),
                "field_type": str(field_obj.type),
            })
        
        # Order is determined by the order of the fields in the dataclass
        return schema


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
    experiment_metadata:
        Optional dictionary of user-supplied metadata that overrides the values
        inferred from Olympus header.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        load_image: bool = False,
    ) -> None:
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

    def summary_row(self) -> Dict[str, Any]:
        """Tabular summary suitable for file list views."""
        return {
            "File Name": self.path.name,
            'Analyzed': '✓' if self.analysisExists else '',
            'Saved': '✓' if not self._dirty else '',
            'Window Points': self._analysis_parameters.parameters.get('window_size', '-'),
            "pixels": self.pixels_per_line or "-",
            "lines": self.num_lines or "-",
            "duration (s)": self.duration_seconds or "-",
            "ms/line": round(self._header.seconds_per_line * 1000, 2) if self._header.seconds_per_line else "-",
            "um/pixel": self._header.um_per_pixel or "-",
            "bits/pixel": self._header.bits_per_pixel or "-",

            "note": self.experiment_metadata.note or "-",
            "path": str(self.path),  # special case, not in any shema
        }

    @classmethod
    def table_column_schema(cls) -> Dict[str, bool]:
        """
        Return column visibility schema for table display.
        
        Returns dict mapping summary_row column name to visible bool.
        Reuses existing form schemas where possible to avoid duplication.
        
        Backend-only, no UI framework knowledge.
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
        if self._image is None:
            self._image = tifffile.imread(self.path)
            # abb 20251121
            self._image = np.flip(self._image, axis=1)

        logger.info(f'image loaded: {self._image.shape} dtype:{self._image.dtype}')        
        
        return self._image

    # ------------------------------------------------------------------
    # Metadata exposure
    # ------------------------------------------------------------------
    # abb not used
    def to_metadata_dict(self, include_analysis: bool = True) -> Dict[str, Any]:
        """
        Merge Olympus header + experimental metadata + derived info.

        This is the primary structure consumed by GUI tables and CLI scripts.
        """
        header = self.ensure_header_loaded()  # header is always loaded in __init__ (can be default)
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
        """Update stored experimental metadata."""
        logger.info(f'fields:{fields}')
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
        progress_callback: Optional[ProgressCallback] = None,
        is_cancelled: Optional[CancelCallback] = None,
        use_multiprocessing: bool = True,
    ) -> None:
        """
        Run the Radon-based flow analysis and persist the metadata snapshot.

        Returns a dictionary payload (angles, timestamps, etc.) that can be
        serialized by callers. Persistence (e.g., CSV, parquet) is explicitly
        left to higher-level services to keep this class IO-light.
        """
        image = self.ensure_image_loaded()
        
        thetas, the_t, spread = mp_analyze_flow(
            image,
            window_size,
            start_pixel=start_pixel,
            stop_pixel=stop_pixel,
            progress_callback=progress_callback,
            is_cancelled=is_cancelled,
            use_multiprocessing=use_multiprocessing,
        )
        # Store lightweight metadata for UI access.
        self._analysis_parameters = AnalysisParameters(
            algorithm="mpRadon",
            parameters={
                "window_size": window_size,
                "start_pixel": start_pixel,
                "stop_pixel": stop_pixel,
                "use_multiprocessing": use_multiprocessing,
            },
            analyzed_at=datetime.now(timezone.utc),
        )

        secondsPerLine = self._header.seconds_per_line
        umPerPixel = self._header.um_per_pixel
        
        # convert to physical units
        drewTime = the_t * secondsPerLine
        
        # convert radians to angle
        _rad = np.deg2rad(thetas)
        drewVelocity = (umPerPixel/secondsPerLine) * np.tan(_rad)
        drewVelocity = drewVelocity / 1000  # mm/s

        # debug, count inf and 0 tan
        # numZeros = np.count_nonzero(drewVelocity==0)
        # logger.info(f'  1) numZeros:{numZeros}')

        # remove inf and 0 tan()
        # np.tan(90 deg) is returning 1e16 rather than inf
        logger.info('not removing inf/0 velocity -->> use this to calculate stalls')
        # tan90or0 = (drewVelocity > 1e6) | (drewVelocity == 0)
        # drewVelocity[tan90or0] = float('nan')
        
        # our original in kym_file_v0.py saved these columns:
        # time,velocity,parentFolder,file,algorithm,delx,delt,numLines,pntsPerLine,cleanVelocity,absVelocity
        
        cleanVelocity = _removeOutliers(drewVelocity)
        cleanVelocity = _medianFilter(cleanVelocity, window_size=5)

        self._dfAnalysis = pd.DataFrame({
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
        })
        
        # Mark as dirty so save_analysis() will save
        self._dirty = True
        
        # Auto-save analysis after successful computation
        # self.save_analysis()
        
    def save_analysis(self) -> bool:
        """
        Save analysis to CSV (data) and JSON (metadata) files.
        
        CSV contains: time, velocity, theta_degrees, time_indices
        JSON contains: OlympusHeader, ExperimentMetadata, AnalysisParameters
        
        Returns True if successful, False otherwise.
        """
        if not self._dirty:
            logger.info(f"Analysis does not need to be for  {self.path.name}")
            return False

        if not self.analysisExists:
            logger.warning(f"No analysis to save for {self.path.name}")
            return False
        
        csv_path, json_path = _getSavePaths(self.path)

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
        """
        Load metadata from JSON file.
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
            self._analysis_parameters = AnalysisParameters(
                algorithm=snap_data.get("algorithm"),
                parameters=snap_data.get("parameters"),
                analyzed_at=datetime.fromisoformat(snap_data["analyzed_at"]),
                result_path=Path(snap_data["result_path"]) if snap_data.get("result_path") else None,
            )

        return True

    def load_analysis(self) -> bool:
        """
        Load analysis from CSV (data) and JSON (metadata) files.
                
        Returns True if successful, False otherwise.
        """
        csv_path, _ = _getSavePaths(self.path)
        
        # Check if files exist
        if not csv_path.exists() :
            logger.info(f"No analysis files found for {self.path.name}")
            return False
        
        # Load CSV into DataFrame
        self._dfAnalysis = pd.read_csv(csv_path)
                        
        self.load_metadata()

        logger.info(f"Loaded analysis for {self.path.name}")
        return True
        
    @property
    def analysisExists(self) -> bool:
        """
        Check if analysis has been loaded.
        """
        return self._dfAnalysis is not None

    def getAnalysisValue(self, key: str) -> Any:
        """
        Get a value from the analysis DataFrame.
        """
        if self._dfAnalysis is None:
            logger.warning(f"No analysis loaded for {self.path.name}")
            return None
        if key not in self._dfAnalysis.columns:
            logger.warning(f"Key {key} not found in analysis DataFrame for {self.path.name}")
            logger.warning(f"  Columns: {self._dfAnalysis.columns}")
            return None
        return self._dfAnalysis[key].values

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
