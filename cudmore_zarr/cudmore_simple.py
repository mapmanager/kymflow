# filename: cudmore_simple.py
"""
Minimal exploration script for the core ZarrDataset / ZarrImageRecord API.

Goal:
1) Create/open a ZarrDataset (directory store).
2) Ingest one raw TIFF (pixels only).
3) Explore the record API and what metadata exists immediately after ingest.
4) Show how to create/load canonical metadata objects (AcqImgHeader + ExperimentMetadata).

Run:
    uv run python cudmore_simple.py

Notes on nomenclature:
- "An acqimage in a zarr dataset" is fine conversationally.
- In this codebase, the precise objects are:
    - ZarrDataset (dataset)
    - ZarrImageRecord (one image/record inside the dataset)
"""

from __future__ import annotations

from pathlib import Path

import tifffile

from kymflow_zarr import MetadataNotFoundError, ZarrDataset

import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def _print_record_storage_summary(ds: ZarrDataset, image_id: str) -> None:
    """Print basic Zarr storage facts for one record (no pixels loaded)."""
    rec = ds.record(image_id)

    print("\n=== Record storage summary ===")
    print("image_id:", rec.image_id)

    # Group attrs and axes
    axes = rec.get_axes()
    print("axes:", axes)

    # Bounds derived from stored axes + array shape
    b = rec.get_image_bounds()
    print("bounds:", b)

    # Zarr array (lazy)
    z = rec.open_array()
    print("zarr array shape:", z.shape)
    print("zarr array dtype:", z.dtype)
    print("zarr chunks:", z.chunks)

    # What analysis/artifact keys exist?
    keys = rec.list_analysis_keys()
    print("analysis keys:", keys if keys else "(none)")


def _try_print_metadata_objects(ds: ZarrDataset, image_id: str) -> None:
    """Try to load and print canonical metadata objects, if they exist."""
    rec = ds.record(image_id)
    print("\n=== Canonical metadata objects ===")

    try:
        header, experiment, rois = rec.load_metadata_objects()
    except MetadataNotFoundError as e:
        print("No canonical metadata payload yet (expected after raw TIFF ingest).")
        print("Reason:", e)
        return
    except ImportError as e:
        print("Cannot load metadata objects because kymflow isn't importable in this env.")
        print("Reason:", e)
        return

    print("\n-- AcqImgHeader --")
    print(header)

    print("\n-- ExperimentMetadata --")
    print(experiment)

    print("\n-- ROIs --")
    try:
        print("num ROIs:", rois.numRois())  # kymflow RoiSet method (if present)
    except AttributeError:
        try:
            print("num ROIs:", len(rois))
        except TypeError:
            print(rois)


def main() -> None:
    # Working directory is assumed to be:
    # /Users/cudmore/Sites/kymflow_outer/kymflow/cudmore_zarr
    work_dir = Path(__file__).resolve().parent

    # 1) Create/open dataset
    dataset_path = work_dir / "my_zarr.zarr"
    ds = ZarrDataset(str(dataset_path), mode="a")

    print(f'ds:{ds}')
    
    # 2) Load one TIFF and ingest
    tiff_path = (
        work_dir
        / "raw_data"
        / "14d Saline"
        / "20251014"
        / "20251014_A98_0002.tif"
    )
    if not tiff_path.exists():
        raise FileNotFoundError(f"TIFF not found: {tiff_path}")

    arr = tifffile.imread(str(tiff_path))
    rec = ds.add_image(arr)  # pixels + axes/chunks inferred and stored
    image_id = rec.image_id

    # Add a simple provenance blob (optional but useful for learning)
    # NOTE: This is NOT "experimental metadata" in your sense; it's just a record artifact.
    rec.save_json(
        "provenance",
        {
            "original_path": str(tiff_path),
            "file_size": tiff_path.stat().st_size,
            "mtime_ns": tiff_path.stat().st_mtime_ns,
        },
    )

    # Update dataset manifest/index
    ds.update_manifest()

    print("Dataset path:", dataset_path)
    print("Ingested image_id:", image_id)

    # 3) Explore the record API: what exists right now?
    _print_record_storage_summary(ds, image_id)

    # 4) Query header + experimental metadata.
    #
    # IMPORTANT: On *raw TIFF ingest*, we do NOT automatically create canonical metadata payload
    # unless you explicitly call save_metadata_objects(...) or save_metadata_payload(...).
    _try_print_metadata_objects(ds, image_id)

    # Now, explicitly create canonical metadata objects (header + empty experiment + empty rois)
    print("\n=== Creating canonical metadata objects (auto header from pixels) ===")
    rec2 = ds.record(image_id)
    rec2.save_metadata_objects(
        header=None,
        experiment=None,
        rois=None,
        auto_header_from_array=True,
        acquired_local_epoch_ns=None,
    )

    # Re-load and print them (now they should exist)
    _try_print_metadata_objects(ds, image_id)

    print("\nDone.")


if __name__ == "__main__":
    main()