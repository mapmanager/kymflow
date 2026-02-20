"""Import helpers for kymflow_zarr datasets."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

from pathlib import Path
import json
from typing import TYPE_CHECKING
from io import BytesIO

import pandas as pd
import numpy as np

if TYPE_CHECKING:
    from .dataset import ZarrDataset

from .utils import local_epoch_ns_now

SOURCES_COLUMNS = [
    "source_primary_path",
    "image_id",
    "source_mtime_ns",
    "source_size_bytes",
    "ingested_epoch_ns",
]


def _require_tifffile():
    try:
        import tifffile  # type: ignore
        return tifffile
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("Legacy ingest requires tifffile (uv pip install tifffile)") from e


def _artifact_name_for_sidecar(tif_path: Path, sidecar_path: Path) -> str | None:
    prefix = tif_path.stem + "."
    if not sidecar_path.name.startswith(prefix):
        return None
    body = sidecar_path.name[len(prefix):]
    if body.endswith(".json"):
        return body[: -len(".json")]
    if body.endswith(".csv.gz"):
        return body[: -len(".csv.gz")]
    if body.endswith(".csv"):
        return body[: -len(".csv")]
    if body.endswith(".parquet"):
        return body[: -len(".parquet")]
    if body.endswith(".npy"):
        return body[: -len(".npy")]
    return None


def _source_row_for_image(tif_path: Path, image_id: str) -> dict[str, int | str]:
    stat = tif_path.stat()
    mtime_ns = int(getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1_000_000_000)))
    size_bytes = int(stat.st_size)
    return {
        "source_primary_path": str(tif_path.resolve()),
        "image_id": str(image_id),
        "source_mtime_ns": mtime_ns,
        "source_size_bytes": size_bytes,
        "ingested_epoch_ns": int(local_epoch_ns_now()),
    }


def ingest_legacy_file(
    ds: "ZarrDataset",
    tif_path: str | Path,
    *,
    include_sidecars: bool = True,
) -> tuple[str, dict[str, int | str]]:
    """Ingest one legacy TIFF (+sidecars) and return (image_id, sources_row)."""
    tifffile = _require_tifffile()
    tif = Path(tif_path).resolve()
    arr = tifffile.imread(str(tif))
    rec = ds.add_image(arr)

    rec.save_json(
        "provenance",
        {
            "source_primary_path": str(tif),
            "source_name": tif.name,
            "ingest_mode": "legacy_folder_v0.1",
        },
    )

    if include_sidecars:
        # Exported-folder compatibility: metadata.json in the same folder.
        exported_md = tif.parent / "metadata.json"
        if exported_md.exists() and exported_md.is_file():
            payload = json.loads(exported_md.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                rec.save_metadata_payload(payload)

        for sidecar in sorted(tif.parent.glob(f"{tif.stem}.*")):
            if sidecar == tif or not sidecar.is_file():
                continue
            name = _artifact_name_for_sidecar(tif, sidecar)
            if not name:
                continue

            if sidecar.name.endswith(".json"):
                payload = json.loads(sidecar.read_text(encoding="utf-8"))
                if name == "metadata" and isinstance(payload, dict):
                    rec.save_metadata_payload(payload)
                else:
                    rec.save_json(name, payload)
            elif sidecar.name.endswith(".csv.gz") or sidecar.name.endswith(".csv"):
                df = pd.read_csv(sidecar)
                rec.save_df_parquet(name, df)
            elif sidecar.name.endswith(".parquet"):
                df = pd.read_parquet(sidecar)
                rec.save_df_parquet(name, df)
            elif sidecar.name.endswith(".npy"):
                arr = np.load(BytesIO(sidecar.read_bytes()), allow_pickle=False)
                rec.save_array_artifact(name, arr)

        # Exported-folder compatibility: array_artifacts/<name>.npy
        array_dir = tif.parent / "array_artifacts"
        if array_dir.exists() and array_dir.is_dir():
            for npy_path in sorted(array_dir.glob("*.npy")):
                name = npy_path.stem
                arr = np.load(BytesIO(npy_path.read_bytes()), allow_pickle=False)
                rec.save_array_artifact(name, arr)

    return rec.image_id, _source_row_for_image(tif, rec.image_id)


def ingest_legacy_folder(
    ds: "ZarrDataset",
    legacy_root: str | Path,
    *,
    pattern: str = "*.tif",
    include_sidecars: bool = True,
) -> list[tuple[str, dict[str, int | str]]]:
    """Ingest TIFF files (+optional sidecars) and return ingested rows."""
    root = Path(legacy_root).resolve()
    out: list[tuple[str, dict[str, int | str]]] = []
    for tif_path in sorted(root.rglob(pattern)):
        if not tif_path.is_file():
            continue
        out.append(ingest_legacy_file(ds, tif_path, include_sidecars=include_sidecars))
    return out
