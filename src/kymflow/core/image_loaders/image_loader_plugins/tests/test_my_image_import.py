"""Tests for ``my_image_import``.

Run from the ``kymflow`` project root::

    uv run pytest src/kymflow/core/image_loaders/image_loader_plugins/tests/
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import tifffile
from tifffile import PHOTOMETRIC

from kymflow.core.image_loaders.image_loader_plugins.my_image_import import (
    ImageHeader,
    ImageLoaderBase,
    MyCziImage,
    MyOirImage,
    MyTifImage,
    PlotlyHeatmapUniformAxes2D,
    image_header_from_olympus_dict,
    image_loader_from_upload,
    preview_yx_shape_hint,
    preview_yx_shape_hint_from_catalog_record,
)
from kymflow.core.image_loaders.image_loader_plugins.olympus_txt_kym import (
    read_olympus_txt_dict,
)

# Paths under tests/fixtures/ (relative to this package's tests directory).
_TESTS_DIR = Path(__file__).resolve().parent
_FIXTURES = _TESTS_DIR / "fixtures"

FIXTURE_OIR_PRIMARY = _FIXTURES / "oir-samples" / "20251030_A106.oir"
FIXTURE_OIR_SECONDARY = _FIXTURES / "oir-samples" / "20251030_A106_0001.oir"
FIXTURE_CZI_LINE = (
    _FIXTURES
    / "czi-samples"
    / "disjointedlinescansandframescans"
    / "disjointlinescanisofluranetest.czi"
)
FIXTURE_CZI_CO2 = _FIXTURES / "czi-samples" / "linescansForVelocityMeasurement" / "CO2.czi"


def _assert_headers_equivalent(a: ImageHeader, b: ImageHeader) -> None:
    """Compare headers; treat NaN == NaN in ``physical_units``."""
    assert a.path == b.path
    assert a.shape == b.shape
    assert a.dims == b.dims
    assert a.sizes == b.sizes
    assert a.dtype == b.dtype
    assert a.num_channels == b.num_channels
    assert a.num_scenes == b.num_scenes
    assert a.physical_units_labels == b.physical_units_labels
    assert len(a.physical_units) == len(b.physical_units)
    for u, v in zip(a.physical_units, b.physical_units, strict=True):
        if isinstance(u, float) and isinstance(v, float) and np.isnan(u) and np.isnan(v):
            continue
        assert u == v
    assert a.date == b.date
    assert a.time == b.time


def _assert_headers_equivalent_except_path(a: ImageHeader, b: ImageHeader) -> None:
    """Same as :func:`_assert_headers_equivalent` but ignores ``path`` (disk vs upload name)."""
    assert a.shape == b.shape
    assert a.dims == b.dims
    assert a.sizes == b.sizes
    assert a.dtype == b.dtype
    assert a.num_channels == b.num_channels
    assert a.num_scenes == b.num_scenes
    assert a.physical_units_labels == b.physical_units_labels
    assert len(a.physical_units) == len(b.physical_units)
    for u, v in zip(a.physical_units, b.physical_units, strict=True):
        if isinstance(u, float) and isinstance(v, float) and np.isnan(u) and np.isnan(v):
            continue
        assert u == v
    assert a.date == b.date
    assert a.time == b.time


@pytest.fixture(scope="module", params=[FIXTURE_OIR_PRIMARY, FIXTURE_OIR_SECONDARY])
def oir_path(request: pytest.FixtureRequest) -> Path:
    p = request.param
    assert p.is_file(), f"Missing fixture: {p}"
    return p


@pytest.fixture(scope="module", params=[FIXTURE_CZI_LINE, FIXTURE_CZI_CO2])
def czi_path(request: pytest.FixtureRequest) -> Path:
    p = request.param
    assert p.is_file(), f"Missing fixture: {p}"
    return p


def test_fixture_files_exist() -> None:
    """Hard requirement: chosen fixtures must be present on disk."""
    for p in (
        FIXTURE_OIR_PRIMARY,
        FIXTURE_OIR_SECONDARY,
        FIXTURE_CZI_LINE,
        FIXTURE_CZI_CO2,
    ):
        assert p.is_file(), f"Expected fixture file: {p}"


def test_image_header_default_physical_for_dims() -> None:
    units, labels = ImageHeader.default_physical_for_dims(("Y", "X"))
    assert units == (1.0, 1.0)
    assert labels == ("Pixels", "Pixels")
    u4, l4 = ImageHeader.default_physical_for_dims(("C", "Z", "Y", "X"))
    assert u4 == (1.0, 1.0, 1.0, 1.0)
    assert l4 == ("Pixels", "Pixels", "Pixels", "Pixels")


def test_array_for_plotly_display_uint8_and_uint16() -> None:
    u8 = np.array([[0, 255], [10, 20]], dtype=np.uint8)
    out8 = ImageLoaderBase.array_for_plotly_display(u8)
    assert out8.dtype == np.uint8
    assert np.array_equal(out8, u8)

    u16 = np.array([[0, 65535], [1000, 2000]], dtype=np.uint16)
    out16 = ImageLoaderBase.array_for_plotly_display(u16)
    assert out16.dtype == np.uint8
    assert int(out16.min()) == 0
    assert int(out16.max()) == 255

    const = np.full((2, 3), 42, dtype=np.uint16)
    assert np.all(ImageLoaderBase.array_for_plotly_display(const) == 0)


def test_preview_yx_shape_hint_from_sizes() -> None:
    h = MyOirImage(str(FIXTURE_OIR_PRIMARY)).header
    assert preview_yx_shape_hint(h) == preview_yx_shape_hint_from_catalog_record(h.as_json_dict())


def test_preview_yx_shape_hint_fallback() -> None:
    assert preview_yx_shape_hint_from_catalog_record({}) == "shape TBD"
    assert "dims" in preview_yx_shape_hint_from_catalog_record({"dims": ["T", "Y", "X"]})


def test_step_from_coord_spacing() -> None:
    """``ImageLoaderBase._step_from_coord`` returns float delta for length >= 2."""
    assert ImageLoaderBase._step_from_coord(np.array([0.0, 1.0, 2.0])) == 1.0
    assert ImageLoaderBase._step_from_coord([3.0, 5.5]) == 2.5


def test_step_from_coord_short_or_none() -> None:
    assert ImageLoaderBase._step_from_coord(None) is None
    assert ImageLoaderBase._step_from_coord(np.array([1.0])) is None
    assert ImageLoaderBase._step_from_coord([]) is None


class _Harness(ImageLoaderBase):
    """Minimal concrete loader to exercise :meth:`ImageLoaderBase._image_header_from_scene`."""

    def read_header(self) -> ImageHeader:
        raise NotImplementedError

    def _physical_units_for_header(
        self, scene: object
    ) -> tuple[tuple[float, ...], tuple[str, ...]]:
        return ((1.0, 2.0), ("a", "b"))

    def _load_full_image_array(self) -> np.ndarray:
        raise NotImplementedError


def test_image_header_from_scene_builds_expected_fields() -> None:
    scene = SimpleNamespace(
        shape=(2, 3, 4),
        dims=("C", "Y", "X"),
        sizes={"C": 2, "Y": 3, "X": 4},
        dtype=np.dtype("uint16"),
    )
    h = _Harness.__new__(_Harness)
    hdr = h._image_header_from_scene("/tmp/example", scene, num_scenes=7)
    assert hdr.path == "/tmp/example"
    assert hdr.shape == (2, 3, 4)
    assert hdr.dims == ("C", "Y", "X")
    assert hdr.sizes == {"C": 2, "Y": 3, "X": 4}
    assert hdr.dtype == np.dtype("uint16")
    assert hdr.num_channels == 2
    assert hdr.num_scenes == 7
    assert hdr.physical_units == (1.0, 2.0)
    assert hdr.physical_units_labels == ("a", "b")
    assert hdr.date == ""
    assert hdr.time == ""


def test_oir_header_date_time_from_fixture(oir_path: Path) -> None:
    h = MyOirImage(str(oir_path)).header
    assert len(h.date) == 8
    assert h.date.isdigit()
    parts = h.time.split(":")
    assert len(parts) == 3
    assert all(p.isdigit() for p in parts)


def test_czi_header_date_time_empty(czi_path: Path) -> None:
    h = MyCziImage(str(czi_path)).header
    assert h.date == ""
    assert h.time == ""


def test_oir_read_header_from_path_and_roundtrip(oir_path: Path) -> None:
    h1 = MyOirImage.read_header_from_path(str(oir_path))
    h2 = MyOirImage(str(oir_path)).header
    _assert_headers_equivalent(h1, h2)
    assert h1.num_scenes == 1
    assert "Y" in h1.dims and "X" in h1.dims


def test_czi_read_header_from_path_and_roundtrip(czi_path: Path) -> None:
    h1 = MyCziImage.read_header_from_path(str(czi_path))
    h2 = MyCziImage(str(czi_path)).header
    _assert_headers_equivalent(h1, h2)
    assert h1.num_scenes >= 1


def test_oir_stream_header_matches_disk(oir_path: Path) -> None:
    data = oir_path.read_bytes()
    stream = io.BytesIO(data)
    h_disk = MyOirImage(str(oir_path)).header
    h_stream = MyOirImage.from_stream(stream, oir_path.name).header
    assert h_stream.path == oir_path.name
    _assert_headers_equivalent_except_path(h_disk, h_stream)


def test_czi_stream_header_matches_disk(czi_path: Path) -> None:
    data = czi_path.read_bytes()
    stream = io.BytesIO(data)
    h_disk = MyCziImage(str(czi_path)).header
    h_stream = MyCziImage.from_stream(stream, czi_path.name).header
    assert h_stream.path == czi_path.name
    _assert_headers_equivalent_except_path(h_disk, h_stream)


def test_image_loader_from_upload_dispatches(
    oir_path: Path, czi_path: Path, tmp_path: Path
) -> None:
    oir_data = oir_path.read_bytes()
    czi_data = czi_path.read_bytes()
    oir_loader = image_loader_from_upload(io.BytesIO(oir_data), oir_path.name)
    czi_loader = image_loader_from_upload(io.BytesIO(czi_data), czi_path.name)
    assert type(oir_loader).__name__ == "MyOirImage"
    assert type(czi_loader).__name__ == "MyCziImage"
    tif_path = tmp_path / "upload.tif"
    arr = np.arange(12, dtype=np.uint16).reshape(3, 4)
    tifffile.imwrite(tif_path, arr)
    tif_data = tif_path.read_bytes()
    tif_loader = image_loader_from_upload(io.BytesIO(tif_data), tif_path.name)
    assert type(tif_loader).__name__ == "MyTifImage"


def test_image_loader_from_upload_rejects_ome_tiff() -> None:
    with pytest.raises(ValueError, match="OME-TIFF"):
        image_loader_from_upload(io.BytesIO(b"x"), "sample.ome.tif")


def test_image_loader_from_upload_bad_extension() -> None:
    with pytest.raises(ValueError, match="Unsupported"):
        image_loader_from_upload(io.BytesIO(b"x"), "bad.txt")


def test_image_header_as_json_dict_roundtrip(oir_path: Path) -> None:
    h = MyOirImage(str(oir_path)).header
    payload = h.as_json_dict()
    json.dumps(payload)
    assert payload["dtype"] == str(h.dtype)
    assert isinstance(payload["shape"], list)
    assert "date" in payload and "time" in payload
    assert payload["date"] == h.date
    assert payload["time"] == h.time


def test_olympus_txt_header_date_time_matches_combined_line() -> None:
    pytest.importorskip("tifffile")
    tif_path = (
        _FIXTURES
        / "tif-samples"
        / "20251030_A106_0002.tif.frames"
        / "20251030_A106_0002.tif"
    )
    if not tif_path.is_file():
        pytest.skip(f"Missing fixture: {tif_path}")
    od = read_olympus_txt_dict(tif_path)
    assert od is not None
    h = image_header_from_olympus_dict(str(tif_path), od)
    assert h.date == "20251030"
    assert h.time == "14:54:36"


def test_oir_load_and_get_slice(oir_path: Path) -> None:
    img = MyOirImage(str(oir_path))
    sl = img.get_slice_data(0)
    assert sl.ndim == 2
    assert sl.shape == (img.header.sizes["Y"], img.header.sizes["X"])


def test_oir_get_channel_matches_shape(oir_path: Path) -> None:
    img = MyOirImage(str(oir_path))
    full = img.load_image_data()
    ch = img.get_channel_data(0)
    if "C" in img.header.dims:
        c_axis = img.header.dims.index("C")
        assert ch.shape == tuple(
            s for i, s in enumerate(full.shape) if i != c_axis
        )
    else:
        assert ch.shape == full.shape


def test_czi_load_and_get_channel(czi_path: Path) -> None:
    img = MyCziImage(str(czi_path))
    full = img.load_image_data()
    ch = img.get_channel_data(0)
    if "C" in img.header.dims:
        assert ch.ndim == full.ndim - 1
    else:
        assert ch.shape == full.shape


def test_czi_get_slice_when_yx_present(czi_path: Path) -> None:
    img = MyCziImage(str(czi_path))
    if "Y" not in img.header.dims or "X" not in img.header.dims:
        pytest.skip("Fixture has no Y/X slice semantics for get_slice_data")
    sl = img.get_slice_data(0)
    assert sl.ndim == 2


def test_my_tif_2d_header_and_load(tmp_path: Path) -> None:
    arr = np.arange(12, dtype=np.uint16).reshape(3, 4)
    p = tmp_path / "two_d.tif"
    tifffile.imwrite(p, arr)
    img = MyTifImage(str(p))
    h = img.header
    assert h.dims == ("Y", "X")
    assert h.shape == (3, 4)
    assert h.num_channels == 1
    assert h.physical_units == (1.0, 1.0)
    assert h.physical_units_labels == ("Pixels", "Pixels")
    loaded = img.load_image_data()
    assert np.array_equal(loaded, arr)


def test_my_tif_3d_and_4d_dims(tmp_path: Path) -> None:
    a3 = np.zeros((5, 3, 4), dtype=np.float32)
    p3 = tmp_path / "three.tif"
    tifffile.imwrite(p3, a3, photometric=PHOTOMETRIC.MINISBLACK)
    h3 = MyTifImage(str(p3)).header
    assert h3.dims == ("Z", "Y", "X")
    assert h3.shape == (5, 3, 4)
    a4 = np.zeros((2, 5, 3, 4), dtype=np.uint8)
    p4 = tmp_path / "four.tif"
    tifffile.imwrite(p4, a4, photometric=PHOTOMETRIC.MINISBLACK)
    h4 = MyTifImage(str(p4)).header
    assert h4.dims == ("C", "Z", "Y", "X")
    assert h4.num_channels == 2


def test_my_tif_stream_header_matches_disk(tmp_path: Path) -> None:
    arr = np.arange(6, dtype=np.uint16).reshape(2, 3)
    p = tmp_path / "stream.tif"
    tifffile.imwrite(p, arr)
    data = p.read_bytes()
    h_disk = MyTifImage(str(p)).header
    h_stream = MyTifImage.from_stream(io.BytesIO(data), p.name).header
    assert h_stream.path == p.name
    _assert_headers_equivalent_except_path(h_disk, h_stream)


def test_my_tif_rejects_ndim_gt_four(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_imread(_source: object, **_kwargs: object) -> np.ndarray:
        return np.zeros((1, 1, 1, 1, 1), dtype=np.uint8)

    monkeypatch.setattr(
        "kymflow.core.image_loaders.image_loader_plugins.my_image_import.tifffile.imread",
        fake_imread,
    )
    with pytest.raises(ValueError, match="Unsupported TIFF ndim 5"):
        MyTifImage("/nonexistent/does_not_matter.tif").header


def test_unload_clears_cache(oir_path: Path) -> None:
    img = MyOirImage(str(oir_path))
    img.load_image_data()
    assert img._img_data is not None  # noqa: SLF001
    img.unload_image_data()
    assert img._img_data is None  # noqa: SLF001
    again = img.load_image_data()
    assert again is not None


def test_image_header_plotly_heatmap_uniform_axes_for_transpose_z() -> None:
    """2D slice (Y, X); z = arr.T → Plotly x = Y dim, y = X dim (cell-centered when stepped)."""
    h = ImageHeader(
        path="/x.tif",
        shape=(10, 20, 30),
        dims=("Z", "Y", "X"),
        sizes={"Z": 10, "Y": 20, "X": 30},
        dtype=np.dtype("uint8"),
        num_channels=1,
        num_scenes=1,
        physical_units=(1.0, 2.0, 0.5),
        physical_units_labels=("z", "µm", "µm"),
    )
    ax = h.plotly_heatmap_uniform_axes_for_transpose_z((4, 5))
    assert isinstance(ax, PlotlyHeatmapUniformAxes2D)
    assert ax.x0 == 1.0 and ax.dx == 2.0
    assert ax.y0 == 0.25 and ax.dy == 0.5
    assert ax.x_title == "µm" and ax.y_title == "µm"
    assert ax.x_range == (0.0, 8.0)
    assert ax.y_range == (0.0, 2.5)


def test_image_header_plotly_heatmap_uniform_axes_fallback_pixel_indices() -> None:
    h = ImageHeader(
        path="/x.tif",
        shape=(3, 4),
        dims=("Y", "X"),
        sizes={"Y": 3, "X": 4},
        dtype=np.dtype("uint8"),
        num_channels=1,
        num_scenes=1,
        physical_units=(float("nan"), 1.0),
        physical_units_labels=("t", "µm"),
    )
    ax = h.plotly_heatmap_uniform_axes_for_transpose_z((2, 3))
    assert ax.x0 == 0.0 and ax.dx == 1.0
    assert ax.y0 == 0.5 and ax.dy == 1.0
    assert ax.x_range == (-0.5, 1.5)
    assert ax.y_range == (0.0, 3.0)
