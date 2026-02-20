# Filename: src/kymflow_zarr/__init__.py
"""kymflow_zarr package.

A small, opinionated Zarr v2 dataset wrapper for:
- N-dimensional image arrays (uint8/uint16 typical)
- Per-image analysis artifacts (JSON + tabular data as Parquet/CSV)
- Dataset-level manifest/index
- Validation and schema versioning

Intended as a starting point you can adapt into kymflow.
"""

from kymflow.core.utils.logging import get_logger

from .dataset import ZarrDataset
from .record import MetadataNotFoundError, ZarrImageRecord
from .schema import DatasetSchema, SchemaValidationError

logger = get_logger(__name__)

__all__ = [
    "ZarrDataset",
    "ZarrImageRecord",
    "MetadataNotFoundError",
    "DatasetSchema",
    "SchemaValidationError",
]
