# Codex Ticket Bundle — 11–13 (Array artifacts foundation for masks/derived images)

Repo: `kymflow`  
Branch: `kymflow-zarr`

This bundle introduces a **generic array-artifact** concept in the acq core container so we can store:
- ROI masks
- distance maps
- watershed labels
- any derived image arrays

This is a **core primitive** (Layer 1), not kymflow-specific.

---

# Ticket 11 — Add record-level array artifact API

## Goal
Allow saving/loading named arrays under a record.

## Requirements
Implement on `ZarrImageRecord` (preferred) and/or `ZarrStore`:

### API
- `def save_array_artifact(self, name: str, arr: np.ndarray, *, axes: list[str] | None = None, chunks: tuple[int, ...] | None = None) -> None`
- `def load_array_artifact(self, name: str) -> np.ndarray`
- `def list_array_artifacts(self) -> list[str]`

### Storage layout
Under each record group:
- `images/<image_id>/analysis_arrays/<name>/...`  (choose exact zarr array/group layout)
Keep it consistent and discoverable.

### Axes/chunks inference
- Reuse the existing axis inference policy used for primary pixels (z,y,x,c,t,...).
- Allow override via params.

## Acceptance
- Unit tests: save/load roundtrip on toy array
- Does not interfere with existing `analysis/*` JSON/parquet artifacts

---

# Ticket 12 — Add MaskROI support using array artifacts (RectROI → mask artifact)

## Goal
Enable storing a rect-derived mask as a real array artifact and reference it from ROI JSON.

## Requirements
1) Implement a helper on the image/record:
- `def materialize_rect_roi_mask(self, roi_id: int, *, name: str | None = None) -> str`
Behavior:
- Generates boolean mask array for that ROI (same slice shape as `_get_slice_2d`)
- Saves via `save_array_artifact`
- Returns `mask_ref` string (path-like key) to store in ROI JSON

2) Update ROI schema guidance:
- MaskROI envelope uses:
  - `roi_type="mask"`
  - `data={"mask_ref": "<ref string>"}`

3) Update factory:
- `roi_from_dict` supports `"mask"` by returning a lightweight object that carries `mask_ref`.

## Tests
- Create RectROI
- materialize mask
- verify array artifact exists, loads back equal
- verify ROI JSON updated with mask_ref when requested

## Acceptance
- Tests pass
- No breaking changes to RectROI normal workflow

---

# Ticket 13 — Export/import support for array artifacts (minimal)

## Goal
Ensure legacy export/import includes array artifacts.

## Requirements
### Export
In `export_legacy_folder`:
- For each record, if array artifacts exist:
  - export each array artifact as:
    - `.tif` for 2D/3D if feasible, OR
    - `.npy` for arbitrary ndim (simpler and lossless), OR
    - both (optional)
Pick one and document.

Recommended v0.1: `.npy` export for array artifacts.

### Import
In `ingest_legacy_folder`:
- If sidecar has matching `.npy` artifacts, ingest them as array artifacts.

(Keep this minimal; do not overbuild naming heuristics.)

## Tests
- Save a small array artifact
- Export legacy folder
- Verify file exists on disk
- Import into new dataset
- Verify array artifact roundtrips

## Acceptance
- Tests pass
- Demos still run

---

# Notes
- Keep docstrings + types.
- Avoid broad exception swallowing.
