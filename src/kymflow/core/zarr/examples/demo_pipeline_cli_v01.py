"""CLI demo: folder -> ingest -> manifest -> kym tables -> optional export.

Run:
    uv run python src/kymflow/core/zarr/examples/demo_pipeline_cli_v01.py \
      --input /path/to/tiffs \
      --dataset /path/to/dataset.zarr
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from kymflow.core.kym_dataset import KymDataset, RadonIndexer, VelocityEventIndexer
from kymflow_zarr import ZarrDataset


def _require_tifffile() -> Any:
    try:
        import tifffile  # type: ignore
        return tifffile
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("This demo requires tifffile") from e


def _fingerprint(path: Path) -> tuple[str, int, int]:
    st = path.stat()
    mtime_ns = int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1_000_000_000)))
    return str(path.resolve()), int(st.st_size), mtime_ns


def _existing_fingerprints(ds: ZarrDataset) -> set[tuple[str, int, int]]:
    out: set[tuple[str, int, int]] = set()
    for rec in ds.iter_records(order_by="image_id"):
        try:
            prov = rec.load_json("provenance")
        except KeyError:
            continue
        if not isinstance(prov, dict):
            continue
        path = prov.get("original_path")
        size = prov.get("file_size")
        mtime = prov.get("mtime_ns")
        if isinstance(path, str) and isinstance(size, int) and isinstance(mtime, int):
            out.add((path, size, mtime))
    return out


def _ingest_folder(ds: ZarrDataset, folder: Path, *, ingest_new_only: bool) -> tuple[int, int]:
    tifffile = _require_tifffile()
    existing = _existing_fingerprints(ds) if ingest_new_only else set()

    scanned = 0
    ingested = 0
    for tif in sorted(folder.rglob("*.tif")):
        if not tif.is_file():
            continue
        scanned += 1
        fp = _fingerprint(tif)
        if ingest_new_only and fp in existing:
            continue

        arr = tifffile.imread(str(tif))
        rec = ds.add_image(arr)
        rec.save_json(
            "provenance",
            {
                "original_path": fp[0],
                "file_size": fp[1],
                "mtime_ns": fp[2],
                "ingest_mode": "pipeline_cli_v01",
            },
        )
        existing.add(fp)
        ingested += 1
    return scanned, ingested


def _run_indexers(ds: ZarrDataset, names_csv: str) -> list[str]:
    requested = [x.strip().lower() for x in names_csv.split(",") if x.strip()]
    indexers = {
        "velocity_event": VelocityEventIndexer(),
        "velocity_events": VelocityEventIndexer(),
        "radon": RadonIndexer(),
    }
    if not requested:
        requested = ["velocity_events", "radon"]

    kd = KymDataset(ds)
    ran: list[str] = []
    for name in requested:
        idx = indexers.get(name)
        if idx is None:
            continue
        kd.update_index(idx, mode="incremental")
        ran.append(str(idx.name))
        print(f"indexer={idx.name} stats={kd.last_update_stats}")
    return ran


def main() -> None:
    parser = argparse.ArgumentParser(description="Pipeline CLI demo")
    parser.add_argument("--input", required=True, type=str, help="Input folder with TIFF files")
    parser.add_argument("--dataset", required=True, type=str, help="Path to dataset.zarr")
    parser.add_argument("--ingest-new-only", dest="ingest_new_only", action="store_true", default=True)
    parser.add_argument("--ingest-all", dest="ingest_new_only", action="store_false")
    parser.add_argument("--run-indexers", type=str, default="velocity_events,radon")
    parser.add_argument("--export-legacy", type=str, default="")
    args = parser.parse_args()

    input_dir = Path(args.input).resolve()
    if not input_dir.exists() or not input_dir.is_dir():
        raise FileNotFoundError(f"Input folder not found: {input_dir}")

    ds = ZarrDataset(str(Path(args.dataset).resolve()), mode="a")
    scanned, ingested = _ingest_folder(ds, input_dir, ingest_new_only=bool(args.ingest_new_only))
    print(f"scanned={scanned} ingested={ingested}")

    manifest = ds.update_manifest()
    print(f"manifest_images={len(manifest.images)}")

    ran = _run_indexers(ds, args.run_indexers)
    print(f"indexers_ran={ran}")

    if args.export_legacy:
        export_dir = Path(args.export_legacy).resolve()
        ds.export_legacy_folder(export_dir)
        print(f"exported_legacy={export_dir}")


if __name__ == "__main__":
    main()
