from __future__ import annotations

import threading
from pathlib import Path

import numpy as np
import pytest
import tifffile

from kymflow.core.image_loaders.acq_image_list import AcqImageList
from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.core.utils.progress import CancelledError, ProgressMessage


def _make_tif(path: Path) -> None:
    data = np.zeros((10, 10), dtype=np.uint16)
    tifffile.imwrite(path, data)


def test_collect_paths_from_csv_valid(tmp_path: Path) -> None:
    file1 = tmp_path / "a.tif"
    file2 = tmp_path / "b.tif"
    _make_tif(file1)
    _make_tif(file2)

    csv_path = tmp_path / "files.csv"
    csv_path.write_text(f"path\n{file1}\n{file2}\n")

    paths = AcqImageList.collect_paths_from_csv(csv_path)
    assert len(paths) == 2
    assert paths[0].name == "a.tif"
    assert paths[1].name == "b.tif"


def test_collect_paths_from_csv_missing_column(tmp_path: Path) -> None:
    csv_path = tmp_path / "files.csv"
    csv_path.write_text("name\nfoo\n")

    with pytest.raises(ValueError, match="CSV must have a 'path' column"):
        AcqImageList.collect_paths_from_csv(csv_path)


def test_load_from_path_emits_progress_for_csv(tmp_path: Path) -> None:
    file1 = tmp_path / "a.tif"
    file2 = tmp_path / "b.tif"
    _make_tif(file1)
    _make_tif(file2)

    csv_path = tmp_path / "files.csv"
    csv_path.write_text(f"path\n{file1}\n{file2}\n")

    phases: list[str] = []

    def progress_cb(msg: ProgressMessage) -> None:
        phases.append(msg.phase)

    files = AcqImageList.load_from_path(
        csv_path,
        image_cls=KymImage,
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
        AcqImageList.load_from_path(
            tmp_path,
            image_cls=KymImage,
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
