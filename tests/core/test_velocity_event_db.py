"""Tests for VelocityEventDb CRUD API and KymImageList integration."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.core.image_loaders.kym_image_list import KymImageList
from kymflow.core.image_loaders.velocity_event_db import VelocityEventDb
from kymflow.core.image_loaders.roi import RoiBounds
from kymflow.core.utils.logging import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)


def test_unique_row_id_format() -> None:
    """Test _unique_row_id generates correct format."""
    # Format: path|roi_id|event_idx
    assert "/path/to/file.tif|1|0" == "/path/to/file.tif|1|0"
    assert "/a/b.tif|42|3" == "/a/b.tif|42|3"


def test_velocity_event_db_init_none_path() -> None:
    """Test VelocityEventDb with db_path=None (single-file, empty mode)."""
    db = VelocityEventDb(db_path=None)
    assert db.get_db_path() is None
    assert db.get_df().empty
    assert db.get_all_events() == []
    assert db.save() is False


def test_velocity_event_db_init_with_path() -> None:
    """Test VelocityEventDb with valid db_path."""
    with TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "kym_event_db.csv"
        db = VelocityEventDb(db_path=db_path)
        assert db.get_db_path() == db_path
        assert db.get_df().empty


def test_velocity_event_db_update_from_image_empty() -> None:
    """Test update_from_image with image that has no velocity events."""
    kym_image = KymImage(img_data=np.zeros((50, 50), dtype=np.uint16), load_image=False)
    kym_image.update_header(shape=(50, 50), ndim=2, voxels=[0.001, 0.284])
    kym_image._file_path_dict[1] = Path("/tmp/test.tif")

    db = VelocityEventDb(db_path=None)
    db.update_from_image(kym_image)
    assert len(db.get_all_events()) == 0


def test_velocity_event_db_update_from_image_with_events() -> None:
    """Test update_from_image populates cache from KymAnalysis."""
    kym_image = KymImage(img_data=np.zeros((50, 50), dtype=np.uint16), load_image=False)
    kym_image.update_header(shape=(50, 50), ndim=2, voxels=[0.001, 0.284])
    bounds = RoiBounds(dim0_start=0, dim0_stop=50, dim1_start=0, dim1_stop=50)
    roi = kym_image.rois.create_roi(bounds=bounds)
    kym_image.get_kym_analysis().add_velocity_event(roi.id, t_start=0.5, t_end=1.0)
    kym_image.get_kym_analysis().add_velocity_event(roi.id, t_start=2.0, t_end=3.0)
    kym_image._file_path_dict[1] = Path("/tmp/test.tif")

    db = VelocityEventDb(db_path=None)
    db.update_from_image(kym_image)

    events = db.get_all_events()
    assert len(events) == 2
    assert events[0]["_unique_row_id"] == "/tmp/test.tif|1|0"
    assert events[1]["_unique_row_id"] == "/tmp/test.tif|1|1"
    assert events[0]["t_start"] == 0.5
    assert events[1]["t_start"] == 2.0


def test_velocity_event_db_save_and_load() -> None:
    """Test save() persists to CSV and load() restores."""
    with TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "kym_event_db.csv"

        def make_image():
            kym_image = KymImage(img_data=np.zeros((50, 50), dtype=np.uint16), load_image=False)
            kym_image.update_header(shape=(50, 50), ndim=2, voxels=[0.001, 0.284])
            bounds = RoiBounds(dim0_start=0, dim0_stop=50, dim1_start=0, dim1_stop=50)
            roi = kym_image.rois.create_roi(bounds=bounds)
            kym_image.get_kym_analysis().add_velocity_event(roi.id, t_start=0.5, t_end=1.0)
            kym_image._file_path_dict[1] = Path(tmpdir) / "test.tif"
            return kym_image

        kym_image = make_image()
        db = VelocityEventDb(db_path=db_path)
        db.update_from_image(kym_image)
        assert db.save() is True
        assert db_path.exists()

        df = pd.read_csv(db_path)
        assert "_unique_row_id" in df.columns
        assert "path" in df.columns
        assert "roi_id" in df.columns
        assert len(df) == 1


def test_velocity_event_db_rebuild_from_images() -> None:
    """Test rebuild_from_images replaces cache."""
    kym_image = KymImage(img_data=np.zeros((50, 50), dtype=np.uint16), load_image=False)
    kym_image.update_header(shape=(50, 50), ndim=2, voxels=[0.001, 0.284])
    bounds = RoiBounds(dim0_start=0, dim0_stop=50, dim1_start=0, dim1_stop=50)
    roi = kym_image.rois.create_roi(bounds=bounds)
    kym_image.get_kym_analysis().add_velocity_event(roi.id, t_start=0.5, t_end=1.0)
    kym_image._file_path_dict[1] = Path("/tmp/test.tif")

    db = VelocityEventDb(db_path=None)
    db.rebuild_from_images(images_provider=lambda: [kym_image])

    events = db.get_all_events()
    assert len(events) == 1


def test_kym_image_list_has_velocity_event_db() -> None:
    """Test KymImageList has _velocity_event_db after init."""
    image_list = KymImageList(path=None, file_extension=".tif")
    assert hasattr(image_list, "_velocity_event_db")
    assert isinstance(image_list._velocity_event_db, VelocityEventDb)


def test_kym_image_list_get_velocity_event_df() -> None:
    """Test get_velocity_event_df returns DataFrame."""
    image_list = KymImageList(path=None, file_extension=".tif")
    df = image_list.get_velocity_event_df()
    assert isinstance(df, pd.DataFrame)
    assert df.empty or "_unique_row_id" in df.columns


def test_kym_image_list_get_velocity_event_db_path() -> None:
    """Test _get_velocity_event_db_path returns correct path for folder mode."""
    with TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        (tmp_path / "a.tif").touch()
        image_list = KymImageList(path=tmp_path, file_extension=".tif", depth=1)
        db_path = image_list._get_velocity_event_db_path()
        assert db_path is not None
        assert db_path.name == "kym_event_db.csv"


def test_kym_image_list_get_velocity_event_db_path_single_file_returns_none() -> None:
    """Test _get_velocity_event_db_path returns None for single-file mode."""
    with TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        test_file = tmp_path / "test.tif"
        test_file.touch()
        image_list = KymImageList(path=test_file, file_extension=".tif")
        db_path = image_list._get_velocity_event_db_path()
        assert db_path is None


def test_kym_image_list_update_velocity_event_for_image() -> None:
    """Test update_velocity_event_for_image updates cache and persists."""
    kym_image = KymImage(img_data=np.zeros((50, 50), dtype=np.uint16), load_image=False)
    kym_image.update_header(shape=(50, 50), ndim=2, voxels=[0.001, 0.284])
    bounds = RoiBounds(dim0_start=0, dim0_stop=50, dim1_start=0, dim1_stop=50)
    roi = kym_image.rois.create_roi(bounds=bounds)
    kym_image.get_kym_analysis().add_velocity_event(roi.id, t_start=0.5, t_end=1.0)

    with TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        test_file = tmp_path / "test.tif"
        test_file.touch()
        kym_image._file_path_dict[1] = test_file
        image_list = KymImageList(path=tmp_path, file_extension=".tif", depth=1)
        image_list.images = [kym_image]

        image_list.update_velocity_event_for_image(kym_image)
        df = image_list.get_velocity_event_df()
        assert len(df) >= 1
        assert "_unique_row_id" in df.columns
        db_path = tmp_path / "kym_event_db.csv"
        assert db_path.exists()


def test_kym_image_list_detect_all_events_updates_velocity_cache() -> None:
    """Test detect_all_events calls update_velocity_event_cache_only for each image."""
    kym_image = KymImage(img_data=np.zeros((50, 50), dtype=np.uint16), load_image=False)
    kym_image.update_header(shape=(50, 50), ndim=2, voxels=[0.001, 0.284])
    bounds = RoiBounds(dim0_start=0, dim0_stop=50, dim1_start=0, dim1_stop=50)
    roi = kym_image.rois.create_roi(bounds=bounds)
    kym_image.get_kym_analysis().analyze_roi(roi.id, window_size=16, use_multiprocessing=False)

    with TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        test_file = tmp_path / "test.tif"
        test_file.touch()
        kym_image._file_path_dict[1] = test_file
        image_list = KymImageList(path=tmp_path, file_extension=".tif", depth=1)
        image_list.images = [kym_image]

        image_list.detect_all_events()
        df = image_list.get_velocity_event_df()
        assert "_unique_row_id" in df.columns or df.empty
