"""Dataset-level table API tests."""

from __future__ import annotations

from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)

from pathlib import Path

import pandas as pd
import pytest

from kymflow_zarr import ZarrDataset


def test_dataset_table_roundtrip(tmp_path: Path) -> None:
    pytest.importorskip("pyarrow")
    ds = ZarrDataset(str(tmp_path / "ds.zarr"), mode="a")
    df = pd.DataFrame({"image_id": ["a", "b"], "value": [1.0, 2.0]})
    ds.save_table("radon_report", df)

    out = ds.load_table("radon_report")
    pd.testing.assert_frame_equal(out, df)


def test_replace_rows_for_image_id(tmp_path: Path) -> None:
    pytest.importorskip("pyarrow")
    ds = ZarrDataset(str(tmp_path / "ds.zarr"), mode="a")
    base = pd.DataFrame({"image_id": ["a", "b"], "value": [1.0, 2.0]})
    ds.save_table("velocity_events", base)

    replacement = pd.DataFrame({"image_id": ["b", "b"], "value": [8.0, 9.0]})
    ds.replace_rows_for_image_id("velocity_events", "b", replacement)

    out = ds.load_table("velocity_events").sort_values(["image_id", "value"]).reset_index(drop=True)
    expected = pd.DataFrame({"image_id": ["a", "b", "b"], "value": [1.0, 8.0, 9.0]})
    pd.testing.assert_frame_equal(out, expected)
