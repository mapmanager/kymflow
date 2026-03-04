# Ticket 027 — Require ROI + Channel for DiameterAnalyzer.analyze (no defaults)

## Context
We want diameter analysis to run **only** on a *specific* `(roi_id, channel_id)` for real kymographs. ROI selection is *not* a detection parameter; it is chosen at the app/workflow level (currently: default `roi_id=1`, `channel_id=1`).

Current source of truth from uploads shows `DiameterAnalyzer.analyze()` still resolves ROI from `cfg.roi` (a field on `DiameterDetectionParams`). Meanwhile, `docs/detection_params.md` describes motion-constraint toggles and does **not** describe a `roi` field. This indicates the ROI responsibility is in flux and must be made explicit and consistent.

This ticket finalizes the contract:
- `DiameterDetectionParams` = **how** detection works.
- `DiameterAnalyzer.analyze(..., roi_id, roi_bounds, channel_id)` = **what region/channel** to analyze.

## Goals
1. **Make ROI + channel required inputs** to `DiameterAnalyzer.analyze()` (no `None` defaults).
2. **Remove ROI from `DiameterDetectionParams`** (and any `cfg.roi` usage).
3. Ensure results/serialization remain **roi-aware** (record `roi_id` and `channel_id` for each run).

## Scope
### A) Update analysis API
**File:** `diameter_analysis.py`

1) Update `DiameterAnalyzer.analyze()` signature to require:
- `roi_id: int`
- `roi_bounds: tuple[int, int, int, int]` (half-open `(t0, t1, x0, x1)` in pixel indices)
- `channel_id: int`

Example:
```python
def analyze(
    self,
    params: Optional[DiameterDetectionParams] = None,
    *,
    roi_id: int,
    roi_bounds: tuple[int, int, int, int],
    channel_id: int,
    backend: str = "serial",
    post_filter_params: Optional[PostFilterParams] = None,
) -> list[DiameterResult]:
    ...
```

2) Remove `roi` field from `DiameterDetectionParams` and remove any `cfg.roi` / `_resolve_roi(cfg.roi)` usage.

3) Replace ROI resolution with the required `roi_bounds`:
- Use `t0, t1, x0, x1 = roi_bounds`.
- Validate bounds against `self.img.shape` (or `self._kym_img` channel array shape) similarly to current `_resolve_roi()`.
- Keep ROI convention **half-open**.

4) Use `channel_id` when loading real data:
- If analysis currently uses a preloaded `self.img`/`self._img` array, ensure the array corresponds to the requested `channel_id`.
- If the analyzer loads channel data inside `analyze`, it must use `channel_id` (and not assume 1).

### B) Make results ROI/channel aware
**File:** `diameter_analysis.py`

1) Ensure `DiameterResult` (or the new aligned-array result structure, if already introduced by ticket 022) records:
- `roi_id`
- `channel_id`

If the project is transitioning to an aligned-array result object, store these once at the *result level* (not repeated per-sample), but ensure the per-row CSV export still includes `roi_id` and `channel_id` columns.

2) Update `to_row()/from_row()` (or schema export) to include these identifiers.

### C) Update docs to match the new contract
**File:** `docs/detection_params.md`

Add a short section:
- Detection params do **not** include ROI.
- ROI + channel are selected by the app/workflow (currently default `roi_id=1`, `channel_id=1` for real data).

### D) Update GUI/controller call sites
**Files likely:** `gui/controllers.py` and any place calling `.analyze()`.

1) The controller should provide:
- `roi_id = 1`
- `channel_id = 1`
- `roi_bounds` from kymflow facade:
  - Use adapter/controller path: `get_roi_pixel_bounds_for(selected_kym_image, roi_id)`
  - Convert `RoiPixelBounds` to tuple `(row_start, row_stop, col_start, col_stop)`.

2) If a selected kym does not have `roi_id=1` or `channel_id=1`, fail fast with a clear UI notification.

### E) Tests
1) Add/extend unit tests for:
- `DiameterAnalyzer.analyze()` rejects missing/invalid bounds.
- ROI/channel fields propagate into results serialization.

2) Update any existing tests that relied on `params.roi`.

## Acceptance
- `uv run pytest` passes.
- `uv run python run_gui.py` works.
- Real-data detect path uses `roi_id=1`, `channel_id=1` and fails with a clear message if missing.
- No remaining references to `DiameterDetectionParams.roi`.

## Guardrails
- Do not modify anything under `kymflow/`.
- No algorithm behavior changes besides enforcing required ROI/channel inputs and routing channel selection correctly.
