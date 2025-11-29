"""Tests for repository/folder scanning functionality."""

from __future__ import annotations

from pathlib import Path

import pytest

from kymflow_core.repository import FolderScanResult, scan_folder, metadata_table


@pytest.mark.skipif(
    not (Path(__file__).parent / "data").exists(),
    reason="Test data directory not found",
)
def test_scan_folder(test_data_dir: Path) -> None:
    """Test scanning a folder for TIFF files."""
    if not test_data_dir.exists():
        pytest.skip("Test data directory does not exist")
    
    result = scan_folder(test_data_dir, load_images=False)
    assert isinstance(result, FolderScanResult)
    assert result.folder == test_data_dir
    assert isinstance(result.files, list)
    # Should find at least some TIFF files if they exist
    if result.files:
        assert all(f.path.suffix == ".tif" for f in result.files)


@pytest.mark.skipif(
    not (Path(__file__).parent / "data").exists(),
    reason="Test data directory not found",
)
def test_metadata_table(test_data_dir: Path) -> None:
    """Test getting metadata table for folder."""
    if not test_data_dir.exists():
        pytest.skip("Test data directory does not exist")
    
    metadata = metadata_table(test_data_dir)
    assert isinstance(metadata, list)
    # Each entry should be a dict with expected keys
    if metadata:
        entry = metadata[0]
        assert "path" in entry
        assert "filename" in entry

