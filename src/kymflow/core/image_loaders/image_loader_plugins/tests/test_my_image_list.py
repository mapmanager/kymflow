"""Tests for :mod:`my_image_list`.

Run from the ``kymflow`` project root::

    KYMFLOW_DISABLE_FILE_LOG=1 uv run pytest src/kymflow/core/image_loaders/image_loader_plugins/tests/test_my_image_list.py
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from kymflow.core.image_loaders.image_loader_plugins.my_image_list import (
    MyImageList,
    PixelLoadPolicy,
)
from kymflow.core.image_loaders.image_loader_plugins.my_image_import import MyCziImage

_TESTS_DIR = Path(__file__).resolve().parent
_FIXTURES = _TESTS_DIR / "fixtures"

FIXTURE_OIR_DIR = _FIXTURES / "oir-samples"
FIXTURE_CZI_ROOT = _FIXTURES / "czi-samples"
FIXTURE_CZI_ONE = (
    _FIXTURES
    / "czi-samples"
    / "disjointedlinescansandframescans"
    / "disjointlinescanisofluranetest.czi"
)
FIXTURE_TIF = (
    _FIXTURES
    / "tif-samples"
    / "20251030_A106_0002.tif.frames"
    / "20251030_A106_0002.tif"
)


def test_fixture_paths_exist() -> None:
    assert FIXTURE_OIR_DIR.is_dir()
    assert FIXTURE_CZI_ROOT.is_dir()
    assert FIXTURE_CZI_ONE.is_file()
    assert FIXTURE_TIF.is_file()


def test_init_does_not_read_czi_headers() -> None:
    with patch.object(
        MyCziImage,
        "read_header_from_path",
        wraps=MyCziImage.read_header_from_path,
    ) as spy:
        lst = MyImageList(
            FIXTURE_CZI_ROOT,
            find_these_extensions=["czi"],
            max_depth=2,
        )
        assert spy.call_count == 0
        assert len(lst) > 0
        lst.header_records()
        assert spy.call_count == len(lst)


def test_depth_zero_czi_root_has_no_czi() -> None:
    lst = MyImageList(
        FIXTURE_CZI_ROOT,
        find_these_extensions=["czi"],
        max_depth=0,
    )
    assert len(lst) == 0


def test_depth_one_czi_root_finds_subfolder_czi() -> None:
    lst = MyImageList(
        FIXTURE_CZI_ROOT,
        find_these_extensions=["czi"],
        max_depth=1,
    )
    assert len(lst) >= 1
    paths = {r["path"] for r in lst.header_records()}
    assert str(FIXTURE_CZI_ONE.resolve()) in paths


def test_oir_flat_folder_max_depth_zero() -> None:
    lst = MyImageList(
        FIXTURE_OIR_DIR,
        find_these_extensions=["oir"],
        max_depth=0,
    )
    assert len(lst) >= 1
    for rec in lst.header_records():
        assert rec["format"] == "oir"
        assert rec["header_loaded"] is True
        assert rec["error"] is None


def test_header_record_has_ancestry_and_display_fields() -> None:
    lst = MyImageList(
        FIXTURE_OIR_DIR,
        find_these_extensions=["oir"],
        max_depth=0,
    )
    rec = lst.header_records()[0]
    assert rec["relative_path"] == Path(rec["path"]).relative_to(lst.folder).as_posix()
    assert Path(rec["parent_dir"]) == Path(rec["path"]).parent
    assert Path(rec["grandparent_dir"]) == Path(rec["path"]).parent.parent
    assert rec["parent_name"] == Path(rec["parent_dir"]).name
    assert rec["grandparent_name"] == Path(rec["grandparent_dir"]).name
    assert rec["file_name"] == Path(rec["path"]).name
    assert "shape_display" in rec
    assert "dims_display" in rec
    assert "dtype" in rec
    assert rec["dtype"]  # string from ImageHeader.as_json_dict()
    assert "physical_units" in rec
    assert "physical_units_labels" in rec


def test_get_loader_for_relative_path(tmp_path: Path) -> None:
    sub = tmp_path / "nested"
    sub.mkdir()
    p = sub / "x.czi"
    p.write_bytes(FIXTURE_CZI_ONE.read_bytes())
    lst = MyImageList(tmp_path, find_these_extensions=["czi"], max_depth=2)
    rel = "nested/x.czi"
    assert lst.header_records()[0]["relative_path"] == rel
    loader = lst.get_loader_for_relative_path(rel)
    assert loader.header.path == str(p.resolve())


def test_iter_matches_header_records() -> None:
    lst = MyImageList(
        FIXTURE_OIR_DIR,
        find_these_extensions=["oir"],
        max_depth=0,
    )
    assert list(iter(lst)) == lst.header_records()


def test_get_loader_caches_same_instance() -> None:
    lst = MyImageList(
        FIXTURE_OIR_DIR,
        find_these_extensions=["oir"],
        max_depth=0,
    )
    p = str(next(iter(Path(FIXTURE_OIR_DIR).glob("*.oir"))).resolve())
    a = lst.get_loader_for_path(p)
    b = lst.get_loader_for_path(p)
    assert a is b


def test_get_loader_at_index_matches_get_loader_for_path() -> None:
    lst = MyImageList(
        FIXTURE_OIR_DIR,
        find_these_extensions=["oir"],
        max_depth=0,
    )
    assert lst.get_loader_at_index(0) is lst.get_loader_for_path(lst.header_records()[0]["path"])


def test_header_error_row_no_fail_fast(tmp_path: Path) -> None:
    bad = tmp_path / "bad.czi"
    bad.write_bytes(b"not a czi")
    good = tmp_path / "good.czi"
    good.write_bytes(FIXTURE_CZI_ONE.read_bytes())

    lst = MyImageList(tmp_path, find_these_extensions=["czi"], max_depth=0)
    assert len(lst) == 2
    by_name = {Path(r["path"]).name: r for r in lst.header_records()}
    assert by_name["bad.czi"]["error"] is not None
    assert by_name["bad.czi"]["header_loaded"] is False
    assert by_name["good.czi"]["header_loaded"] is True
    assert by_name["good.czi"]["error"] is None
    loader = lst.get_loader_for_path(str(good.resolve()))
    assert loader.header.path == str(good.resolve())
    with pytest.raises(ValueError):
        lst.get_loader_for_path(str(bad.resolve()))


def test_ome_tiff_row_and_get_loader_raises(tmp_path: Path) -> None:
    ome = tmp_path / "sample.ome.tif"
    ome.write_bytes(b"x")
    lst = MyImageList(tmp_path, find_these_extensions=["tif"], max_depth=0)
    assert len(lst) == 1
    rec = lst.header_records()[0]
    assert rec["format"] == "ome-tiff"
    assert rec["header_loaded"] is False
    assert rec["error"] is not None
    with pytest.raises(ValueError, match="OME-TIFF"):
        lst.get_loader_for_path(str(ome.resolve()))


def test_describe_pixel_load_and_record_for_relative_path(tmp_path: Path) -> None:
    pytest.importorskip("tifffile")
    import numpy as np
    import tifffile
    from tifffile import PHOTOMETRIC

    p = tmp_path / "small.tif"
    tifffile.imwrite(p, np.zeros((2, 3), dtype=np.uint8), photometric=PHOTOMETRIC.MINISBLACK)
    lst = MyImageList(tmp_path, find_these_extensions=["tif"], max_depth=0)
    rel = "small.tif"
    pol = lst.describe_pixel_load(rel)
    assert isinstance(pol, PixelLoadPolicy)
    assert pol.allowed is True
    assert pol.code == "ok"
    rec = lst.record_for_relative_path(rel)
    assert rec is not None
    assert rec["relative_path"] == rel
    assert lst.record_for_relative_path("missing.tif") is None
    bad_pol = lst.describe_pixel_load("missing.tif")
    assert bad_pol.allowed is False
    assert bad_pol.code == "not_in_catalog"


def test_tif_placeholder_then_loader(tmp_path: Path) -> None:
    pytest.importorskip("tifffile")
    import numpy as np
    import tifffile
    from tifffile import PHOTOMETRIC

    p = tmp_path / "small.tif"
    tifffile.imwrite(p, np.zeros((2, 3), dtype=np.uint8), photometric=PHOTOMETRIC.MINISBLACK)
    lst = MyImageList(tmp_path, find_these_extensions=["tif"], max_depth=0)
    rec = lst.header_records()[0]
    assert rec["format"] == "tif"
    assert rec["header_loaded"] is False
    loader = lst.get_loader_for_path(str(p.resolve()))
    assert loader.header.shape == (2, 3)


def test_mixed_extensions_under_fixtures() -> None:
    lst = MyImageList(
        _FIXTURES,
        find_these_extensions=["czi", "oir", "tif"],
        max_depth=4,
    )
    formats = {r["format"] for r in lst.header_records()}
    assert "oir" in formats
    assert "czi" in formats
    assert "tif" in formats


def test_empty_find_extensions_raises() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        MyImageList(FIXTURE_OIR_DIR, find_these_extensions=[], max_depth=0)


def test_non_directory_raises(tmp_path: Path) -> None:
    f = tmp_path / "notadir.txt"
    f.write_text("x")
    with pytest.raises(ValueError, match="directory"):
        MyImageList(f, find_these_extensions=["tif"], max_depth=0)
