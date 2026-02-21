# Change Report: codex_ticket_11_13

## 1. Branch name used
- `kymflow-zarr`

## 2. Commands run and exact outcomes
- `uv run pytest src/kymflow/core/zarr/tests -q`
  - Passed.
  - Output: `.............................                                            [100%]`
- `uv run python src/kymflow/core/zarr/examples/demo_gui_flow_v01.py`
  - Passed.
  - Output included ROI pixel/stats lines and completed ingest + ordered iteration.
- `uv run python src/kymflow/core/zarr/examples/demo_export_import_v01.py`
  - Passed.
  - Output included sources refresh rows, export path, and ordered image IDs.

## 3. Files modified (full relative paths) with per-file details

### `src/kymflow/core/image_loaders/roi.py`
- What changed:
  - Added `MaskROI` dataclass with envelope `to_dict()/from_dict()` and `mask_ref`.
  - Updated `roi_from_dict(...)` to return `MaskROI` for `roi_type="mask"` instead of raising.
  - Updated supported-type error messaging accordingly.
- Why:
  - Ticket 12 requires mask ROI schema support and factory parsing.
- Behavior change vs refactor-only:
  - Behavior changed: `roi_type="mask"` payloads now parse into a lightweight object.

### `src/kymflow/core/zarr/src/kymflow_zarr/utils.py`
- What changed:
  - Added `PathParts` helpers for array artifacts:
    - `analysis_arrays_group`
    - `analysis_arrays_prefix`
    - `analysis_array_group(name)`
    - `analysis_array_data(name)`
- Why:
  - Ticket 11 requires consistent discoverable `analysis_arrays` layout.
- Behavior change vs refactor-only:
  - Refactor/infra helper addition; no direct runtime behavior by itself.

### `src/kymflow/core/zarr/src/kymflow_zarr/record.py`
- What changed:
  - Added array artifact APIs:
    - `save_array_artifact(name, arr, *, axes=None, chunks=None) -> None`
    - `load_array_artifact(name) -> np.ndarray`
    - `list_array_artifacts() -> list[str]`
  - New storage path: `images/<image_id>/analysis_arrays/<name>/data` (zarr array).
  - Axis inference reuses existing `_infer_axes` for ndim 2..5; falls back to `a0..aN` for other ndim.
  - Chunk inference uses existing `_infer_chunks`.
- Why:
  - Ticket 11 requires record-level array artifact primitive.
- Behavior change vs refactor-only:
  - Behavior changed: records can now persist/retrieve/list N-D array artifacts independently of `analysis/*` JSON/tabular blobs.

### `src/kymflow/core/zarr/src/kymflow_zarr/experimental_stores/acq_image.py`
- What changed:
  - Added `materialize_rect_roi_mask(self, roi_id: int, *, name: str | None = None) -> str`.
  - Method generates RectROI boolean mask, saves via artifact store `save_array_artifact`, returns `analysis_arrays/<name>` ref.
  - Method updates metadata payload ROI entry with mask reference (`meta.mask_ref` for rect ROI, `data.mask_ref` for mask ROI).
- Why:
  - Ticket 12 requires rect ROI mask materialization using array artifacts and JSON reference.
- Behavior change vs refactor-only:
  - Behavior changed: AcqImageV01 can now materialize and persist ROI mask arrays and annotate metadata payload.

### `src/kymflow/core/zarr/src/kymflow_zarr/experimental_stores/stores/base.py`
- What changed:
  - Extended `ArtifactStore` protocol with optional array artifact methods:
    - `save_array_artifact(...)`
    - `load_array_artifact(...)`
    - `list_array_artifacts(...)`
- Why:
  - Ticket 12/11 integration from AcqImageV01 through store abstraction.
- Behavior change vs refactor-only:
  - Public protocol surface changed.

### `src/kymflow/core/zarr/src/kymflow_zarr/experimental_stores/stores/zarr_store.py`
- What changed:
  - Implemented array artifact methods by delegating to `ZarrImageRecord`:
    - `save_array_artifact`
    - `load_array_artifact`
    - `list_array_artifacts`
- Why:
  - Required for AcqImageV01 mask materialization in zarr-backed mode.
- Behavior change vs refactor-only:
  - Behavior changed: zarr store now supports N-D artifact APIs.

### `src/kymflow/core/zarr/src/kymflow_zarr/experimental_stores/stores/sidecar.py`
- What changed:
  - Added sidecar array artifact support via `.npy` files:
    - `save_array_artifact`
    - `load_array_artifact`
    - `list_array_artifacts`
  - Sidecar naming convention: `<image>.<artifact_name>.npy`.
- Why:
  - Enables mask materialization for TIFF/sidecar-backed AcqImageV01.
- Behavior change vs refactor-only:
  - Behavior changed: sidecar store can now persist/load/list array artifacts.

### `src/kymflow/core/zarr/src/kymflow_zarr/io_export.py`
- What changed:
  - Added export of record array artifacts to:
    - `export_dir/images/<image_id>/array_artifacts/<name>.npy`
  - Uses `np.save(..., allow_pickle=False)`.
- Why:
  - Ticket 13 export requirement for array artifacts.
- Behavior change vs refactor-only:
  - Behavior changed: legacy export now emits `.npy` array artifact sidecars.

### `src/kymflow/core/zarr/src/kymflow_zarr/io_import.py`
- What changed:
  - Added `.npy` sidecar recognition for `<tif_stem>.<name>.npy`.
  - Added import of exported-folder array artifacts from `array_artifacts/*.npy`.
  - Added exported-folder compatibility for same-folder `metadata.json` next to `image.tif`.
  - Imported arrays saved via `rec.save_array_artifact(name, arr)`.
- Why:
  - Ticket 13 import requirement for array artifacts and export/import roundtrip.
- Behavior change vs refactor-only:
  - Behavior changed: ingest now imports N-D array artifacts and exported metadata layout.

### `src/kymflow/core/zarr/tests/test_record_api.py`
- What changed:
  - Added `test_array_artifact_roundtrip`.
- Why:
  - Ticket 11 acceptance requires save/load/list roundtrip test.
- Behavior change vs refactor-only:
  - Test-only change.

### `src/kymflow/core/zarr/tests/test_import_export_v01.py`
- What changed:
  - Added `test_array_artifact_export_import_roundtrip`.
- Why:
  - Ticket 13 acceptance requires export/import roundtrip for array artifacts.
- Behavior change vs refactor-only:
  - Test-only change.

### `src/kymflow/core/zarr/tests/test_roi_schema_and_pixels_v01.py`
- What changed:
  - Extended fake artifact store with array artifact methods.
  - Updated mask factory test to expect `MaskROI`.
  - Added `test_materialize_rect_roi_mask_updates_metadata_and_artifact`.
- Why:
  - Ticket 12 acceptance: materialization + metadata reference update.
- Behavior change vs refactor-only:
  - Test-only change.

## 4. Files added
- `src/kymflow/core/zarr/prompts/codex_ticket_11_13_change_report.md`

## 5. Files deleted
- None.

## 6. Public API changes (functions/methods/signatures)
- `kymflow_zarr.record.ZarrImageRecord`
  - `save_array_artifact(self, name: str, arr: np.ndarray, *, axes: list[str] | None = None, chunks: tuple[int, ...] | None = None) -> None`
  - `load_array_artifact(self, name: str) -> np.ndarray`
  - `list_array_artifacts(self) -> list[str]`
- `kymflow_zarr.experimental_stores.acq_image.AcqImageV01`
  - `materialize_rect_roi_mask(self, roi_id: int, *, name: str | None = None) -> str`
- `kymflow.core.image_loaders.roi`
  - Added `MaskROI` dataclass.
  - `roi_from_dict(...)` now supports `roi_type="mask"` by returning `MaskROI`.
- `kymflow_zarr.experimental_stores.stores.base.ArtifactStore` protocol
  - Added optional array artifact method signatures (`save/load/list`).
- `kymflow_zarr.experimental_stores.stores.zarr_store.ZarrStore`
  - Added array artifact method implementations.
- `kymflow_zarr.experimental_stores.stores.sidecar.SidecarArtifactStore`
  - Added array artifact method implementations.

## 7. Exception handling changes
- `AcqImageV01.materialize_rect_roi_mask(...)`
  - Raises `KeyError` when ROI id is missing.
  - Raises `NotImplementedError` when ROI is not rect-like or store lacks array artifact support.
- `ZarrImageRecord.load_array_artifact(...)`
  - Raises `FileNotFoundError` when artifact path is missing.
- `roi_from_dict(...)`
  - `mask` is now supported (no exception for valid mask payload).
  - `line/polygon` remain `NotImplementedError`.
  - unknown types remain `ValueError`.

## 8. Read/write semantics changes
- New write/read path for array artifacts:
  - Write: `images/<id>/analysis_arrays/<name>/data`
  - Read/list via record APIs.
- AcqImageV01 mask materialization now performs two writes:
  - writes boolean array artifact
  - updates and saves metadata payload with `mask_ref`.
- Legacy import/export now reads/writes `.npy` sidecars for array artifacts in addition to existing JSON/CSV/Parquet artifact handling.

## 9. Data layout changes
- Added per-record zarr array artifact subtree:
  - `images/<image_id>/analysis_arrays/<name>/data`
- Added legacy export folder artifact subtree:
  - `images/<image_id>/array_artifacts/<name>.npy`
- Added legacy ingest support for:
  - `<tif_stem>.<artifact>.npy`
  - `array_artifacts/*.npy` alongside `image.tif`
- ROI JSON schema support expanded:
  - `roi_type="mask"` with `data={"mask_ref": "<ref>"}` now parsed into `MaskROI`.

## 10. Known limitations / TODOs
- `MaskROI` is lightweight schema support only; ROI set editing/hit-testing/clamping logic remains RectROI-centric.
- `materialize_rect_roi_mask` currently stores `mask_ref` in RectROI `meta.mask_ref` rather than auto-creating a separate `roi_type="mask"` entry.
- Array artifact export format is `.npy` only (no `.tif` export for 2D/3D artifacts in this ticket).
- Ingest sidecar matching remains minimal; no advanced naming heuristics beyond explicit `.npy` patterns and exported `array_artifacts/` folder.
