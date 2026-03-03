from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from .diameter_kymflow_adapter import (
    get_kym_by_path,
    list_file_table_kym_images,
    load_kym_list_for_folder,
)

SEED_FOLDER = "/Users/cudmore/Downloads/kymflow_app/cell-shortening/fig1"


def build_kym_image_list(seed_folder: str | Path = SEED_FOLDER) -> tuple[Any | None, str | None]:
    folder = Path(seed_folder).expanduser()
    if not folder.exists():
        return None, f"File browser seed folder missing: {folder}"
    try:
        return load_kym_list_for_folder(folder), None
    except Exception as e:
        return None, f"Failed to load file browser list: {e}"


def iter_kym_images(kml: Any) -> Iterable[Any]:
    try:
        return list_file_table_kym_images(kml)
    except Exception:
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


def find_kym_image_by_path(kml: Any | None, path: str | Path) -> Any | None:
    if kml is None:
        return None
    return get_kym_by_path(kml, path)
