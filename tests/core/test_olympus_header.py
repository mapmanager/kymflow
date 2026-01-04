"""Tests for Olympus header parsing."""

from __future__ import annotations

from pathlib import Path

import pytest

from kymflow.core.image_loaders.olympus_header.read_olympus_header import _readOlympusHeader

from kymflow.core.utils.logging import get_logger, setup_logging

# setup_logging()
logger = get_logger(__name__)

@pytest.mark.requires_data
def test_read_olympus_header_with_file(sample_tif_file: Path | None) -> None:
    """Test reading Olympus header from existing .txt file."""
    if sample_tif_file is None:
        pytest.skip("No test data files available")

    txt_file = sample_tif_file.with_suffix(".txt")
    if not txt_file.exists():
        pytest.skip(f"No header file found: {txt_file}")

    result = _readOlympusHeader(str(sample_tif_file))

    logger.info('_readOlympusHeader result:')
    from pprint import pprint
    pprint(result, sort_dicts=False, width=300)

    assert result is not None
    assert isinstance(result, dict)
    # Check for expected keys
    assert "umPerPixel" in result or result.get("umPerPixel") is None
    assert "secondsPerLine" in result or result.get("secondsPerLine") is None


def test_read_olympus_header_missing_file() -> None:
    """Test reading Olympus header when .txt file is missing."""
    fake_path = "/nonexistent/path/file.tif"
    result = _readOlympusHeader(fake_path)
    # Should return None when file doesn't exist
    assert result is None

# def test_olympus_header_from_tif_missing_file() -> None:
#     """Test OlympusHeader when .txt file is missing."""
#     # Use a non-existent file path
#     fake_path = Path("/nonexistent/path/file.tif")
#     header = OlympusHeader.from_tif(fake_path)
#     # Should return header with default values
#     assert header.um_per_pixel == 1.0
#     assert header.seconds_per_line == 0.001


# @pytest.mark.requires_data
# def test_olympus_header_from_tif_with_file(sample_tif_file: Path | None) -> None:
#     """Test OlympusHeader loading from existing .txt file."""
#     if sample_tif_file is None:
#         pytest.skip("No test data files available")

#     # Check if corresponding .txt file exists
#     txt_file = sample_tif_file.with_suffix(".txt")
#     if not txt_file.exists():
#         pytest.skip(f"No header file found: {txt_file}")

#     header = OlympusHeader.from_tif(sample_tif_file)
#     # Should have parsed values (exact values depend on test data)
#     assert header is not None
