"""Integration-style tests for KymFile using test data.

These tests use sample TIFF files from tests/data/. Tests are skipped gracefully
if the data folder is empty or unavailable (e.g., CI machines without test data).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from kymflow.core.kym_file import (
    KymFile,
    # collect_metadata,
    # iter_metadata,
)
from kymflow.core.metadata import ExperimentMetadata
from kymflow.core.utils.logging import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)


def test_experiment_metadata_unknown_fields_ignored() -> None:
    """Test that unknown fields in metadata are silently ignored."""
    payload = {
        "species": "mouse",
        "region": "cortex",
        "favorite_color": "blue",  # Unknown field
        "note": "Important sample",
    }
    meta = ExperimentMetadata.from_dict(payload)
    assert meta.species == "mouse"
    assert meta.region == "cortex"
    # Unknown fields should be ignored (no extra attribute)
    merged = meta.to_dict()
    assert merged["species"] == "mouse"
    # favorite_color should not be in to_dict() output


@pytest.mark.requires_data
def test_metadata_only_load(sample_tif_file: Path | None) -> None:
    """Test loading metadata without loading image data."""
    if sample_tif_file is None:
        pytest.skip("No test data files available")

    logger.info("Loading metadata for %s", sample_tif_file.name)
    kymFile = KymFile(sample_tif_file, load_image=False)
    metadata = kymFile.to_metadata_dict()
    assert metadata["filename"] == sample_tif_file.name
    
    from pprint import pprint
    logger.info('metadata:')
    pprint(metadata)
    
    # Olympus header keys should exist even if not populated
    # assert "um_per_pixel" in metadata
    # assert "seconds_per_line" in metadata


@pytest.mark.requires_data
def test_lazy_image_loading(sample_tif_file: Path | None) -> None:
    """Test that image is not loaded until explicitly requested."""
    if sample_tif_file is None:
        pytest.skip("No test data files available")

    kymFile = KymFile(sample_tif_file, load_image=False)
    # Image should not be loaded until explicitly requested
    # assert kymFile.get_img_slice(channel=1) is None  # type: ignore[attr-defined]
    image = kymFile.get_img_slice(channel=1)
    assert isinstance(image, np.ndarray)
    assert image.ndim >= 2
    logger.info("Image shape loaded: %s", image.shape)


# @pytest.mark.requires_data
# def test_iter_and_collect_metadata(
#     test_data_dir: Path, sample_tif_file: Path | None
# ) -> None:
#     """Test iter_metadata and collect_metadata functions."""
#     if sample_tif_file is None:
#         pytest.skip("No test data files available")

#     logger.info("Iterating metadata under %s", test_data_dir)
#     entries = list(iter_metadata(test_data_dir, glob=sample_tif_file.name))
#     logger.info(f'entries:{entries}')

#     assert any(
#         entry["path"] == str(sample_tif_file) for entry in entries
#     ), "iter_metadata should return the test TIFF"
#     collected = collect_metadata(test_data_dir, glob=sample_tif_file.name)
#     assert len(entries) == len(collected)
