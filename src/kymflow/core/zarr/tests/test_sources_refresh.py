"""Tests for dataset sources index and refresh ingest behavior."""

from __future__ import annotations

from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from kymflow_zarr import ZarrDataset


def _require_tifffile():
    return pytest.importorskip("tifffile")


def test_sources_index_populated_on_ingest_and_refresh(tmp_path: Path) -> None:
    pytest.importorskip("pyarrow")
    tifffile = _require_tifffile()

    legacy = tmp_path / "legacy"
    legacy.mkdir(parents=True, exist_ok=True)

    for i in range(2):
        tifffile.imwrite(str(legacy / f"s{i}.tif"), (np.random.rand(10, 10) * 255).astype(np.uint8))

    ds = ZarrDataset(str(tmp_path / "ds.zarr"), mode="a")
    ds.ingest_legacy_folder(legacy)

    sources = ds.load_sources_index()
    assert len(sources) == 2
    assert set(sources.columns) == {
        "source_primary_path",
        "image_id",
        "source_mtime_ns",
        "source_size_bytes",
        "ingested_epoch_ns",
    }

    tifffile.imwrite(str(legacy / "s2.tif"), (np.random.rand(10, 10) * 255).astype(np.uint8))
    new_ids = ds.refresh_from_folder(legacy)
    assert len(new_ids) == 1

    sources2 = ds.load_sources_index()
    assert len(sources2) == 3

    again = ds.refresh_from_folder(legacy)
    assert again == []
