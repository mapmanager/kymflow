from __future__ import annotations

from dataclasses import dataclass, field, fields, asdict, MISSING
from typing import Any, Dict, Optional, List, Type, Tuple

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
        except (ImportError) as e:
            # Fallback if tabulate is not available
            # print(f"\n## {dc.__name__}\n")
            print(df.to_string(index=False))
            print("\nNote: Install 'tabulate' for markdown table format")
            print(f"  -->> e:{e}")
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
                val = getattr(self, field_name)
                # Convert to string: None -> "", otherwise str(val)
                values[field_name] = "" if val is None else str(val)
        return values

@dataclass
class AcqImgHeader:
    """Header metadata for acquired images.
    
    Contains all header-related fields that can be set from metadata without
    loading the full image data. This enables lazy loading of image data while
    still providing access to essential metadata.
    
    Attributes:
        shape: Image shape tuple (e.g., (1000, 500) for 2D, (100, 1000, 500) for 3D).
        ndim: Number of dimensions (2 or 3).
        voxels: Physical unit of each voxel (e.g., [0.001, 0.284] for time and space).
        voxels_units: Units for each voxel (e.g., ['s', 'um']).
        labels: Labels for each dimension (e.g., ['time (s)', 'space (um)']).
        physical_size: Physical size along each dimension (shape[i] * voxels[i]).
    """
    
    # Note: Many fields are list/tuple types; the metadata here is mainly to
    # support future UI/schema usage (e.g., forms, column configs).
    shape: Tuple[int, ...] | None = field(
        default=None,
        metadata=field_metadata(
            editable=False,
            label="Shape",
            widget_type="text",
            grid_span=1,
        ),
    )
    ndim: int | None = field(
        default=None,
        metadata=field_metadata(
            editable=False,
            label="Dimensions",
            widget_type="number",
            grid_span=1,
        ),
    )
    voxels: list[float] | None = field(
        default=None,
        metadata=field_metadata(
            editable=False,
            label="Voxel Size",
            widget_type="text",
            grid_span=1,
        ),
    )
    voxels_units: list[str] | None = field(
        default=None,
        metadata=field_metadata(
            editable=False,
            label="Voxel Units",
            widget_type="text",
            grid_span=1,
        ),
    )
    labels: list[str] | None = field(
        default=None,
        metadata=field_metadata(
            editable=False,
            label="Axis Labels",
            widget_type="text",
            grid_span=1,
        ),
    )
    physical_size: list[float] | None = field(
        default=None,
        metadata=field_metadata(
            editable=False,
            label="Physical Size",
            widget_type="text",
            grid_span=1,
        ),
    )
    
    def __post_init__(self) -> None:
        """Validate consistency after initialization.
        
        Checks that all fields are consistent with ndim if ndim is set.
        This is optional validation - fields can be set incrementally and
        validated explicitly when needed.
        """
        if self.ndim is not None:
            self._validate_consistency()
    
    def _validate_consistency(self) -> None:
        """Validate that all fields are consistent with ndim.
        
        Raises:
            ValueError: If any field length doesn't match ndim.
        """
        if self.ndim is None:
            return
        
        if self.ndim not in (2, 3):
            raise ValueError(f"ndim must be 2 or 3, got {self.ndim}")
        
        # Validate shape
        if self.shape is not None and len(self.shape) != self.ndim:
            raise ValueError(f"shape length {len(self.shape)} doesn't match ndim {self.ndim}")
        
        # Validate voxels
        if self.voxels is not None and len(self.voxels) != self.ndim:
            raise ValueError(f"voxels length {len(self.voxels)} doesn't match ndim {self.ndim}")
        
        # Validate voxels_units
        if self.voxels_units is not None and len(self.voxels_units) != self.ndim:
            raise ValueError(f"voxels_units length {len(self.voxels_units)} doesn't match ndim {self.ndim}")
        
        # Validate labels
        if self.labels is not None and len(self.labels) != self.ndim:
            raise ValueError(f"labels length {len(self.labels)} doesn't match ndim {self.ndim}")
    
    def validate_ndim(self, ndim: int) -> bool:
        """Validate that ndim is consistent with existing header fields.
        
        Args:
            ndim: Number of dimensions to validate.
            
        Returns:
            True if ndim is valid and consistent with existing fields.
        """
        if ndim not in (2, 3):
            return False
        
        # Check consistency with shape
        if self.shape is not None and len(self.shape) != ndim:
            return False
        
        # Check consistency with voxels
        if self.voxels is not None and len(self.voxels) != ndim:
            return False
        
        # Check consistency with voxels_units
        if self.voxels_units is not None and len(self.voxels_units) != ndim:
            return False
        
        # Check consistency with labels
        if self.labels is not None and len(self.labels) != ndim:
            return False
        
        return True
    
    def validate_shape(self, shape: Tuple[int, ...]) -> bool:
        """Validate that shape is consistent with existing header fields.
        
        Args:
            shape: Shape tuple to validate.
            
        Returns:
            True if shape is valid and consistent with existing fields.
        """
        if not shape or len(shape) not in (2, 3):
            return False
        
        ndim = len(shape)
        
        # Check consistency with ndim
        if self.ndim is not None and self.ndim != ndim:
            return False
        
        # Check consistency with voxels
        if self.voxels is not None and len(self.voxels) != ndim:
            return False
        
        # Check consistency with voxels_units
        if self.voxels_units is not None and len(self.voxels_units) != ndim:
            return False
        
        # Check consistency with labels
        if self.labels is not None and len(self.labels) != ndim:
            return False
        
        return True
    
    def compute_physical_size(self) -> list[float] | None:
        """Compute physical size from shape and voxels.
        
        Returns:
            List of physical sizes (shape[i] * voxels[i]) for each dimension,
            or None if shape or voxels are not set.
        """
        if self.shape is None or self.voxels is None:
            return None
        
        if len(self.shape) != len(self.voxels):
            return None
        
        return [s * v for s, v in zip(self.shape, self.voxels)]
    
    # ------------------------------------------------------------------
    # New helper methods for AcqImage
    # ------------------------------------------------------------------
    def set_shape_ndim(self, shape: Tuple[int, ...] | None, ndim: int | None) -> None:
        """Set shape and ndim with consistency validation."""
        if shape is not None:
            self.shape = shape
            if ndim is None:
                ndim = len(shape)
        self.ndim = ndim
        # Validate current state
        self._validate_consistency()

    def init_defaults_from_shape(self) -> None:
        """Initialize default voxels/units/labels based on ndim if not set."""
        if self.ndim is None:
            return
        # Only initialize if currently None
        if self.voxels is None:
            self.voxels = [1.0] * self.ndim
        if self.voxels_units is None:
            self.voxels_units = ["px"] * self.ndim
        if self.labels is None:
            self.labels = [""] * self.ndim
        # Compute physical size
        self.physical_size = self.compute_physical_size()
        # Validate
        self._validate_consistency()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize header to a dictionary for metadata save."""
        return {
            "shape": list(self.shape) if self.shape is not None else None,
            "ndim": self.ndim,
            "voxels": self.voxels,
            "voxels_units": self.voxels_units,
            "labels": self.labels,
            "physical_size": self.physical_size,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AcqImgHeader":
        """Deserialize header from a dictionary."""
        header = cls()
        if not data:
            return header
        if "shape" in data:
            header.shape = tuple(data["shape"]) if data["shape"] is not None else None
        if "ndim" in data:
            header.ndim = data["ndim"]
        if "voxels" in data:
            header.voxels = data["voxels"]
        if "voxels_units" in data:
            header.voxels_units = data["voxels_units"]
        if "labels" in data:
            header.labels = data["labels"]
        if "physical_size" in data:
            header.physical_size = data["physical_size"]
        # If physical_size missing but shape+voxels present, compute
        if header.physical_size is None:
            header.physical_size = header.compute_physical_size()
        # Validate consistency
        header._validate_consistency()
        return header

    # ------------------------------------------------------------------
    # Optional schema helper for UI (similar to ExperimentMetadata)
    # ------------------------------------------------------------------
    @classmethod
    def form_schema(cls) -> List[Dict[str, Any]]:
        """Return field schema for form generation.

        Mirrors the pattern used in ExperimentMetadata.form_schema(). This can
        be used by GUI code to dynamically build an AcqImageHeader form.
        """
        from dataclasses import fields

        schema: List[Dict[str, Any]] = []
        for field_obj in fields(cls):
            meta = field_obj.metadata
            schema.append(
                {
                    "name": field_obj.name,
                    "label": meta.get(
                        "label", field_obj.name.replace("_", " ").title()
                    ),
                    "editable": meta.get("editable", False),
                    "widget_type": meta.get("widget_type", "text"),
                    "grid_span": meta.get("grid_span", 1),
                    "visible": meta.get("visible", True),
                    "field_type": str(field_obj.type),
                }
            )
        return schema

    @classmethod
    def from_data(cls, shape: Tuple[int, ...], ndim: int) -> AcqImgHeader:
        """Create header from image data shape and ndim.
        
        Initializes default values for voxels, voxels_units, and labels.
        
        Args:
            shape: Image shape tuple.
            ndim: Number of dimensions.
            
        Returns:
            AcqImgHeader instance with shape and ndim set, and default values
            for other fields.
        """
        header = cls()
        header.shape = shape
        header.ndim = ndim
        header.voxels = [1.0] * ndim
        header.voxels_units = ["px"] * ndim
        header.labels = [""] * ndim
        header.physical_size = header.compute_physical_size()
        return header

