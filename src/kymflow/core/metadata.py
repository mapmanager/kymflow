from __future__ import annotations

from dataclasses import dataclass, field, fields, asdict, MISSING
from pathlib import Path
from typing import Any, Dict, Optional, List, Type
from datetime import datetime

import pandas as pd

from .read_olympus_header import _readOlympusHeader

from .utils.logging import get_logger

logger = get_logger(__name__)

@dataclass
class FieldMetadata:
    """Structured metadata for form field definitions.

    Provides type-safe field metadata to avoid typos in metadata dictionaries.
    Used by GUI forms to configure field visibility, editability, and layout.

    Attributes:
        editable: Whether the field can be edited by the user.
        label: Display label for the field.
        widget_type: Type of widget to use (e.g., "text", "number").
        grid_span: Number of grid columns this field spans.
        visible: Whether the field should be visible in forms.
        description: Human-readable description of the field for documentation.
    """

    editable: bool = True
    label: str = ""
    widget_type: str = "text"
    grid_span: int = 1
    visible: bool = True
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for use in field(metadata=...).

        Returns:
            Dictionary containing all field metadata attributes
        """
        result = {
            "editable": self.editable,
            "label": self.label,
            "widget_type": self.widget_type,
            "grid_span": self.grid_span,
            "visible": self.visible,
            "description": self.description,
        }
        return result


def field_metadata(
    editable: bool = True,
    label: str = "",
    widget_type: str = "text",
    grid_span: int = 1,
    visible: bool = True,
    description: str = "",
) -> Dict[str, Any]:
    """Create field metadata dictionary.

    Convenience function that creates a FieldMetadata instance and converts
    it to a dictionary suitable for use in dataclass field metadata.

    Args:
        editable: Whether the field can be edited by the user.
        label: Display label for the field.
        widget_type: Type of widget to use (e.g., "text", "number").
        grid_span: Number of grid columns this field spans.
        visible: Whether the field should be visible in forms.
        description: Human-readable description of the field for documentation.

    Returns:
        Dictionary containing field metadata attributes.
    """
    return FieldMetadata(
        editable=editable,
        label=label,
        widget_type=widget_type,
        grid_span=grid_span,
        visible=visible,
        description=description,
    ).to_dict()


def _generateDocs(dc: Type, print_markdown: bool = True) -> pd.DataFrame:
    """Generate documentation DataFrame from a dataclass.

    Extracts field information from a dataclass including name, display name,
    default value, and description. Optionally prints a markdown table to console.

    Args:
        dc: The dataclass type to document.
        print_markdown: If True, print markdown table to console. Defaults to True.

    Returns:
        pandas DataFrame with columns: name, display_name, default_value, description.
    """
    rows = []
    for field_obj in fields(dc):
        # Get metadata
        meta = field_obj.metadata
        
        # Extract field information
        name = field_obj.name
        display_name = meta.get("label", "") or name
        description = meta.get("description", "")
        
        # Handle default value
        if field_obj.default is not MISSING:
            # Regular default value
            default_value = field_obj.default
        elif field_obj.default_factory is not MISSING:
            # default_factory case
            factory_name = getattr(field_obj.default_factory, '__name__', 'callable')
            default_value = f"<factory: {factory_name}>"
        else:
            # No default (required field)
            default_value = "<required>"
        
        # Convert default to string representation
        if default_value is None:
            default_str = "None"
        elif isinstance(default_value, str):
            default_str = f'"{default_value}"'
        else:
            default_str = str(default_value)
        
        rows.append({
            "name": name,
            "display_name": display_name,
            "default_value": default_str,
            "description": description,
        })
    
    df = pd.DataFrame(rows)
    
    if print_markdown:
        try:
            # Try using pandas to_markdown (requires tabulate)
            print(f"\n## {dc.__name__}\n")
            print(df.to_markdown(index=False))
            print()
        except ImportError:
            # Fallback if tabulate is not available
            print(f"\n## {dc.__name__}\n")
            print(df.to_string(index=False))
            print("\nNote: Install 'tabulate' for markdown table format")
            print()
    
    return df


@dataclass
class OlympusHeader:
    """Structured representation of Olympus microscope header metadata.

    Contains acquisition parameters extracted from the Olympus .txt header file
    that accompanies kymograph TIFF files. All fields have default values to
    handle cases where the header file is missing.

    Attributes:
        um_per_pixel: Spatial resolution in micrometers per pixel.
        seconds_per_line: Temporal resolution in seconds per line scan.
        duration_seconds: Total recording duration in seconds.
        pixels_per_line: Number of pixels in the spatial dimension.
        num_lines: Number of line scans in the temporal dimension.
        bits_per_pixel: Bit depth of the image data.
        date_str: Acquisition date string from header.
        time_str: Acquisition time string from header.
        raw: Raw dictionary of all parsed header values.
    """

    # OlympusHeader needs defaults in case corresponding Olympus txt file is not found
    um_per_pixel: Optional[float] = field(
        default=1.0,
        metadata=field_metadata(
            editable=False,
            label="um/pixel",
            widget_type="text",
            grid_span=1,
        ),
    )
    seconds_per_line: Optional[float] = field(
        default=0.001,  # 1 ms
        metadata=field_metadata(
            editable=False,
            label="seconds/line",
            widget_type="text",
            grid_span=1,
        ),
    )
    duration_seconds: Optional[float] = field(
        default=None,
        metadata=field_metadata(
            editable=False,
            label="Duration (s)",
            widget_type="text",
            grid_span=1,
        ),
    )
    pixels_per_line: Optional[int] = field(
        default=None,
        metadata=field_metadata(
            editable=False,
            label="Pixels/Line",
            widget_type="text",
            grid_span=1,
        ),
    )
    num_lines: Optional[int] = field(
        default=None,
        metadata=field_metadata(
            editable=False,
            label="Lines",
            widget_type="text",
            grid_span=1,
        ),
    )
    bits_per_pixel: Optional[int] = field(
        default=None,
        metadata=field_metadata(
            editable=False,
            label="Bits/Pixel",
            widget_type="text",
            grid_span=1,
        ),
    )
    date_str: Optional[str] = field(
        default=None,
        metadata=field_metadata(
            editable=False,
            label="Date",
            widget_type="text",
            grid_span=1,
        ),
    )
    time_str: Optional[str] = field(
        default=None,
        metadata=field_metadata(
            editable=False,
            label="Time",
            widget_type="text",
            grid_span=1,
        ),
    )
    raw: Dict[str, Any] = field(
        default_factory=dict,
        metadata=field_metadata(
            editable=False,
            label="Raw",
            widget_type="text",
            grid_span=2,  # Full width for raw dict
            visible=False,  # Hide raw dict from form display
        ),
    )

    @classmethod
    def from_tif(cls, tif_path: Path) -> "OlympusHeader":
        """Load Olympus header from accompanying .txt file.

        Attempts to parse the Olympus header file that should be in the same
        directory as the TIFF file with the same base name. Returns a header
        with default values if the file is not found or cannot be parsed.

        Args:
            tif_path: Path to the TIFF file. The corresponding .txt file will
                be looked up in the same directory.

        Returns:
            OlympusHeader instance with parsed values, or default values if
            the header file is missing.
        """
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
        """Convert to dictionary with renamed keys.

        Returns:
            Dictionary representation with date_str and time_str renamed to
            date and time for compatibility with external APIs.
        """
        d = asdict(self)
        # Rename keys
        d["date"] = d.pop("date_str", None)
        d["time"] = d.pop("time_str", None)
        return d

    @classmethod
    def form_schema(cls) -> List[Dict[str, Any]]:
        """Return field schema for form generation.

        Generates a list of field definitions with metadata extracted from
        the dataclass field definitions. Used by GUI frameworks to dynamically
        generate forms without hardcoding field information.

        Returns:
            List of dictionaries, each containing field name, label, editability,
            widget type, grid span, visibility, and field type information.
            Fields are ordered by their declaration order in the dataclass.
        """
        schema = []
        for field_obj in fields(cls):
            meta = field_obj.metadata
            schema.append(
                {
                    "name": field_obj.name,
                    "label": meta.get(
                        "label", field_obj.name.replace("_", " ").title()
                    ),
                    "editable": meta.get("editable", True),
                    "widget_type": meta.get("widget_type", "text"),
                    "grid_span": meta.get("grid_span", 1),
                    "visible": meta.get("visible", True),
                    "field_type": str(field_obj.type),
                }
            )

        # Order is determined by the order of the fields in the dataclass
        return schema

    def get_editable_values(self) -> Dict[str, str]:
        """Get current values for editable fields only.

        Returns:
            Dictionary mapping field names to string representations of their
            current values. Only includes fields marked as editable in the
            form schema. None values are converted to empty strings.
        """
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
    """User-provided experimental metadata for kymograph files.

    Contains structured fields for documenting experimental conditions,
    sample information, and notes. All fields are optional and have default
    values. Unknown keys in dictionaries are silently ignored when loading
    from dict to maintain strict schema validation.

    Attributes:
        species: Animal species (e.g., "mouse", "rat").
        region: Brain region or anatomical location.
        cell_type: Type of cell or vessel being imaged.
        depth: Imaging depth in micrometers.
        branch_order: Branch order for vascular structures.
        direction: Flow direction or vessel orientation.
        sex: Animal sex.
        genotype: Genetic background or modification.
        condition: Experimental condition or treatment.
        acquisition_date: Date of acquisition (read-only, from header).
        acquisition_time: Time of acquisition (read-only, from header).
        note: Free-form notes or comments.
    """

    species: Optional[str] = field(
        default="",
        metadata=field_metadata(
            editable=True,
            label="Species",
            widget_type="text",
            grid_span=1,
        ),
    )
    region: Optional[str] = field(
        default="",
        metadata=field_metadata(
            editable=True,
            label="Region",
            widget_type="text",
            grid_span=1,
        ),
    )
    cell_type: Optional[str] = field(
        default="",
        metadata=field_metadata(
            editable=True,
            label="Cell type",
            widget_type="text",
            grid_span=1,
        ),
    )
    depth: Optional[float] = field(
        default=None,
        metadata=field_metadata(
            editable=True,
            label="Depth",
            widget_type="number",
            grid_span=1,
        ),
    )
    branch_order: Optional[int] = field(
        default=None,
        metadata=field_metadata(
            editable=True,
            label="Branch Order",
            widget_type="number",
            grid_span=1,
        ),
    )
    direction: Optional[str] = field(
        default="",
        metadata=field_metadata(
            editable=True,
            label="Direction",
            widget_type="text",
            grid_span=1,
        ),
    )
    sex: Optional[str] = field(
        default="",
        metadata=field_metadata(
            editable=True,
            label="Sex",
            widget_type="text",
            grid_span=1,
        ),
    )
    genotype: Optional[str] = field(
        default="",
        metadata=field_metadata(
            editable=True,
            label="Genotype",
            widget_type="text",
            grid_span=1,
        ),
    )
    condition: Optional[str] = field(
        default="",
        metadata=field_metadata(
            editable=True,
            label="Condition",
            widget_type="text",
            grid_span=1,
        ),
    )
    acquisition_date: Optional[str] = field(
        default="",
        metadata=field_metadata(
            editable=False,
            label="Acquisition Date",
            widget_type="text",
            grid_span=1,
        ),
    )
    acquisition_time: Optional[str] = field(
        default="",
        metadata=field_metadata(
            editable=False,
            label="Acquisition Time",
            widget_type="text",
            grid_span=1,
        ),
    )
    note: Optional[str] = field(
        default="",
        metadata=field_metadata(
            editable=True,
            label="Note",
            widget_type="text",
            grid_span=2,
        ),
    )

    @classmethod
    def from_dict(cls, payload: Optional[Dict[str, Any]]) -> "ExperimentMetadata":
        """Create instance from dictionary, ignoring unknown keys.

        Only fields defined in the dataclass are extracted from the payload.
        Unknown keys are silently ignored to maintain strict schema validation.

        Args:
            payload: Dictionary containing metadata fields. Can be None or empty.

        Returns:
            ExperimentMetadata instance with values from payload, or defaults
            if payload is None or empty.
        """
        payload = payload or {}
        valid = {f.name for f in fields(cls) if f.init}
        known = {k: payload[k] for k in payload.keys() & valid}
        # Unknown keys are silently ignored (strict schema-only strategy)
        return cls(**known)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with standardized key names.

        Returns:
            Dictionary with all field values, using abbreviated keys (acq_date,
            acq_time) for compatibility with external APIs. All fields are
            included automatically, including depth and branch_order.
        """
        d = asdict(self)
        # Rename keys for compatibility with external APIs
        d["acq_date"] = d.pop("acquisition_date", None)
        d["acq_time"] = d.pop("acquisition_time", None)
        return d

    @classmethod
    def form_schema(cls) -> List[Dict[str, Any]]:
        """Return field schema for form generation.

        Generates a list of field definitions with metadata extracted from
        the dataclass field definitions. Used by GUI frameworks to dynamically
        generate forms without hardcoding field information.

        Returns:
            List of dictionaries, each containing field name, label, editability,
            widget type, grid span, visibility, and field type information.
        """
        schema = []
        for field_obj in fields(cls):
            meta = field_obj.metadata
            schema.append(
                {
                    "name": field_obj.name,
                    "label": meta.get(
                        "label", field_obj.name.replace("_", " ").title()
                    ),
                    "editable": meta.get("editable", True),
                    "widget_type": meta.get("widget_type", "text"),
                    "grid_span": meta.get("grid_span", 1),
                    "visible": meta.get("visible", True),
                    "field_type": str(field_obj.type),
                }
            )

        # order is determined by the order of the fields in the dataclass
        return schema

    def get_editable_values(self) -> Dict[str, str]:
        """Get current values for editable fields only.

        Returns:
            Dictionary mapping field names to string representations of their
            current values. Only includes fields marked as editable in the
            form schema. None values are converted to empty strings.
        """
        schema = self.form_schema()
        values = {}
        for field_def in schema:
            if field_def["editable"]:
                field_name = field_def["name"]
                values[field_name] = getattr(self, field_name) or ""
        return values


@dataclass
class AnalysisParameters:
    """Metadata describing analysis parameters and results.

    Stores information about the analysis algorithm used, its parameters,
    when it was run, and where results are saved. This metadata is saved
    alongside analysis results for reproducibility.

    Attributes:
        algorithm: Name of the analysis algorithm (e.g., "mpRadon").
        window_size: Number of time lines per analysis window.
        start_pixel: Start index in space dimension (inclusive). None uses 0.
        stop_pixel: Stop index in space dimension (exclusive). None uses full width.
        start_line: Start index in time dimension (inclusive). None uses 0.
        stop_line: Stop index in time dimension (exclusive). None uses full height.
        use_multiprocessing: Whether multiprocessing was used for computation.
        analyzed_at: Timestamp when analysis was performed.
        result_path: Path to the saved analysis results file (CSV).
    """

    algorithm: str = field(
        default="",
        metadata=field_metadata(
            editable=False,
            label="Algorithm",
            widget_type="text",
            grid_span=1,
        ),
    )
    window_size: Optional[int] = field(
        default=None,
        metadata=field_metadata(
            editable=False,
            label="Window Size",
            widget_type="number",
            grid_span=1,
        ),
    )
    start_pixel: Optional[int] = field(
        default=None,
        metadata=field_metadata(
            editable=False,
            label="Start Pixel",
            widget_type="number",
            grid_span=1,
        ),
    )
    stop_pixel: Optional[int] = field(
        default=None,
        metadata=field_metadata(
            editable=False,
            label="Stop Pixel",
            widget_type="number",
            grid_span=1,
        ),
    )
    start_line: Optional[int] = field(
        default=None,
        metadata=field_metadata(
            editable=False,
            label="Start Line",
            widget_type="number",
            grid_span=1,
        ),
    )
    stop_line: Optional[int] = field(
        default=None,
        metadata=field_metadata(
            editable=False,
            label="Stop Line",
            widget_type="number",
            grid_span=1,
        ),
    )
    use_multiprocessing: bool = field(
        default=True,
        metadata=field_metadata(
            editable=False,
            label="Use Multiprocessing",
            widget_type="text",
            grid_span=1,
        ),
    )
    analyzed_at: Optional[datetime] = field(
        default=None,
        metadata=field_metadata(
            editable=False,
            label="Analyzed At",
            widget_type="text",
            grid_span=1,
        ),
    )
    result_path: Optional[Path] = field(
        default=None,
        metadata=field_metadata(
            editable=False,
            label="Result Path",
            widget_type="text",
            grid_span=2,
        ),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary with all analysis parameters. Datetime is converted to
            ISO format string, and Path is converted to string. All fields are
            included automatically.
        """
        d = asdict(self)
        # Convert datetime to ISO format string
        if d.get("analyzed_at") is not None:
            d["analyzed_at"] = d["analyzed_at"].isoformat()
        # Convert Path to string
        if d.get("result_path") is not None:
            d["result_path"] = str(d["result_path"])
        return d

    @classmethod
    def form_schema(cls) -> List[Dict[str, Any]]:
        """Return field schema for form generation.

        Generates a list of field definitions with metadata extracted from
        the dataclass field definitions. Used by GUI frameworks to dynamically
        generate forms without hardcoding field information.

        Returns:
            List of dictionaries, each containing field name, label, editability,
            widget type, grid span, visibility, and field type information.
        """
        schema = []
        for field_obj in fields(cls):
            meta = field_obj.metadata
            schema.append(
                {
                    "name": field_obj.name,
                    "label": meta.get(
                        "label", field_obj.name.replace("_", " ").title()
                    ),
                    "editable": meta.get("editable", True),
                    "widget_type": meta.get("widget_type", "text"),
                    "grid_span": meta.get("grid_span", 1),
                    "visible": meta.get("visible", True),
                    "field_type": str(field_obj.type),
                }
            )

        # Order is determined by the order of the fields in the dataclass
        return schema
