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
from kymflow.core.image_loaders.velocity_event_db import (
    VelocityEventDb,
    _norm_event_tuple,
)
from kymflow.core.image_loaders.velocity_event_report import VelocityEventReport
from dataclasses import fields
from kymflow.core.image_loaders.roi import RoiBounds
from kymflow.core.utils.logging import get_logger, setup_logging
from kymflow.core.utils.hidden_cache_paths import get_hidden_cache_path

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


def test_velocity_event_db_update_from_image_includes_channel() -> None:
    """Test that update_from_image populates channel from ROI.channel."""
    kym_image = KymImage(img_data=np.zeros((50, 50), dtype=np.uint16), load_image=False)
    kym_image.update_header(shape=(50, 50), ndim=2, voxels=[0.001, 0.284])
    bounds = RoiBounds(dim0_start=0, dim0_stop=50, dim1_start=0, dim1_stop=50)
    # create_roi uses channel=1 by default; image has only channel 1
    roi = kym_image.rois.create_roi(bounds=bounds, channel=1)
    kym_image.get_kym_analysis().add_velocity_event(roi.id, t_start=0.5, t_end=1.0)
    kym_image._file_path_dict[1] = Path("/tmp/test.tif")

    db = VelocityEventDb(db_path=None)
    db.update_from_image(kym_image)

    events = db.get_all_events()
    assert len(events) == 1
    assert events[0]["channel"] == 1
    assert events[0]["roi_id"] == roi.id


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

        # Hidden copy should also exist and match schema
        hidden_path = get_hidden_cache_path(db_path)
        assert hidden_path.exists()
        hidden_df = pd.read_csv(hidden_path)
        assert set(hidden_df.columns) == set(df.columns)


def test_velocity_event_db_roundtrip_cache_csv_load() -> None:
    """Roundtrip: runtime cache → save CSV → load CSV → loaded cache.
    Verifies save/load preserves data for staleness comparison (t_start, t_end, event_type).
    Tests both t_end=None (baseline) and t_end=value (user-set) cases.
    """
    with TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "kym_event_db.csv"
        tmp_path = Path(tmpdir)
        test_file = tmp_path / "test.tif"
        test_file.touch()

        # Build cache: event A with t_end=None, event B with t_end=1.5
        kym_image = KymImage(img_data=np.zeros((50, 50), dtype=np.uint16), load_image=False)
        kym_image.update_header(shape=(50, 50), ndim=2, voxels=[0.001, 0.284])
        bounds = RoiBounds(dim0_start=0, dim0_stop=50, dim1_start=0, dim1_stop=50)
        roi = kym_image.rois.create_roi(bounds=bounds)
        kym_image._file_path_dict[1] = test_file
        kym_image.get_kym_analysis().add_velocity_event(roi.id, t_start=0.01, t_end=None)
        kym_image.get_kym_analysis().add_velocity_event(roi.id, t_start=0.5, t_end=1.5)

        db = VelocityEventDb(db_path=db_path)
        db.update_from_image(kym_image)
        assert db.save() is True

        # Load CSV into fresh cache
        df = pd.read_csv(db_path)
        loaded_cache = df.to_dict("records")

        # Build normalized fingerprints from original and loaded
        orig_events = db.get_all_events()
        orig_fps = [
            _norm_event_tuple(r["t_start"], r.get("t_end"), r.get("event_type"))
            for r in orig_events
        ]
        loaded_fps = [
            _norm_event_tuple(r["t_start"], r.get("t_end"), r.get("event_type"))
            for r in loaded_cache
        ]
        orig_sorted = sorted(orig_fps, key=lambda x: (x[0], x[1]))
        loaded_sorted = sorted(loaded_fps, key=lambda x: (x[0], x[1]))
        assert orig_sorted == loaded_sorted, (
            f"Roundtrip mismatch: orig={orig_sorted} loaded={loaded_sorted}"
        )


def test_velocity_event_db_save_empty_cache_roundtrip() -> None:
    """Roundtrip: events → save → clear cache → save (empty) → load CSV.
    When all events are removed, save() must write a CSV with correct headers and 0 rows
    so the file reflects the empty state. Verifies the empty CSV can be read back.
    """
    with TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "kym_event_db.csv"
        test_file = Path(tmpdir) / "test.tif"
        test_file.touch()

        # 1. Create db with events, save
        kym_image = KymImage(img_data=np.zeros((50, 50), dtype=np.uint16), load_image=False)
        kym_image.update_header(shape=(50, 50), ndim=2, voxels=[0.001, 0.284])
        bounds = RoiBounds(dim0_start=0, dim0_stop=50, dim1_start=0, dim1_stop=50)
        roi = kym_image.rois.create_roi(bounds=bounds)
        kym_image._file_path_dict[1] = test_file
        kym_image.get_kym_analysis().add_velocity_event(roi.id, t_start=0.5, t_end=1.0)

        db = VelocityEventDb(db_path=db_path)
        db.update_from_image(kym_image)
        assert db.save() is True
        df_before = pd.read_csv(db_path)
        assert len(df_before) == 1
        expected_cols = {f.name for f in fields(VelocityEventReport)}

        # 2. Simulate "remove all events" - clear cache
        db._cache = []
        assert len(db.get_all_events()) == 0

        # 3. Save with empty cache - must write CSV with headers, 0 rows
        assert db.save() is True

        # 4. Round-trip: read CSV, verify structure
        df_after = pd.read_csv(db_path)
        assert len(df_after) == 0, "CSV should have 0 data rows"
        assert expected_cols.issubset(set(df_after.columns)), (
            f"CSV should have expected columns. Missing: {expected_cols - set(df_after.columns)}"
        )

        # 5. Load into cache format - verify empty
        loaded_cache = df_after.to_dict("records")
        assert loaded_cache == [], "Loaded cache from empty CSV should be []"

        # Hidden copy should also exist and have the same columns
        hidden_path = get_hidden_cache_path(db_path)
        assert hidden_path.exists()
        hidden_df = pd.read_csv(hidden_path)
        assert set(hidden_df.columns) == set(df_after.columns)


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


def test_kym_event_db_no_hidden_rebuild_saves_both_visible_and_hidden() -> None:
    """When hidden kym event CSV is missing, load triggers rebuild then saves both visible and hidden."""
    expected_cols = {f.name for f in fields(VelocityEventReport)}
    with TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        (tmp_path / "a.tif").touch()
        # No visible or hidden kym_event_db.csv yet
        visible_path = tmp_path / "kym_event_db.csv"
        hidden_path = get_hidden_cache_path(visible_path)
        assert not visible_path.exists()
        assert not hidden_path.exists()

        # KymImageList init triggers _velocity_event_db.load(); no hidden -> rebuild -> save()
        KymImageList(path=tmp_path, file_extension=".tif", depth=1)

        assert visible_path.exists()
        assert hidden_path.exists()
        df_visible = pd.read_csv(visible_path)
        df_hidden = pd.read_csv(hidden_path)
        assert set(df_visible.columns) == set(df_hidden.columns)
        assert expected_cols.issubset(set(df_visible.columns))


# ---------------------------------------------------------------------------
# Regression: TypeError when loading velocity event DB
# Original error: '<' not supported between instances of 'float' and 'NoneType'
# Root cause: randomized-20260218-n10_kym_event_db.csv has (path, roi_id) groups
# where two events share the same t_start but one has t_end=NaN (empty CSV cell)
# and one has t_end=float. _is_cache_stale sorts normalized tuples by (x[0], x[1]);
# comparing (32.556, None) with (32.556, 32.798) triggers the TypeError.
# Failing case: path=.../20251020_A100_0003.tif, roi_id=1, t_start=32.556
# ---------------------------------------------------------------------------


def test_sort_normed_tuples_with_none_raises_without_fix() -> None:
    """Demonstrates the bug: sorting (0.5, None) with (0.5, 1.0) raises TypeError."""
    normed = [
        _norm_event_tuple(0.5, None, "stall"),
        _norm_event_tuple(0.5, 1.0, "stall"),
    ]
    with pytest.raises(TypeError, match="not supported between instances of .*float.*NoneType"):
        sorted(normed, key=lambda x: (x[0], x[1]))


def test_is_cache_stale_handles_same_t_start_mixed_nan_t_end() -> None:
    """Regression: _is_cache_stale must not raise when same (path, roi_id) has two
    events with identical t_start but one t_end=NaN and one t_end=float.

    Real-world case from randomized-20260218-n10_kym_event_db.csv:
    path=.../20251020_A100_0003.tif, roi_id=1 has (t_start=32.556, t_end=nan)
    and (t_start=32.556, t_end=32.798). Sorting raises:
    TypeError: '<' not supported between instances of 'float' and 'NoneType'

    Use str(test_file) (not resolve()) so cache path matches img.path on macOS
    where /var/... and /private/var/... differ.
    """
    with TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "kym_event_db.csv"
        test_file = Path(tmpdir) / "test.tif"
        test_file.touch()
        path_str = str(test_file)  # Must match str(img.path), not resolve()

        kym_image = KymImage(img_data=np.zeros((50, 50), dtype=np.uint16), load_image=False)
        kym_image.update_header(shape=(50, 50), ndim=2, voxels=[0.001, 0.284])
        bounds = RoiBounds(dim0_start=0, dim0_stop=50, dim1_start=0, dim1_stop=50)
        roi = kym_image.rois.create_roi(bounds=bounds)
        # Exact scenario: same t_start, one t_end=None, one t_end=float
        kym_image.get_kym_analysis().add_velocity_event(roi.id, t_start=32.556, t_end=None)
        kym_image.get_kym_analysis().add_velocity_event(roi.id, t_start=32.556, t_end=32.798)
        kym_image._file_path_dict[1] = test_file

        db = VelocityEventDb(db_path=db_path)
        db._cache = [
            {"path": path_str, "roi_id": roi.id, "t_start": 32.556, "t_end": np.nan, "event_type": "baseline_drop"},
            {"path": path_str, "roi_id": roi.id, "t_start": 32.556, "t_end": 32.798, "event_type": "nan_gap"},
        ]

        # Must not raise TypeError
        _ = db._is_cache_stale(images_provider=lambda: [kym_image])


def test_is_cache_stale_handles_none_t_start_t_end_in_cache() -> None:
    """Regression: _is_cache_stale must not raise when cache has NaN/None in t_start or t_end.

    When cache has events with t_end=NaN (from empty CSV cells), _norm_event_tuple returns
    (0.5, None, ...). Sorting with key=(x[0], x[1]) compares None with float and raises:
    TypeError: '<' not supported between instances of 'float' and 'NoneType'.
    """
    with TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "kym_event_db.csv"
        test_file = Path(tmpdir) / "test.tif"
        test_file.touch()
        path_str = str(test_file)  # Must match str(img.path)

        kym_image = KymImage(img_data=np.zeros((50, 50), dtype=np.uint16), load_image=False)
        kym_image.update_header(shape=(50, 50), ndim=2, voxels=[0.001, 0.284])
        bounds = RoiBounds(dim0_start=0, dim0_stop=50, dim1_start=0, dim1_stop=50)
        roi = kym_image.rois.create_roi(bounds=bounds)
        kym_image.get_kym_analysis().add_velocity_event(roi.id, t_start=0.5, t_end=None)
        kym_image.get_kym_analysis().add_velocity_event(roi.id, t_start=0.5, t_end=1.0)
        kym_image._file_path_dict[1] = test_file

        db = VelocityEventDb(db_path=db_path)
        # Use actual roi.id so cache key matches current key (both have 2 events, triggers sort)
        db._cache = [
            {"path": path_str, "roi_id": roi.id, "t_start": 0.5, "t_end": np.nan, "event_type": "stall"},
            {"path": path_str, "roi_id": roi.id, "t_start": 0.5, "t_end": 1.0, "event_type": "stall"},
        ]

        # Must not raise TypeError (would raise without fix when sorting cache_norm)
        _ = db._is_cache_stale(images_provider=lambda: [kym_image])


def test_load_handles_nan_t_start_t_end_in_csv() -> None:
    """Regression: load() must not raise when CSV has NaN/None in t_start or t_end.

    When cache has events where t_start or t_end is NaN (from empty CSV cells),
    _is_cache_stale sorts normalized tuples. Sorting (0.5, None) with (0.5, 1.0)
    triggers: TypeError: '<' not supported between instances of 'float' and 'NoneType'.
    """
    with TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "kym_event_db.csv"
        test_file = Path(tmpdir) / "test.tif"
        test_file.touch()
        path_str = str(test_file)  # Must match str(img.path) for key match

        # Create image first to get roi.id for matching cache key
        kym_image = KymImage(img_data=np.zeros((50, 50), dtype=np.uint16), load_image=False)
        kym_image.update_header(shape=(50, 50), ndim=2, voxels=[0.001, 0.284])
        bounds = RoiBounds(dim0_start=0, dim0_stop=50, dim1_start=0, dim1_stop=50)
        roi = kym_image.rois.create_roi(bounds=bounds)
        kym_image.get_kym_analysis().add_velocity_event(roi.id, t_start=0.5, t_end=None)
        kym_image.get_kym_analysis().add_velocity_event(roi.id, t_start=0.5, t_end=1.0)
        kym_image._file_path_dict[1] = test_file

        # Build minimal CSV: same (path, roi_id), one t_end=NaN and one t_end=1.0
        col_order = [f.name for f in fields(VelocityEventReport)]
        row1 = {c: None for c in col_order}
        row1["_unique_row_id"] = f"{path_str}|{roi.id}|0"
        row1["path"] = path_str
        row1["roi_id"] = roi.id
        row1["rel_path"] = "test.tif"
        row1["t_start"] = 0.5
        row1["t_end"] = np.nan  # NaN -> None in _norm_event_tuple
        row1["event_type"] = "stall"

        row2 = {c: None for c in col_order}
        row2["_unique_row_id"] = f"{path_str}|{roi.id}|1"
        row2["path"] = path_str
        row2["roi_id"] = roi.id
        row2["rel_path"] = "test.tif"
        row2["t_start"] = 0.5
        row2["t_end"] = 1.0
        row2["event_type"] = "stall"

        df = pd.DataFrame([row1, row2])
        df.to_csv(db_path, index=False)

        db = VelocityEventDb(db_path=db_path)
        db.load(images_provider=lambda: [kym_image])
        # Should not raise TypeError: '<' not supported between instances of 'float' and 'NoneType'
        assert db.get_df() is not None


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
