from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from kymflow.core.image_loaders.kym_image_list import KymImageList

# SEED_FOLDER = "/Users/cudmore/Dropbox/data/cell-shortening/fig1"
SEED_FOLDER = "/Users/cudmore/Downloads/kymflow_app/cell-shortening/fig1"


def build_kym_image_list(seed_folder: str | Path = SEED_FOLDER) -> tuple[KymImageList | None, str | None]:
    folder = Path(seed_folder).expanduser()
    if not folder.exists():
        return None, f"File browser seed folder missing: {folder}"

    try:
        return KymImageList(path=folder), None
    except Exception as e:
        return None, f"Failed to load file browser list: {e}"


def iter_kym_images(kml: KymImageList) -> Iterable[Any]:
    try:
        images = getattr(kml, "images", None)
        if images is not None:
            return images
    except Exception:
        pass

    try:
        return iter(kml)
    except Exception:
        return ()


def filter_tiff_images(images: Iterable[Any]) -> list[Any]:
    out: list[Any] = []
    for img in images:
        p = getattr(img, "path", None)
        if p is None:
            continue
        suffix = Path(str(p)).suffix.lower()
        if suffix in {".tif", ".tiff"}:
            out.append(img)
    return out


# abb depreciate, not needed when using KymImageList
def find_kym_image_by_path(kml: KymImageList | None, path: str | Path) -> Any | None:
    if kml is None:
        return None
    target = str(Path(path))
    for img in iter_kym_images(kml):
        img_path = getattr(img, "path", None)
        if img_path is None:
            continue
        if str(img_path) == target:
            return img
    return None
