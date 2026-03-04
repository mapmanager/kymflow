# ticket_030_motion_constraint_bool_enforcement.md

## Goal
Fix the “motion constraint bools ignored” issue: when the GUI toggles any of:
- `max_edge_shift_um_on`
- `max_diameter_change_um_on`
- `max_center_shift_um_on`

…the subsequent `Detect` run must respect those toggles (i.e., when `_on == False`, the corresponding constraint must not be applied).

This ticket is intentionally small and does **not** change the detection algorithm aside from honoring the existing toggles.

## Scope
- Work only inside `sandbox/diameter-analysis/`.
- Do not add backward-compat defaults/fallbacks.
- Prefer fail-fast errors if required fields/objects are missing.

## Background / current symptom
- GUI JSON for detection params reflects the toggles changing.
- The computed diameter still behaves as if constraints are enabled.

This strongly suggests the params object used for analysis differs from what the GUI edits (e.g., detect path clones/overwrites params, or uses defaults).

## Tasks

### 1) Trace parameter propagation in GUI detect path
Locate the code path for the Detect button (controller method) and verify:
- The exact `DiameterDetectionParams` instance used for analysis is the one stored in GUI state (or a direct copy that preserves all fields).
- No code path “rebuilds” params via `DiameterDetectionParams()` or `.from_dict()` without carrying over the `_on` fields.

If you find the detect path creating a new params object, refactor so that the toggles are preserved.

### 2) Add a minimal unit test that proves toggles are honored end-to-end
Create a test that:
- Constructs an analyzer with a small synthetic input where motion constraints would clearly clamp/alter results.
- Runs `analyze(...)` with the same numeric constraint values, but toggles set to `True` vs `False`.
- Asserts the outputs differ when toggles are `True` and match the “unconstrained” behavior when toggles are `False`.

If creating a “clearly clamped” dataset is too involved, an alternative acceptable test is:
- Monkeypatch/spyon the internal motion-gating function (e.g., `_apply_motion_constraints`) and assert it is **not called** when all `_on` toggles are `False`. (Pick the cleanest approach given current architecture.)

### 3) Add a controller-level test (if controller owns detect)
If the controller owns the detect call, add a test that:
- Sets controller.state.detection_params with toggles off.
- Triggers controller.detect().
- Asserts the analyzer receives params with toggles off (no mutation).

## Acceptance criteria
- Toggling any `_on` field in GUI materially affects the detect result as expected.
- New unit tests pass and fail on the pre-fix behavior.
- No new backward-compat defaults are introduced.
