# ticket_026_detection_params_cleanup_and_generic_dataclass_editor_codex_report

## Final report path
- `kymflow/sandbox/diameter-analysis/tickets/ticket_026_detection_params_cleanup_and_generic_dataclass_editor_codex_report.md`

## A) Modified code files
- `kymflow/sandbox/diameter-analysis/gui/widgets.py`
- `kymflow/sandbox/diameter-analysis/diameter_analysis.py`
- `kymflow/sandbox/diameter-analysis/run_example.py`
- `kymflow/sandbox/diameter-analysis/tests/test_motion_constraints_qc.py`
- `kymflow/sandbox/diameter-analysis/tests/test_gradient_edges.py`
- `kymflow/sandbox/diameter-analysis/tests/test_post_filter_diameter.py`
- `kymflow/sandbox/diameter-analysis/tests/test_analysis_hardened.py`
- `kymflow/sandbox/diameter-analysis/tests/test_results_aligned_schema.py`
- `kymflow/sandbox/diameter-analysis/tests/test_detection_params_metadata.py`
- `kymflow/sandbox/diameter-analysis/tests/test_gui_dataclass_editor_smoke.py`

## B) Artifacts created
- `kymflow/sandbox/diameter-analysis/docs/detection_params.md` (updated doc artifact)
- `kymflow/sandbox/diameter-analysis/tickets/ticket_026_detection_params_cleanup_and_generic_dataclass_editor_codex_report.md`

## C) Unified diff (short)
### `gui/widgets.py`
```diff
-        motion_fields = {"max_edge_shift_um", "max_diameter_change_um", "max_center_shift_um"}
-        motion_controls: list[Any] = []
-        def _set_motion_controls_enabled(...): ...
...
-                if isinstance(value, bool) or tp is bool:
-                    if name == "enable_motion_constraints": ...
+                if isinstance(value, bool) or tp is bool:
+                    w = ui.switch(value=bool(value))
+                    w.on("update:model-value", lambda e, n=name: on_change(n, bool(_select_value(e.args))))
...
-                if name in motion_fields: ...
+                # no detection-specific control wiring
```

### `diameter_analysis.py`
```diff
 class DiameterDetectionParams:
-    roi: tuple[int, int, int, int] | None = ...
-    enable_motion_constraints: bool = ...
+    max_edge_shift_um_on: bool = field(default=True, ...)
+    max_diameter_change_um_on: bool = field(default=True, ...)
+    max_center_shift_um_on: bool = field(default=True, ...)
@@
-        if obj.roi is not None and len(obj.roi) != 4: ...
+        return dataclass_from_dict(cls, payload)
@@
-        t0, t1, x0, x1 = self._resolve_roi(cfg.roi)
+        t0, t1, x0, x1 = self._resolve_roi(None)
@@
-        if cfg.diameter_method == GRADIENT_EDGES and cfg.enable_motion_constraints:
+        if cfg.diameter_method == GRADIENT_EDGES and (cfg.max_edge_shift_um_on or cfg.max_diameter_change_um_on or cfg.max_center_shift_um_on):
             self._apply_motion_constraints(...)
@@
-            if np.isfinite(cur_left) and np.isfinite(prev_left):
+            if params.max_edge_shift_um_on and np.isfinite(cur_left) and np.isfinite(prev_left):
                 ...
-            if np.isfinite(cur_d) and np.isfinite(prev_d):
+            if params.max_diameter_change_um_on and np.isfinite(cur_d) and np.isfinite(prev_d):
                 ...
-            if np.isfinite(cur_c) and np.isfinite(prev_c):
+            if params.max_center_shift_um_on and np.isfinite(cur_c) and np.isfinite(prev_c):
                 ...
```

### `run_example.py`
```diff
-        roi=(0, int(payload["kymograph"].shape[0]), 0, int(payload["kymograph"].shape[1])),
```

### Tests
```diff
- use roi=... in DiameterDetectionParams(...)
+ remove roi kwargs and adjust expected centers to full-frame behavior

- enable_motion_constraints=True/False
+ max_edge_shift_um_on / max_diameter_change_um_on / max_center_shift_um_on

+ add test_only_enabled_constraint_toggle_applies()
+ add generic-widget guard test asserting no "enable_motion_constraints" or "motion_fields" in dataclass_editor_card source
+ add tests asserting `.roi`/`.enable_motion_constraints` removed and new `_on` booleans default True
```

### `docs/detection_params.md`
```diff
- include `roi` and `enable_motion_constraints`
+ remove `roi` and add `max_edge_shift_um_on`, `max_diameter_change_um_on`, `max_center_shift_um_on`
+ update tuning cookbook guidance accordingly
```

## D) Search confirmation
Searched patterns:
- `enable_motion_constraints`
- `motion_fields`
- `roi=(`
- `max_edge_shift_um_on|max_diameter_change_um_on|max_center_shift_um_on`

Outcomes:
- `gui/widgets.py` no longer contains detection-specific `motion_fields`/`enable_motion_constraints` logic.
- `DiameterDetectionParams` no longer has `roi` or `enable_motion_constraints`.
- Tests and docs updated to new toggle fields.
- Remaining `enable_motion_constraints`/`roi=` references are only in historical ticket markdown files or assertion text in tests validating removals.

## E) Validation commands run
From `kymflow/sandbox/diameter-analysis/`:

1. `uv run pytest`
- Result: PASS (`65 passed, 1 warning`).

## F) Summary of changes
- Made `dataclass_editor_card` generic by removing all DetectionParams-specific enable/disable wiring.
- Removed `roi` from `DiameterDetectionParams`.
- Replaced global `enable_motion_constraints` with per-constraint booleans:
  - `max_edge_shift_um_on`
  - `max_diameter_change_um_on`
  - `max_center_shift_um_on`
- Updated motion-constraint application logic to gate each constraint independently by its toggle.
- Updated docs, example script, and tests to match the refactor.

## G) Risks / tradeoffs
- Removing `roi` from params changes external config shape; callers passing `roi=` now fail until updated.
- Analyzer now always resolves full-image ROI internally (`_resolve_roi(None)`), matching ticket scope but removing prior per-call ROI clipping behavior.
- Per-constraint toggles improve granularity but require explicit understanding of three booleans instead of one global switch.

## H) Self-critique
- Pros:
  - Strictly removed detection-specific GUI logic from the generic editor.
  - Refactor is well-covered by tests and keeps algorithm math unchanged beyond requested gating controls.
  - All validations pass.
- Cons:
  - `run_example.py` was updated for compatibility but could use a short comment about ROI now being external/runtime.
- Drift risk:
  - Future docs/tests must stay synchronized with `DiameterDetectionParams` field changes.
- What I’d do next:
  - Add a dedicated runtime ROI selection object/path separate from detection params (future ticket).

## Assumptions
- Interpreting “no ROI in DetectionParams” as full-image analysis by default in `analyze()` is acceptable for this ticket.
- Keeping `_resolve_roi` helper intact (unused with non-None input in current path) is acceptable and non-disruptive.

## Required confirmation
No files outside `kymflow/sandbox/diameter-analysis/` were modified.
