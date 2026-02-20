"""Import/export integration tests for v0.1 folder bridge."""

from __future__ import annotations

from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)

from pathlib import Path
import json

import numpy as np
import pandas as pd
import pytest

from kymflow_zarr import ZarrDataset


def _require_tifffile():
    return pytest.importorskip("tifffile")


def test_export_legacy_folder_writes_expected_outputs(tmp_path: Path) -> None:
    pytest.importorskip("pyarrow")
    _require_tifffile()

    ds = ZarrDataset(str(tmp_path / "ds.zarr"), mode="a")
    rec = ds.add_image((np.random.rand(8, 8) * 255).astype(np.uint8))
    rec.save_metadata_payload({"version": "2.0", "header": {"acquired_local_epoch_ns": 10}})
    rec.save_json("events", {"n": 2})
    rec.save_df_parquet("radon_report", pd.DataFrame({"roi_id": [1], "velocity": [0.5]}))
    ds.save_table("velocity_events", pd.DataFrame({"image_id": [rec.image_id], "event_id": ["e1"]}))

    export_dir = tmp_path / "export"
    ds.export_legacy_folder(export_dir)

    rec_dir = export_dir / "images" / rec.image_id
    assert (rec_dir / "image.tif").exists()
    assert (rec_dir / "metadata.json").exists()
    assert (rec_dir / "events.json").exists()
    assert (rec_dir / "radon_report.csv").exists()
    assert (export_dir / "tables" / "velocity_events.csv").exists()


def test_ingest_legacy_folder_imports_tiff_and_sidecars(tmp_path: Path) -> None:
    pytest.importorskip("pyarrow")
    tifffile = _require_tifffile()

    legacy = tmp_path / "legacy"
    legacy.mkdir(parents=True, exist_ok=True)

    tif_path = legacy / "sample.tif"
    tifffile.imwrite(str(tif_path), (np.random.rand(12, 12) * 255).astype(np.uint8))
    (legacy / "sample.metadata.json").write_text(
        json.dumps({"version": "2.0", "header": {"acquired_local_epoch_ns": 123}}),
        encoding="utf-8",
    )
    pd.DataFrame({"roi_id": [1], "velocity": [0.1]}).to_csv(legacy / "sample.radon_report.csv", index=False)

    ds = ZarrDataset(str(tmp_path / "ds.zarr"), mode="a")
    ds.ingest_legacy_folder(legacy)

    ids = ds.list_image_ids()
    assert len(ids) == 1
    rec = ds.record(ids[0])

    md = rec.load_metadata_payload()
    assert md["header"]["acquired_local_epoch_ns"] == 123
    rr = rec.load_df_parquet("radon_report")
    assert len(rr) == 1
    prov = rec.load_json("provenance")
    assert "source_primary_path" in prov

    sources = ds.load_sources_index()
    assert len(sources) == 1
