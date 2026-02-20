# Filename: src/kymflow_zarr/schema.py
"""Dataset schema and validation.

This module provides:
- A small schema object (version, required attributes, conventions)
- Validation helpers to ensure a Zarr store matches expected layout

The goal is to catch issues early, and allow safe evolution by bumping schema_version.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

from dataclasses import dataclass
from typing import Any, Optional

import zarr


class SchemaValidationError(ValueError):
    """Raised when a dataset fails schema validation."""


@dataclass(frozen=True)
class DatasetSchema:
    """Schema definition for the dataset layout.

    Attributes:
        format_name: A string identifying the dataset format.
        schema_version: Integer schema version.
        require_images_group: If True, require root/images group to exist.
        require_index_group: If True, require root/index group to exist.
    """

    format_name: str = "kymflow_zarr_v1"
    schema_version: int = 1
    require_images_group: bool = False
    require_index_group: bool = False

    def validate_root(self, root: zarr.hierarchy.Group) -> None:
        """Validate a Zarr root group against this schema.

        Args:
            root: The Zarr root group.

        Raises:
            SchemaValidationError: If validation fails.
        """
        attrs = dict(root.attrs)

        fmt = attrs.get("format")
        if fmt is None:
            raise SchemaValidationError("Root attrs missing required key: 'format'")
        if fmt != self.format_name:
            raise SchemaValidationError(f"Unexpected dataset format: {fmt!r} (expected {self.format_name!r})")

        ver = attrs.get("schema_version")
        if ver is None:
            raise SchemaValidationError("Root attrs missing required key: 'schema_version'")
        if int(ver) != int(self.schema_version):
            raise SchemaValidationError(f"Unexpected schema_version: {ver!r} (expected {self.schema_version!r})")


        if self.require_images_group and "images" not in root:
            raise SchemaValidationError("Missing required group: /images")
        if self.require_index_group and "index" not in root:
            raise SchemaValidationError("Missing required group: /index")

    def validate_image_record(self, root: zarr.hierarchy.Group, image_id: str) -> None:
        """Validate that an image record exists and has required pieces.

        Args:
            root: Zarr root group.
            image_id: Image record id.

        Raises:
            SchemaValidationError: If the record is missing or invalid.
        """
        path = f"images/{image_id}"
        if path not in root:
            raise SchemaValidationError(f"Missing image group: /{path}")

        grp = root[path]
        if "data" not in grp:
            raise SchemaValidationError(f"Missing array: /{path}/data")

        arr = grp["data"]
        if arr.ndim < 2:
            raise SchemaValidationError(f"Image array must be >=2D, got shape={arr.shape}")
        if str(arr.dtype) not in ("uint8", "uint16", "int16", "float32", "float64"):
            # Not a hard rule; just a guardrail.
            raise SchemaValidationError(f"Unexpected dtype {arr.dtype} for /{path}/data")

        axes = grp.attrs.get("axes")
        if axes is not None:
            if not isinstance(axes, (list, tuple)):
                raise SchemaValidationError(f"Expected axes in attrs to be list/tuple, got {type(axes)}")
            if len(axes) != arr.ndim:
                raise SchemaValidationError(f"axes length {len(axes)} does not match ndim {arr.ndim} for /{path}/data")
