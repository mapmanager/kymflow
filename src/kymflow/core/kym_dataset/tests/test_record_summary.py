"""Tests for record_summary helpers."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from kymflow.core.kym_dataset.record_summary import summarize_record
from kymflow_zarr import ZarrDataset


def test_summarize_record_minimal_metadata(tmp_path: Path) -> None:
    ds = ZarrDataset(str(tmp_path / "ds.zarr"), mode="a")
    rec = ds.add_image((np.random.rand(6, 7) * 255).astype(np.uint8))
    rec.save_json("provenance", {"original_path": "/tmp/a.tif"})
    rec.save_metadata_payload({"version": "2.0", "header": {"acquired_local_epoch_ns": 99}})

    summary = summarize_record(rec)
    assert summary.image_id == rec.image_id
    assert summary.original_path == "/tmp/a.tif"
    assert summary.acquired_local_epoch_ns == 99
    assert summary.shape == (6, 7)
    assert summary.dtype == "uint8"
    assert summary.axes == ("y", "x")
    assert summary.has_metadata is True
    assert summary.has_header is True
    assert summary.has_rois is False
    assert summary.n_rois is None


def test_summarize_record_missing_metadata(tmp_path: Path) -> None:
    ds = ZarrDataset(str(tmp_path / "ds.zarr"), mode="a")
    rec = ds.add_image((np.random.rand(4, 5) * 255).astype(np.uint8))

    summary = summarize_record(rec)
    assert summary.image_id == rec.image_id
    assert summary.has_metadata is False
    assert summary.has_header is False
    assert summary.has_rois is False
    assert summary.n_rois is None


def test_summarize_record_counts_roi_list(tmp_path: Path) -> None:
    ds = ZarrDataset(str(tmp_path / "ds.zarr"), mode="a")
    rec = ds.add_image((np.random.rand(5, 6) * 255).astype(np.uint8))
    rec.save_metadata_payload(
        {
            "version": "2.0",
            "rois": [
                {"roi_id": 1, "name": "a"},
                {"roi_id": 2, "name": "b"},
            ],
            "experiment_metadata": {"notes": "hello"},
        }
    )

    summary = summarize_record(rec)
    assert summary.has_metadata is True
    assert summary.has_rois is True
    assert summary.n_rois == 2
    assert summary.notes == "hello"
