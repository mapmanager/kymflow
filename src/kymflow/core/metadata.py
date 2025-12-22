from __future__ import annotations

from dataclasses import dataclass, field, fields, asdict, MISSING
from pathlib import Path
from typing import Any, Dict, Optional, List, Type
from datetime import datetime

import pandas as pd

from kymflow.core.utils.logging import get_logger

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
    """Metadata describing analysis parameters and results with ROI information.

    Unified structure combining ROI coordinates and analysis parameters. This allows
    a single data structure to represent both unanalyzed ROIs (analysis fields are None)
    and analyzed ROIs (all fields populated). When ROI coordinates change, analysis
    fields become invalid (set to None) and must be re-analyzed.

    Attributes:
        roi_id: Unique identifier for this ROI.
        left: Left coordinate of ROI in full-image pixels.
        top: Top coordinate of ROI in full-image pixels.
        right: Right coordinate of ROI in full-image pixels.
        bottom: Bottom coordinate of ROI in full-image pixels.
        note: Optional note/description for this ROI.
        algorithm: Name of the analysis algorithm (e.g., "mpRadon"). Empty string if not analyzed.
        window_size: Number of time lines per analysis window. None if not analyzed.
        analyzed_at: Timestamp when analysis was performed. None if not analyzed.
        
        Note: Pixel/line indices (start_pixel, stop_pixel, start_line, stop_line) are
        computed on-the-fly from left/top/right/bottom during analysis and are not stored.
    """

    # ROI fields (always present)
    roi_id: int = field(
        default=0,
        metadata=field_metadata(
            editable=False,
            label="ROI ID",
            widget_type="number",
            grid_span=1,
        ),
    )
    left: int = field(
        default=0,
        metadata=field_metadata(
            editable=True,
            label="Left",
            widget_type="number",
            grid_span=1,
        ),
    )
    top: int = field(
        default=0,
        metadata=field_metadata(
            editable=True,
            label="Top",
            widget_type="number",
            grid_span=1,
        ),
    )
    right: int = field(
        default=0,
        metadata=field_metadata(
            editable=True,
            label="Right",
            widget_type="number",
            grid_span=1,
        ),
    )
    bottom: int = field(
        default=0,
        metadata=field_metadata(
            editable=True,
            label="Bottom",
            widget_type="number",
            grid_span=1,
        ),
    )
    note: str = field(
        default="",
        metadata=field_metadata(
            editable=True,
            label="Note",
            widget_type="text",
            grid_span=2,
        ),
    )

    # Analysis fields (None if ROI not analyzed or analysis invalidated)
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
    analyzed_at: Optional[datetime] = field(
        default=None,
        metadata=field_metadata(
            editable=False,
            label="Analyzed At",
            widget_type="text",
            grid_span=1,
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
        return d

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "AnalysisParameters":
        """Create instance from dictionary, filtering unknown fields and logging warnings.
        
        Only fields defined in the dataclass are extracted from the payload.
        Unknown keys are filtered out and logged as warnings to help identify
        schema evolution issues (e.g., deprecated fields in old JSON files).
        
        Args:
            payload: Dictionary containing ROI and analysis fields. Can include
                unknown/deprecated fields that will be filtered out.
        
        Returns:
            AnalysisParameters instance with values from payload, using defaults
            for missing fields.
        """
        from kymflow.core.utils.logging import get_logger
        logger = get_logger(__name__)
        
        # Get valid field names from dataclass
        valid_field_names = {f.name for f in fields(cls)}
        
        # Separate known and unknown fields
        known_fields = {k: v for k, v in payload.items() if k in valid_field_names}
        unknown_fields = {k: v for k, v in payload.items() if k not in valid_field_names}
        
        # Log warning if unknown fields were found
        if unknown_fields:
            logger.warning(
                f"AnalysisParameters.from_dict(): Ignoring unknown/deprecated fields: {list(unknown_fields.keys())}. "
                f"This may indicate schema evolution - old data files may need migration."
            )
        
        # Convert float coordinates to int
        for coord in ['left', 'top', 'right', 'bottom']:
            if coord in known_fields and isinstance(known_fields[coord], float):
                known_fields[coord] = int(known_fields[coord])
        
        # Handle datetime conversion for analyzed_at
        if "analyzed_at" in known_fields and known_fields["analyzed_at"]:
            if isinstance(known_fields["analyzed_at"], str):
                known_fields["analyzed_at"] = datetime.fromisoformat(known_fields["analyzed_at"])
        
        return cls(**known_fields)

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

    def has_same_coordinates(self, other: "AnalysisParameters") -> bool:
        """Check if this ROI has the same coordinates as another ROI.
        
        Compares only the coordinate fields (left, top, right, bottom), ignoring
        other fields like roi_id, note, and analysis parameters.
        
        Args:
            other: Another AnalysisParameters instance to compare against.
        
        Returns:
            True if coordinates are the same, False otherwise.
        """
        if not isinstance(other, AnalysisParameters):
            return False
        return (
            self.left == other.left
            and self.top == other.top
            and self.right == other.right
            and self.bottom == other.bottom
        )
    
    def __str__(self) -> str:
        """String representation of all dataclass fields."""
        d = asdict(self)
        parts = [f'{k}={v!r}' for k, v in d.items()]
        return f'{self.__class__.__name__}(' + ', '.join(parts) + ')'
