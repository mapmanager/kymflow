"""Export helpers for kymflow_zarr datasets."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

from pathlib import Path
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .dataset import ZarrDataset


def _require_tifffile():
    try:
        import tifffile  # type: ignore
        return tifffile
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("TIFF export requires tifffile (uv pip install tifffile)") from e


def export_legacy_folder(
    ds: "ZarrDataset",
    export_dir: str | Path,
    *,
    include_tiff: bool = True,
    include_tables: bool = True,
) -> None:
    """Export dataset contents to a filesystem layout with TIFF/CSV/JSON files."""
    out_root = Path(export_dir).resolve()
    out_images = out_root / "images"
    out_tables = out_root / "tables"
    out_images.mkdir(parents=True, exist_ok=True)
    out_tables.mkdir(parents=True, exist_ok=True)

    tifffile = _require_tifffile() if include_tiff else None

    for rec in ds.iter_records(order_by="image_id"):
        rec_dir = out_images / rec.image_id
        rec_dir.mkdir(parents=True, exist_ok=True)

        if include_tiff and tifffile is not None:
            arr = rec.load_array()
            tifffile.imwrite(str(rec_dir / "image.tif"), arr)

        try:
            metadata = rec.load_metadata_payload()
        except FileNotFoundError:
            metadata = {}
        (rec_dir / "metadata.json").write_text(json.dumps(metadata, indent=2, default=str), encoding="utf-8")

        for key in rec.list_analysis_keys():
            fn = key.rsplit("/", 1)[-1]
            if fn in ("metadata.json", "metadata.json.gz"):
                continue
            if fn.endswith(".json"):
                name = fn[: -len(".json")]
                payload = rec.load_json(name)
                (rec_dir / f"{name}.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
            elif fn.endswith(".json.gz"):
                name = fn[: -len(".json.gz")]
                payload = rec.load_json(name)
                (rec_dir / f"{name}.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
            elif fn.endswith(".parquet"):
                name = fn[: -len(".parquet")]
                df = rec.load_df_parquet(name)
                df.to_csv(rec_dir / f"{name}.csv", index=False)
            elif fn.endswith(".csv.gz"):
                name = fn[: -len(".csv.gz")]
                df = rec.load_df_csv_gz(name)
                df.to_csv(rec_dir / f"{name}.csv", index=False)

    if include_tables:
        for table_name in ds.list_table_names():
            df = ds.load_table(table_name)
            df.to_csv(out_tables / f"{table_name}.csv", index=False)
