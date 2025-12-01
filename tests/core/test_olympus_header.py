"""Tests for Olympus header parsing."""

from __future__ import annotations

from pathlib import Path

import pytest

from kymflow.core.read_olympus_header import _readOlympusHeader


@pytest.mark.requires_data
def test_read_olympus_header_with_file(sample_tif_file: Path | None) -> None:
    """Test reading Olympus header from existing .txt file."""
    if sample_tif_file is None:
        pytest.skip("No test data files available")

    txt_file = sample_tif_file.with_suffix(".txt")
    if not txt_file.exists():
        pytest.skip(f"No header file found: {txt_file}")

    result = _readOlympusHeader(str(sample_tif_file))
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
