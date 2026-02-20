"""Tests for KymDataset v0.1 indexer workflow."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from kymflow.core.kym_dataset.kym_dataset import KymDataset
from kymflow_zarr import ZarrDataset, ZarrImageRecord


@dataclass
class _SimpleIndexer:
    name: str = "simple"
    metric_value: float = 1.0

    def extract_rows(self, rec: ZarrImageRecord) -> pd.DataFrame:
        return pd.DataFrame({"metric": [self.metric_value], "source_image": [rec.image_id]})

    def params_hash(self, rec: ZarrImageRecord) -> str:
        return f"h:{rec.image_id}:{self.metric_value}"

    def analysis_version(self) -> str:
        return "v0.1"


@pytest.fixture
def tiny_ds(tmp_path: Path) -> ZarrDataset:
    pytest.importorskip("pyarrow")
    ds = ZarrDataset(str(tmp_path / "ds.zarr"), mode="a")
    for _ in range(3):
        ds.add_image((np.random.rand(8, 8) * 255).astype(np.uint8))
    return ds


def test_indexer_row_insertion(tiny_ds: ZarrDataset) -> None:
    kd = KymDataset(tiny_ds)
    kd.update_index(_SimpleIndexer(name="events"))

    df = tiny_ds.load_table("kym_events")
    assert len(df) == len(tiny_ds.list_image_ids())
    assert {"image_id", "analysis_version", "params_hash", "metric"}.issubset(df.columns)


def test_table_name_enforcement(tiny_ds: ZarrDataset) -> None:
    kd = KymDataset(tiny_ds)
    tiny_ds.save_table("external", pd.DataFrame({"x": [1]}))

    with pytest.raises(ValueError, match="reserved prefix"):
        kd.update_index(_SimpleIndexer(name="kym_bad"))

    with pytest.raises(ValueError, match="must match"):
        kd.update_index(_SimpleIndexer(name="bad/name"))

    # Ensure non-kym table is untouched by kym index updates.
    kd.update_index(_SimpleIndexer(name="ok"))
    external = tiny_ds.load_table("external")
    assert len(external) == 1
    assert list(external.columns) == ["x"]


def test_params_hash_written(tiny_ds: ZarrDataset) -> None:
    kd = KymDataset(tiny_ds)
    idx = _SimpleIndexer(name="hashes", metric_value=3.5)
    kd.update_index(idx)

    df = tiny_ds.load_table("kym_hashes")
    assert len(df) == len(tiny_ds.list_image_ids())

    by_id = {str(row["image_id"]): str(row["params_hash"]) for _, row in df.iterrows()}
    for image_id in tiny_ds.list_image_ids():
        assert by_id[image_id] == f"h:{image_id}:3.5"


def test_replace_rows_semantics(tiny_ds: ZarrDataset, caplog: pytest.LogCaptureFixture) -> None:
    kd = KymDataset(tiny_ds)
    idx = _SimpleIndexer(name="replace", metric_value=1.0)
    kd.update_index(idx)

    first = tiny_ds.load_table("kym_replace")
    assert len(first) == len(tiny_ds.list_image_ids())
    assert set(first["metric"].astype(float)) == {1.0}

    caplog.set_level("INFO")
    idx.metric_value = 2.0
    kd.update_index(idx)
    second = tiny_ds.load_table("kym_replace")
    assert len(second) == len(tiny_ds.list_image_ids())
    assert set(second["metric"].astype(float)) == {2.0}

    idx.metric_value = 2.0
    kd.update_index(idx, mode="incremental")
    msgs = [r.getMessage() for r in caplog.records]
    assert any("updated=0 skipped=3 missing=0" in m for m in msgs)
