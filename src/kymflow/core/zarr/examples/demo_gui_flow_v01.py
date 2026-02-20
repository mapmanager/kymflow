# Filename: examples/demo_gui_flow_v01.py
"""Demo: GUI-like workflow using AcqImageListV01 and ZarrDataset ingestion.

Flow:
  1) Build list from folder of TIFFs
  2) Select one TIFF, add/edit ROI via AcqImageV01
  3) Ingest into ZarrDataset with one call
  4) Reload dataset and iterate by acquired time (when available) or created time
  5) Open pixels + show ROIs + show header without manual ndim/shape code

Requirements:
  - tifffile (for TIFF pixels)
  - kymflow (for ROI/metadata object conveniences) [optional but recommended]
  - zarr<3, numcodecs
"""

from __future__ import annotations

from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)

from pathlib import Path
import numpy as np

from kymflow_zarr import ZarrDataset
from kymflow_zarr.experimental_stores import AcqImageListV01


def main() -> None:
    tif_folder = Path("/Users/cudmore/Dropbox/data/declan/2026/compare-condiitons/zarr-data")
    ds_path = Path("/Users/cudmore/Dropbox/data/declan/2026/compare-condiitons/zarr-data/zarr_dataset.zarr")

    src_list = AcqImageListV01(tif_folder)
    if len(src_list) == 0:
        raise RuntimeError(f"No TIFF files found under: {tif_folder}")

    src_img = next(iter(src_list))
    print("Selected TIFF:", src_img.source_key)

    # Load pixels
    print("Channels available:", src_img.channels_available())
    arr = src_img.getChannelData(1)
    print("Pixels:", arr.shape, arr.dtype)

    # ROI CRUD (requires kymflow installed)
    try:
        from kymflow.core.image_loaders.roi import RoiBounds
    except ImportError as e:
        print("ROI demo skipped (kymflow not available):", e)
    else:
        h, w = int(arr.shape[-2]), int(arr.shape[-1])
        dim0_start = max(0, min(10, h - 2))
        dim0_stop = min(h, dim0_start + max(5, min(40, h // 10)))
        dim1_start = max(0, min(2, w - 2))
        dim1_stop = min(w, dim1_start + max(2, min(20, w // 2)))
        rid = src_img.add_roi(
            RoiBounds(dim0_start, dim0_stop, dim1_start, dim1_stop),
            channel=1,
            z=0,
            name="roi1",
            note="",
        )
        src_img.edit_roi(rid, name="roi1_edited")
        src_img.save_metadata_objects(auto_header_from_pixels=True)
        print("ROI id:", rid)

    ds = ZarrDataset(str(ds_path), mode="a")
    rec = ds.ingest_image(src_img)
    print("Ingested image_id:", rec.image_id)

    ds.update_manifest()

    ds2 = ZarrDataset(str(ds_path), mode="r")
    # Prefer acquired time when present; else created time
    order = "acquired_local_epoch_ns"
    ids = []
    for r in ds2.iter_records(order_by=order):
        ids.append(r.image_id)
    print("Ordered ids:", ids)

    # Show first record metadata (if possible)
    r0 = ds2.record(ids[0])
    try:
        hdr, em, rois = r0.load_metadata_objects()
    except ImportError as e:
        print("Metadata objects unavailable (kymflow not available):", e)
    except FileNotFoundError as e:
        print("Metadata missing for record:", e)
    else:
        print("Header acquired ns:", getattr(hdr, "acquired_local_epoch_ns", None))
        print("Num ROIs:", rois.numRois())

if __name__ == "__main__":
    main()
