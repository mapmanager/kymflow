# Change Report: codex_ticket_07_10

## 1) Branch name used
- `kymflow-zarr`

## 2) Commands run and exact outcomes
- `uv run pytest src/kymflow/core/zarr/tests -q`
  - Outcome: passed
  - Output: `..........................                                               [100%]`
- `uv run python src/kymflow/core/zarr/examples/demo_gui_flow_v01.py`
  - Outcome: passed
  - Output included:
    - `Selected TIFF: /Users/cudmore/Dropbox/data/declan/2026/compare-condiitons/zarr-data/14d Saline/20251014/20251014_A98_0002.tif`
    - `Channels available: [1]`
    - `Pixels: (30000, 20) uint16`
    - `ROI id: 8`
    - `ROI pixels: (40, 10)`
    - `ROI stats: {'mean': 379.69, 'std': 122.57095455286296, 'min': 142.0, 'max': 831.0, 'n': 400.0}`
    - `Ingested image_id: 4c78ca3f-7178-45f8-a97a-cd4596c39c2e`
    - `Ordered ids: [...]`
    - `Header acquired ns: None`
    - `Num ROIs: 3`

## 3) Files modified (full relative paths) with per-file details

### `src/kymflow/core/image_loaders/roi.py`
- What changed:
  - Added `BaseROI` dataclass and `RectROI` dataclass.
  - Added `roi_from_dict(data: dict[str, Any]) -> BaseROI` factory.
  - Added compatibility alias `ROI = RectROI`.
  - Replaced legacy flattened ROI serialization with envelope serialization in `RectROI.to_dict()`:
    - writes keys: `roi_id`, `roi_type`, `version`, `name`, `note`, `channel`, `z`, `data`, `meta`.
  - Extended `RectROI.from_dict()` to parse both envelope and legacy flattened dicts.
  - Updated `RoiSet.from_list()` to call `roi_from_dict(...)` and reject non-rect ROI objects with `NotImplementedError`.
- Why:
  - Ticket 07/09 required explicit rect ROI schema envelope, backward-compatible loading, and forward-compatible ROI type factory.
- Behavior change vs refactor-only:
  - **Behavior changed**:
    - ROI payloads written to metadata are now envelope format (not flattened coordinates).
    - Legacy payloads still load, then re-serialize in new envelope format.
    - Unknown `roi_type` now raises actionable `ValueError`; reserved `line/polygon/mask` raise `NotImplementedError`.
    - `mask` error message includes schema convention: `{"mask_ref": "analysis_arrays/rois/masks/<roi_id>"}`.

### `src/kymflow/core/zarr/src/kymflow_zarr/experimental_stores/acq_image.py`
- What changed:
  - Switched logger wiring to `get_logger(__name__)`.
  - Added `_get_slice_2d(self, z: int, channel: int, t: int = 0) -> np.ndarray`.
  - Added `get_roi_pixels(self, roi_id: int) -> np.ndarray`.
  - Added `get_roi_mask(self, roi_id: int) -> np.ndarray`.
  - Added `roi_stats(self, roi_id: int) -> dict[str, float]`.
- Why:
  - Ticket 08/10 required generic ROI-to-pixels and ROI reduction APIs in acq core without domain analysis.
- Behavior change vs refactor-only:
  - **Behavior changed**:
    - New public methods expose ROI crop/mask/stats functionality.
    - 2D slice extraction is now standardized across 2D/3D/4D/5D arrays.
    - 5D behavior defaults to `t=0` in v0.1.
    - Missing ROI id now raises `KeyError`; non-rect ROI object raises `NotImplementedError`.

### `src/kymflow/core/zarr/examples/demo_gui_flow_v01.py`
- What changed:
  - Added calls to `get_roi_pixels(rid)` and `roi_stats(rid)` and printed both outputs.
- Why:
  - Ticket acceptance required demo continuity while exercising new ROI API.
- Behavior change vs refactor-only:
  - **Behavior changed** (demo output only): script now prints ROI crop shape + stats.

## 4) Files added
- `src/kymflow/core/zarr/tests/test_roi_schema_and_pixels_v01.py`
  - New tests for:
    - ROI envelope roundtrip write format
    - legacy flattened ROI upgrade path
    - `roi_from_dict` unknown/reserved type errors
    - `get_roi_pixels`, `get_roi_mask`, `roi_stats` correctness for 4D
    - 5D default `t=0` extraction behavior

## 5) Files deleted
- None.

## 6) Public API changes (functions/methods/signatures)

### Module `kymflow.core.image_loaders.roi`
- Added:
  - `class BaseROI`
  - `class RectROI(BaseROI)`
  - `def roi_from_dict(data: dict[str, Any]) -> BaseROI`
  - alias `ROI = RectROI`
- Existing API behavior changed:
  - `RectROI.to_dict()` now returns envelope schema (not legacy flattened structure).
  - `RectROI.from_dict()` now accepts envelope and legacy formats.

### Class `AcqImageV01` (`kymflow_zarr.experimental_stores.acq_image`)
- Added:
  - `_get_slice_2d(self, z: int, channel: int, t: int = 0) -> np.ndarray`
  - `get_roi_pixels(self, roi_id: int) -> np.ndarray`
  - `get_roi_mask(self, roi_id: int) -> np.ndarray`
  - `roi_stats(self, roi_id: int) -> dict[str, float]`

## 7) Exception handling changes
- `roi_from_dict(...)`:
  - unknown type: `ValueError("Unknown roi_type ...")`
  - reserved/unimplemented (`line`, `polygon`, `mask`): `NotImplementedError(...)`
- `RectROI.from_dict(...)`:
  - non-rect `roi_type`: `NotImplementedError(...)`
- `RoiSet.from_list(...)`:
  - non-`RectROI` object from factory: `NotImplementedError(...)`
- `AcqImageV01.get_roi_pixels(...)`:
  - missing roi id: `KeyError`
  - non-rect ROI object: `NotImplementedError`
- `AcqImageV01._get_slice_2d(...)`:
  - unsupported ndim / invalid indices / invalid axes: `ValueError`

## 8) Read/write semantics changes
- ROI metadata write path changed:
  - `RoiSet.to_list()` now writes envelope ROI objects through `RectROI.to_dict()`.
  - legacy ROI payloads are read and upgraded in-memory; subsequent save writes envelope format.
- No storage-layer file path write semantics were changed (no modifications in `record.py`, `dataset.py`, or stores layout code in this ticket).

## 9) Data layout changes
- Changed logical schema for metadata payload field `rois`:
  - Before: per-ROI flattened dict with keys like `dim0_start`, `dim0_stop`, `dim1_start`, `dim1_stop`, etc.
  - Now: envelope format:
    - `roi_id`, `roi_type`, `version`, `name`, `note`, `channel`, `z`
    - `data`: `{x0, x1, y0, y1}`
    - `meta`: dict (includes optional `revision`, `img_*` stats when present)
- Backward compatibility:
  - legacy flattened ROI dicts still parse via `RectROI.from_dict(...)`.

## 10) Known limitations / TODOs
- `RoiSet` remains RectROI-only; `line`, `polygon`, and `mask` are schema-recognized but not implemented.
- `mask` ROI is schema-only; no mask artifact loading implemented.
- `get_roi_mask(...)` currently returns an all-`True` mask over the ROI crop shape for RectROI.
- `AcqImageV01._get_slice_2d(...)` defaults 5D `t` to `0`; no caller-facing `t` selector is exposed yet in public ROI methods.
