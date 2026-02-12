from __future__ import annotations

import threading
from pathlib import Path

import numpy as np
import pytest
import tifffile

from kymflow.core.image_loaders.kym_image_list import KymImageList
from kymflow.core.image_loaders.acq_image_list import AcqImageList
from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.core.utils.progress import CancelledError, ProgressMessage


def _make_tif(path: Path) -> None:
    data = np.zeros((10, 10), dtype=np.uint16)
    tifffile.imwrite(path, data)


def test_collect_paths_from_csv_valid(tmp_path: Path) -> None:
    # Create folder structure: tmp_path/subdir/file.tif
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    file1 = subdir / "a.tif"
    file2 = subdir / "b.tif"
    _make_tif(file1)
    _make_tif(file2)

    # CSV is in tmp_path, rel_paths are relative to tmp_path
    csv_path = tmp_path / "files.csv"
    csv_path.write_text("rel_path\nsubdir/a.tif\nsubdir/b.tif\n")

    paths = AcqImageList.collect_paths_from_csv(csv_path)
    assert len(paths) == 2
    assert paths[0].name == "a.tif"
    assert paths[1].name == "b.tif"


def test_collect_paths_from_csv_missing_column(tmp_path: Path) -> None:
    csv_path = tmp_path / "files.csv"
    csv_path.write_text("name\nfoo\n")

    with pytest.raises(ValueError, match="CSV must have a 'rel_path' column"):
        AcqImageList.collect_paths_from_csv(csv_path)


def test_collect_paths_from_csv_nested_structure(tmp_path: Path) -> None:
    """Test collect_paths_from_csv() with nested folder structure matching real use case.
    
    Creates structure like:
    base/
      condition1/
        date1/
          file1.tif
        date2/
          file2.tif
      condition2/
        date3/
          file3.tif
      files.csv (at base level with rel_path column)
    
    Verifies that rel_path values correctly resolve to nested files.
    """
    # Create nested folder structure
    condition1 = tmp_path / "14d Saline"
    condition2 = tmp_path / "28d AngII"
    condition1.mkdir()
    condition2.mkdir()
    
    date1 = condition1 / "20251014"
    date2 = condition1 / "20251015"
    date3 = condition2 / "20250708"
    date1.mkdir()
    date2.mkdir()
    date3.mkdir()
    
    # Create TIF files in nested directories
    file1 = date1 / "20251014_A100_0001.tif"
    file2 = date2 / "20251015_A101_0002.tif"
    file3 = date3 / "20250708_A85_0003.tif"
    _make_tif(file1)
    _make_tif(file2)
    _make_tif(file3)
    
    # Create CSV at base level with rel_path column
    csv_path = tmp_path / "randomized-declan-data-20260208-n-5.csv"
    csv_content = """rel_path
14d Saline/20251014/20251014_A100_0001.tif
14d Saline/20251015/20251015_A101_0002.tif
28d AngII/20250708/20250708_A85_0003.tif
"""
    csv_path.write_text(csv_content)
    
    # Test collect_paths_from_csv
    paths = AcqImageList.collect_paths_from_csv(csv_path)
    
    # Verify all paths were found
    assert len(paths) == 3
    
    # Verify paths are correct
    assert paths[0] == file1.resolve()
    assert paths[1] == file2.resolve()
    assert paths[2] == file3.resolve()
    
    # Verify file names
    assert paths[0].name == "20251014_A100_0001.tif"
    assert paths[1].name == "20251015_A101_0002.tif"
    assert paths[2].name == "20250708_A85_0003.tif"


def test_collect_paths_from_csv_invalid_rel_path(tmp_path: Path) -> None:
    """Test collect_paths_from_csv() raises ValueError when rel_path doesn't exist."""
    # Create CSV with invalid rel_path
    csv_path = tmp_path / "files.csv"
    csv_content = """rel_path
nonexistent/file.tif
"""
    csv_path.write_text(csv_content)
    
    # Should raise ValueError because file doesn't exist
    with pytest.raises(ValueError, match="invalid rel_path values that don't exist"):
        AcqImageList.collect_paths_from_csv(csv_path)


def test_load_from_path_emits_progress_for_csv(tmp_path: Path) -> None:
    file1 = tmp_path / "a.tif"
    file2 = tmp_path / "b.tif"
    _make_tif(file1)
    _make_tif(file2)

    csv_path = tmp_path / "files.csv"
    csv_path.write_text("rel_path\na.tif\nb.tif\n")

    phases: list[str] = []

    def progress_cb(msg: ProgressMessage) -> None:
        phases.append(msg.phase)

    files = KymImageList.load_from_path(
        csv_path,
        progress_cb=progress_cb,
    )

    assert len(files) == 2
    assert "read_csv" in phases
    assert "wrap" in phases


def test_load_from_path_cancel_during_wrap(tmp_path: Path) -> None:
    file1 = tmp_path / "a.tif"
    file2 = tmp_path / "b.tif"
    _make_tif(file1)
    _make_tif(file2)

    cancel_event = threading.Event()

    def progress_cb(msg: ProgressMessage) -> None:
        if msg.phase == "wrap" and msg.done == 0:
            cancel_event.set()

    with pytest.raises(CancelledError):
        KymImageList.load_from_path(
            tmp_path,
            depth=1,
            cancel_event=cancel_event,
            progress_cb=progress_cb,
        )


def test_collect_paths_from_folder_depth(tmp_path: Path) -> None:
    (tmp_path / "root.tif").write_bytes(b"")
    sub1 = tmp_path / "sub1"
    sub1.mkdir()
    (sub1 / "sub1.tif").write_bytes(b"")
    sub2 = sub1 / "sub2"
    sub2.mkdir()
    (sub2 / "sub2.tif").write_bytes(b"")

    paths_depth1 = AcqImageList.collect_paths_from_folder(
        tmp_path,
        depth=1,
        file_extension=".tif",
        ignore_file_stub=None,
        follow_symlinks=False,
    )
    paths_depth2 = AcqImageList.collect_paths_from_folder(
        tmp_path,
        depth=2,
        file_extension=".tif",
        ignore_file_stub=None,
        follow_symlinks=False,
    )

    assert len(paths_depth1) == 1
    assert len(paths_depth2) == 2


def test_collect_paths_from_folder_cancelled(tmp_path: Path) -> None:
    file1 = tmp_path / "a.tif"
    _make_tif(file1)

    cancel_event = threading.Event()
    cancel_event.set()

    with pytest.raises(CancelledError):
        AcqImageList.collect_paths_from_folder(
            tmp_path,
            depth=1,
            file_extension=".tif",
            ignore_file_stub=None,
            follow_symlinks=False,
            cancel_event=cancel_event,
        )
