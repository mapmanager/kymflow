# Codex Ticket Bundle — 07–10 (ROI v0.1 + ROI→pixels helpers)

Repo: `kymflow`  
Branch: `kymflow-zarr`  

This bundle focuses on **extensible ROI** in the *core acquisition container* (the “acq core” concept we’re building), and adds
a first-class API for extracting pixels and masks from a RectROI. It must remain **generic** (no kymflow domain analysis).

## Architectural boundary (critical)
- Core ROI + ROI→pixels lives in the **acq core layer** (currently inside `kymflow_zarr` + shared ROI code).
- No kymflow-specific analysis logic (radon/events/etc).
- Must preserve existing behavior for current Rect ROI workflows.

---

# Ticket 07 — Formalize ROI schema envelope + RectROI naming

## Goal
Make the current “roi” explicit as a **RectROI** and make ROI storage forward-compatible with future shapes.

## Requirements
1) Introduce schema envelope for each ROI item (JSON-serializable):
```json
{
  "roi_id": 6,
  "roi_type": "rect",
  "version": "1.0",
  "name": "roi1",
  "note": "",
  "channel": 1,
  "z": 0,
  "data": {"x0": 10, "x1": 50, "y0": 20, "y1": 60},
  "meta": {}
}
```

2) Keep backward compatibility when loading:
- If an existing dataset has legacy ROI dicts without `roi_type/version/data`, interpret them as RectROI and upgrade in memory.
- On save, always write the new envelope form.

3) Naming:
- Introduce `RectROI` dataclass (or equivalent) representing an axis-aligned rectangle.
- Optionally keep a temporary alias `ROI = RectROI` if needed for minimal disruption, but new code should prefer `RectROI`.

4) Add ROI registry/factory:
- `roi_from_dict(d: dict) -> BaseROI`
- `BaseROI.to_dict()` returns envelope format.

## Scope (likely files)
- `src/kymflow/core/image_loaders/roi.py` (your current ROI + RoiSet implementation)
- Any zarr metadata adapters that serialize/deserialize ROI payloads
- Tests that validate ROI roundtrip

## Acceptance
- Existing ROI JSON roundtrip still works, now with envelope schema on write
- `uv run pytest src/kymflow/core/zarr/tests -q` passes (and any core tests you touch)
- Demo scripts still run

---

# Ticket 08 — Add ROI→pixels and ROI→mask APIs (RectROI v0.1)

## Goal
Provide a generic API in the acq core to retrieve pixels and masks for a RectROI.

## Requirements

### 1) Add `get_roi_pixels`
Implement on the appropriate image wrapper class used by the acq core (one of):
- `AcqImageV01` (in `kymflow_zarr.experimental_stores`)
- or the existing `kymflow.core.image_loaders.acq_image.AcqImage` if that’s the right home

Method signature (choose one, typed):
- `def get_roi_pixels(self, roi_id: int) -> np.ndarray:`
- `def get_roi_pixels(self, roi: RectROI) -> np.ndarray:`

Behavior:
- Returns a **2D** array crop for the ROI’s `z` and `channel` (if applicable).
- Uses ROI bounds (x0,x1,y0,y1) with clamping already applied.
- For 2D images: ignore z, channel.
- For 3D (z,y,x): use ROI.z
- For 4D (z,y,x,c): use ROI.z and ROI.channel
- For 5D (t,z,y,x,c): **v0.1**: use t=0 by default (document), or require t selector (choose one, but keep simple).

### 2) Add `get_roi_mask`
Method signature:
- `def get_roi_mask(self, roi_id: int) -> np.ndarray:`

Behavior:
- Returns boolean mask aligned with the returned slice shape (same HxW).
- For RectROI, mask is a filled rectangle over the slice.

### 3) Centralize slice extraction
Add an internal helper that standardizes “return a 2D slice” from n-D pixels:
- `_get_slice_2d(z: int, channel: int, t: int = 0) -> np.ndarray`
- Must follow axis convention already established:
  - 3D: (z,y,x)
  - 4D: (z,y,x,c)
  - 5D: (t,z,y,x,c)

This helper should be used by `get_roi_pixels` and later supports Line/Polygon/Mask.

## Tests
Add tests (prefer under `src/kymflow/core/zarr/tests/` for now, since that’s your active test suite):
- Create a toy array with known values (e.g., z=2, y=10, x=12, c=3)
- Add a RectROI and verify:
  - crop shape correct
  - crop contents match expected slice subsection
  - mask shape matches slice
  - mask has correct True region

## Acceptance
- Tests pass
- `demo_gui_flow_v01.py` continues to run

---

# Ticket 09 — ROI “meta” field and forward schema hooks (no new shapes yet)

## Goal
Future-proof for Line/Polygon/Mask without implementing them fully.

## Requirements
- Ensure ROI envelope includes `meta: dict[str, Any]` (default `{}`).
- Add `roi_type` enum strings recognized by factory:
  - support `"rect"` now
  - allow `"line"`, `"polygon"`, `"mask"` to parse into placeholder objects OR raise a clear `NotImplementedError` with message.
- Document MaskROI storage convention (schema-only):
  - `"data": {"mask_ref": "analysis_arrays/rois/masks/<roi_id>"}` (path is a string reference; not implemented yet)

## Acceptance
- Loading a dataset with unknown roi_type gives actionable error
- RectROI path remains stable

---

# Ticket 10 — Minimal “ROI stats” helper (generic reductions only)

## Goal
Add a tiny, generic helper to reduce ROI pixels without introducing domain analysis.

## Requirements
Add one of:
- `def roi_stats(self, roi_id: int) -> dict[str, float]:`
  - returns mean, std, min, max, n
OR a smaller surface:
- `def roi_mean(self, roi_id: int) -> float`
- `def roi_count(self, roi_id: int) -> int`

Use `get_roi_pixels` + optional mask.

## Acceptance
- Tests for roi_stats on toy array
- No new domain logic

---

# Notes
- Keep typed signatures and Google-style docstrings.
- Avoid broad `except Exception`.
