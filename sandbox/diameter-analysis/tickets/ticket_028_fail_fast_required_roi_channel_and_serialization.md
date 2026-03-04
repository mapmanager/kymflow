# Ticket 028 — Fail-fast required ROI/channel + tighten result/serialization schema

## Goal
Now that diameter analysis **requires** explicit `(roi_id, roi_bounds, channel_id)` at run time, remove “back-compat / defensive defaults” that can silently mask broken pipeline state.

Concretely:
- ROI/channel become **required everywhere** (no `Optional[int]`, no default-to-1).
- Serialization/deserialization is **fail-fast** if required fields are missing.

## Background / Current issues
- Some serialization paths (e.g., `from_row`) may default `channel_id` when missing.
- Some result fields are typed optional even though the pipeline requires them.
- Helper `_resolve_roi(...)` currently supports `None`/defaults; this is defensive and can hide missing ROI bounds.

## Requirements

### A) Make ROI/channel required in results
In `diameter_analysis.py`:
1. Update `DiameterResult` to include required identifiers:
   - `roi_id: int`
   - `channel_id: int`
   - (Optional but recommended) `roi_bounds: tuple[int,int,int,int]` (the pixel bounds analyzed)
2. Ensure these are populated on construction for every result.

### B) Make analyze() require ROI/channel (no defaults)
In `DiameterAnalyzer.analyze(...)`:
- Require parameters (no `None` defaults):
  - `roi_id: int`
  - `roi_bounds: tuple[int,int,int,int]`
  - `channel_id: int`
- Remove dependence on `DiameterDetectionParams.roi` (ROI is not a detection parameter).

### C) Remove defensive defaults in serialization
In `DiameterResult.from_row(...)` and related helpers:
- Do **not** default missing `roi_id` or `channel_id`.
- If any required field is missing, raise a clear exception (ValueError) mentioning the missing key.
- Remove “backward compatibility” comments/branches unless explicitly justified in the ticket.

### D) Tighten `_resolve_roi` (or remove it)
- If `_resolve_roi` remains, it must:
  - accept **only** explicit `roi_bounds` (no `None`),
  - validate bounds against the image shape,
  - raise on invalid inputs.
- If you can simplify more: inline/rename to `_validate_roi_bounds(bounds, img_shape)`.

### E) Update call sites
- Update controller(s) and any call sites to pass explicit roi/channel.
- The GUI default remains `roi_id=1`, `channel_id=1`, but those are chosen at the app/controller layer, not inside analysis or serialization.

### F) Tests
Add/adjust pytest tests to enforce fail-fast behavior:
- Creating/serializing results without roi/channel must fail.
- `from_row` must raise if `roi_id` or `channel_id` is missing.
- `analyze(...)` must raise immediately if roi/channel not provided.

## Acceptance criteria
- No `Optional` typing for required fields (`roi_id`, `channel_id`) in `DiameterResult`.
- No defaulting `channel_id` (or `roi_id`) in any `from_*` deserialization.
- `DiameterAnalyzer.analyze(...)` signature requires `(roi_id, roi_bounds, channel_id)`.
- Unit tests cover the above and pass.

## Non-goals
- No algorithm behavior changes to edge detection.
- No UI refactors beyond required call-site updates.
