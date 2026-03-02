from __future__ import annotations

from pathlib import Path

from gui.file_table_integration import build_kym_image_list, filter_tiff_images, iter_kym_images


def test_build_kym_image_list_missing_folder_returns_warning(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist"
    kym_list, warning = build_kym_image_list(missing)
    assert kym_list is None
    assert warning is not None


def test_filter_tiff_images_with_kym_image_list(tmp_path: Path) -> None:
    (tmp_path / "a.tif").write_bytes(b"")
    (tmp_path / "b.tiff").write_bytes(b"")
    (tmp_path / "c.txt").write_text("x", encoding="utf-8")

    kym_list, warning = build_kym_image_list(tmp_path)
    assert warning is None
    assert kym_list is not None

    filtered = filter_tiff_images(iter_kym_images(kym_list))
    suffixes = {Path(str(img.path)).suffix.lower() for img in filtered}
    assert suffixes.issubset({".tif", ".tiff"})
    assert ".txt" not in suffixes


def test_iter_kym_images_fallback_iterable() -> None:
    class _DummyList:
        def __iter__(self):
            return iter([1, 2, 3])

    assert list(iter_kym_images(_DummyList())) == [1, 2, 3]
