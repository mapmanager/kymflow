"""Tests for repository/folder scanning functionality."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from kymflow.core.repository import FolderScanResult, scan_folder, metadata_table


@pytest.mark.requires_data
def test_scan_folder(test_data_dir: Path) -> None:
    """Test scanning a folder for TIFF files."""
    result = scan_folder(test_data_dir, load_images=False)
    assert isinstance(result, FolderScanResult)
    # Use resolve() to handle symlink differences (e.g., /var -> /private/var on macOS)
    assert result.folder.resolve() == test_data_dir.resolve()
    assert isinstance(result.files, list)
    # Should find at least some TIFF files if they exist
    if result.files:
        assert all(f.path.suffix == ".tif" for f in result.files)


@pytest.mark.requires_data
def test_metadata_table(test_data_dir: Path) -> None:
    """Test getting metadata table for folder."""
    metadata = metadata_table(test_data_dir)
    assert isinstance(metadata, list)
    # Each entry should be a dict with expected keys
    if metadata:
        entry = metadata[0]
        assert "path" in entry
        assert "filename" in entry


def test_scan_folder_with_depth() -> None:
    """Test scan_folder() with different depth values."""
    # Create a temporary directory structure:
    # base/
    #   file0.tif (depth 0)
    #   sub1/
    #     file1.tif (depth 1)
    #     sub2/
    #       file2.tif (depth 2)
    #       sub3/
    #         file3.tif (depth 3)
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        
        # Create files at different depths
        (base / "file0.tif").touch()
        (base / "sub1").mkdir()
        (base / "sub1" / "file1.tif").touch()
        (base / "sub1" / "sub2").mkdir()
        (base / "sub1" / "sub2" / "file2.tif").touch()
        (base / "sub1" / "sub2" / "sub3").mkdir()
        (base / "sub1" / "sub2" / "sub3" / "file3.tif").touch()
        
        # Test depth=1: should include only base (code depth 0)
        result = scan_folder(base, depth=1)
        file_names = {f.path.name for f in result.files}
        assert "file0.tif" in file_names, "depth=1 should include base folder files (code depth 0)"
        assert "file1.tif" not in file_names, "depth=1 should NOT include sub1 files (code depth 1)"
        assert "file2.tif" not in file_names, "depth=1 should NOT include sub2 files (code depth 2)"
        assert "file3.tif" not in file_names, "depth=1 should NOT include sub3 files (code depth 3)"
        
        # Test depth=2: should include base (code depth 0) and sub1 (code depth 1)
        result = scan_folder(base, depth=2)
        file_names = {f.path.name for f in result.files}
        assert "file0.tif" in file_names, "depth=2 should include base folder files (code depth 0)"
        assert "file1.tif" in file_names, "depth=2 should include sub1 files (code depth 1)"
        assert "file2.tif" not in file_names, "depth=2 should NOT include sub2 files (code depth 2)"
        assert "file3.tif" not in file_names, "depth=2 should NOT include sub3 files (code depth 3)"
        
        # Test depth=3: should include base (code depth 0), sub1 (code depth 1), and sub2 (code depth 2)
        result = scan_folder(base, depth=3)
        file_names = {f.path.name for f in result.files}
        assert "file0.tif" in file_names, "depth=3 should include base folder files (code depth 0)"
        assert "file1.tif" in file_names, "depth=3 should include sub1 files (code depth 1)"
        assert "file2.tif" in file_names, "depth=3 should include sub2 files (code depth 2)"
        assert "file3.tif" not in file_names, "depth=3 should NOT include sub3 files (code depth 3)"
        
        # Test default depth=1 (should match explicit depth=1)
        result_default = scan_folder(base)
        result_explicit = scan_folder(base, depth=1)
        assert len(result_default.files) == len(result_explicit.files)
        assert {f.path.name for f in result_default.files} == {f.path.name for f in result_explicit.files}
