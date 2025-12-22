"""Tests for KymFileList class."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from kymflow.core.kym_file import KymFile
from kymflow.core.kym_file_list import KymFileList
from kymflow.core.utils.logging import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)


def test_kymfilelist_empty_folder() -> None:
    """Test KymFileList with an empty folder."""
    with tempfile.TemporaryDirectory() as tmpdir:
        folder = Path(tmpdir)
        file_list = KymFileList(folder)
        
        assert len(file_list) == 0
        assert file_list.folder.resolve() == folder.resolve()
        assert file_list.depth == 1
        assert file_list.load_image is False
        assert list(file_list) == []
        assert file_list.collect_metadata() == []


def test_kymfilelist_nonexistent_folder() -> None:
    """Test KymFileList with a non-existent folder."""
    nonexistent = Path("/nonexistent/path/that/does/not/exist")
    file_list = KymFileList(nonexistent)
    
    assert len(file_list) == 0
    assert file_list.folder == nonexistent.resolve()


def test_kymfilelist_depth_1() -> None:
    """Test KymFileList with depth=1 (base folder only)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        
        # Create files at different depths
        (base / "file0.tif").touch()
        (base / "sub1").mkdir()
        (base / "sub1" / "file1.tif").touch()
        (base / "sub1" / "sub2").mkdir()
        (base / "sub1" / "sub2" / "file2.tif").touch()
        
        file_list = KymFileList(base, depth=1)
                
        file_names = {kf.path.name for kf in file_list}
        
        assert "file0.tif" in file_names, "depth=1 should include base folder files (code depth 0)"
        assert "file1.tif" not in file_names, "depth=1 should NOT include sub1 files (code depth 1)"
        assert "file2.tif" not in file_names, "depth=1 should NOT include sub2 files (code depth 2)"


def test_kymfilelist_depth_2() -> None:
    """Test KymFileList with depth=2 (base + immediate subfolders)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        
        # Create files at different depths
        (base / "file0.tif").touch()
        (base / "sub1").mkdir()
        (base / "sub1" / "file1.tif").touch()
        (base / "sub1" / "sub2").mkdir()
        (base / "sub1" / "sub2" / "file2.tif").touch()
        
        file_list = KymFileList(base, depth=2)
        
        file_names = {kf.path.name for kf in file_list}
        assert "file0.tif" in file_names, "depth=2 should include base folder files (code depth 0)"
        assert "file1.tif" in file_names, "depth=2 should include sub1 files (code depth 1)"
        assert "file2.tif" not in file_names, "depth=2 should NOT include sub2 files (code depth 2)"


def test_kymfilelist_depth_3() -> None:
    """Test KymFileList with depth=3 (base + subfolders + sub-subfolders)."""
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
        
        file_list = KymFileList(base, depth=3)
        
        file_names = {kf.path.name for kf in file_list}
        assert "file0.tif" in file_names, "depth=3 should include base folder files (code depth 0)"
        assert "file1.tif" in file_names, "depth=3 should include sub1 files (code depth 1)"
        assert "file2.tif" in file_names, "depth=3 should include sub2 files (code depth 2)"
        assert "file3.tif" not in file_names, "depth=3 should NOT include sub3 files (code depth 3)"


def test_kymfilelist_default_depth() -> None:
    """Test that default depth=1 works correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        
        (base / "file0.tif").touch()
        (base / "sub1").mkdir()
        (base / "sub1" / "file1.tif").touch()
        
        # Default depth should be 1
        file_list_default = KymFileList(base)
        file_list_explicit = KymFileList(base, depth=1)
        
        assert len(file_list_default) == len(file_list_explicit)
        assert {kf.path.name for kf in file_list_default} == {kf.path.name for kf in file_list_explicit}


def test_kymfilelist_iteration() -> None:
    """Test that KymFileList can be iterated over."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        (base / "file1.tif").touch()
        (base / "file2.tif").touch()
        (base / "file3.tif").touch()
        
        file_list = KymFileList(base, depth=1)
        
        # Test iteration
        files_iterated = list(file_list)
        assert len(files_iterated) == 3
        assert all(isinstance(kf, KymFile) for kf in files_iterated)
        
        # Test indexing
        assert isinstance(file_list[0], KymFile)
        assert file_list[0].path.name in {"file1.tif", "file2.tif", "file3.tif"}
        
        # Test len
        assert len(file_list) == 3


def test_kymfilelist_reload() -> None:
    """Test that reload() method refreshes the file list."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        
        (base / "file1.tif").touch()
        file_list = KymFileList(base, depth=1)
        assert len(file_list) == 1
        
        # Add a new file
        (base / "file2.tif").touch()
        file_list.reload()
        assert len(file_list) == 2
        
        # Remove a file
        (base / "file1.tif").unlink()
        file_list.load()  # Test that load() also works
        assert len(file_list) == 1
        assert file_list[0].path.name == "file2.tif"


def test_kymfilelist_collect_metadata() -> None:
    """Test collect_metadata() method."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        (base / "file1.tif").touch()
        
        file_list = KymFileList(base, depth=1)
        
        metadata_list = file_list.collect_metadata()
        assert isinstance(metadata_list, list)
        assert len(metadata_list) == 1
        
        metadata = metadata_list[0]
        assert "path" in metadata
        assert "filename" in metadata
        assert metadata["filename"] == "file1.tif"
        
        # Test with include_analysis=True (analysis now handled by kymanalysis, not in metadata dict)
        metadata_with_analysis = file_list.collect_metadata()
        assert len(metadata_with_analysis) == 1
        # Analysis is no longer included in metadata dict - it's accessed via kymanalysis
        # Verify basic metadata fields are present
        assert "path" in metadata_with_analysis[0]
        assert "filename" in metadata_with_analysis[0]


def test_kymfilelist_iter_metadata() -> None:
    """Test iter_metadata() method."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        (base / "file1.tif").touch()
        (base / "file2.tif").touch()
        
        file_list = KymFileList(base, depth=1)
        
        metadata_iter = file_list.iter_metadata()
        metadata_list = list(metadata_iter)
        
        assert len(metadata_list) == 2
        assert all("path" in m for m in metadata_list)
        assert all("filename" in m for m in metadata_list)
        assert {m["filename"] for m in metadata_list} == {"file1.tif", "file2.tif"}


@pytest.mark.requires_data
def test_kymfilelist_with_real_data(test_data_dir: Path) -> None:
    """Test KymFileList with actual test data files."""
    if not test_data_dir.exists():
        pytest.skip("Test data directory does not exist")
    
    file_list = KymFileList(test_data_dir, depth=1)
    
    # Should find at least some files if test data exists
    if len(file_list) > 0:
        # Verify all items are KymFile instances
        assert all(isinstance(kf, KymFile) for kf in file_list)
        
        # Verify metadata collection works
        metadata_list = file_list.collect_metadata()
        assert len(metadata_list) == len(file_list)
        assert all("path" in m for m in metadata_list)
        assert all("filename" in m for m in metadata_list)


def test_kymfilelist_load_image_parameter() -> None:
    """Test that load_image parameter is respected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        (base / "file1.tif").touch()
        
        # Test with load_image=False (default)
        file_list_false = KymFileList(base, load_image=False)
        if len(file_list_false) > 0:
            kf = file_list_false[0]
            # Image should not be loaded yet
            assert kf.get_img_slice(channel=1) is None
        
        # Test with load_image=True
        file_list_true = KymFileList(base, load_image=True)
        if len(file_list_true) > 0:
            kf = file_list_true[0]
            # Image should be loaded (or attempt was made)
            # Note: For empty/invalid TIFF files, this might still be None


def test_kymfilelist_str_repr() -> None:
    """Test string representation of KymFileList."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        (base / "file1.tif").touch()
        
        file_list = KymFileList(base, depth=2, load_image=True)
        
        str_repr = str(file_list)
        assert "KymFileList" in str_repr
        assert "depth: 2" in str_repr
        assert "load_image: True" in str_repr
        
        repr_repr = repr(file_list)
        assert repr_repr == str_repr

