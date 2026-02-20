# Filename: src/kymflow_zarr/experimental_stores/acq_image_list.py
"""Experimental AcqImageListV01 (folder scan or Zarr dataset)."""

from __future__ import annotations

from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, List

from .acq_image import AcqImageV01
from .stores import stores_for_path


@dataclass
class AcqImageListV01:
    """Enumerate images from a folder of TIFFs or a Zarr dataset."""

    root: str | Path
    file_extension: str = ".tif"

    def __post_init__(self) -> None:
        self.root = str(Path(self.root).resolve())
        self.images: List[AcqImageV01] = []
        self._load()

    def _load(self) -> None:
        p = Path(self.root)
        if p.suffix.lower() == ".zarr":
            # Zarr dataset: keys are image ids
            px, art = stores_for_path(p)
            # px is a ZarrStore which has ds.list_image_ids
            image_ids = px.ds.list_image_ids()  # type: ignore[attr-defined]
            for image_id in image_ids:
                self.images.append(AcqImageV01.from_zarr(p, image_id))
            return

        folder = p
        glob = f"*{self.file_extension}" if self.file_extension.startswith(".") else f"*.{self.file_extension}"
        for fp in sorted(folder.rglob(glob)):
            if not fp.is_file():
                continue
            self.images.append(AcqImageV01.from_path(fp))

    def __len__(self) -> int:
        return len(self.images)

    def __iter__(self) -> Iterator[AcqImageV01]:
        return iter(self.images)
