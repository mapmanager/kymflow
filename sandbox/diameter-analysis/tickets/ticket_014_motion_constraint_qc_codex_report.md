# Codex Report: ticket_014_motion_constraint_qc.md

Final report path written: `kymflow/sandbox/diameter-analysis/tickets/ticket_014_motion_constraint_qc_codex_report.md`

## A) Modified code files
- `kymflow/sandbox/diameter-analysis/diameter_analysis.py`
- `kymflow/sandbox/diameter-analysis/gui/widgets.py`
- `kymflow/sandbox/diameter-analysis/gui/views.py`
- `kymflow/sandbox/diameter-analysis/tests/test_motion_constraints_qc.py` (new)
- `kymflow/sandbox/diameter-analysis/tests/test_gradient_edges.py`

## B) Artifacts created
- `kymflow/sandbox/diameter-analysis/tickets/ticket_014_motion_constraint_qc_codex_report.md` (this report)

## C) Unified diff (short)
```diff
diff --git a/diameter_analysis.py b/diameter_analysis.py
@@ class DiameterDetectionParams:
+    enable_motion_constraints: bool = True
+    max_edge_shift_um: float = 2.0
+    max_diameter_change_um: float = 2.0
+    max_center_shift_um: float = 2.0
@@
+    # TODO(ticket_014): add stable DetectionParams.to_dict()/from_dict() schema contract.
@@ class DiameterResult:
+    qc_edge_violation: bool = False
+    qc_diameter_violation: bool = False
+    qc_center_violation: bool = False
@@
+    # TODO(ticket_014): add stable DetectionResults.to_dict()/from_dict() schema contract.
@@ def analyze(...):
+        if cfg.diameter_method == DiameterMethod.GRADIENT_EDGES and cfg.enable_motion_constraints:
+            self._apply_motion_constraints(results=results, params=cfg)
+        self.last_motion_qc = self.motion_qc_arrays(results)
@@
+    def _apply_motion_constraints(...):
+        ... edge/diameter/center thresholds in um, violations set NaN + QC flags ...
```

```diff
diff --git a/gui/widgets.py b/gui/widgets.py
@@
+        motion_fields = {"max_edge_shift_um", "max_diameter_change_um", "max_center_shift_um"}
+        motion_controls: list[Any] = []
+        ...
+        if name == "enable_motion_constraints":
+            ... toggle disable/enable for motion numeric inputs ...
```

```diff
diff --git a/gui/views.py b/gui/views.py
@@ Detection Params block
+                    def _reset_detection_params() -> None:
+                        from diameter_analysis import DiameterDetectionParams
+                        controller.state.detection_params = DiameterDetectionParams()
+                        controller._emit()
+                        ui.notify("Detection Params reset to defaults", type="positive", timeout=1500)
+                        ui.navigate.reload()
+
+                    ui.button("Reset to Defaults", on_click=_reset_detection_params).props("outline")
```

```diff
diff --git a/tests/test_motion_constraints_qc.py b/tests/test_motion_constraints_qc.py
new file mode 100644
@@
+def test_gradient_motion_constraints_produce_nans_and_qc_flags() -> None: ...
+
+def test_motion_constraints_off_matches_baseline_behavior() -> None: ...
```

```diff
diff --git a/tests/test_gradient_edges.py b/tests/test_gradient_edges.py
@@
+        enable_motion_constraints=False,
```

## D) Search confirmation
- Motion/QC fields and TODO scaffolding search:
  - `enable_motion_constraints|max_edge_shift_um|max_diameter_change_um|max_center_shift_um|motion_qc_arrays|qc_edge_violation|qc_diameter_violation|qc_center_violation|TODO(ticket_014)|Reset to Defaults`
  - Result: all required additions are present in `diameter_analysis.py`, `gui/widgets.py`, and `gui/views.py`.
- File picker change guard:
  - `git diff --name-only -- gui/file_picker.py`
  - Result: no output (unchanged in this ticket).

## E) Validation commands run
From `kymflow/sandbox/diameter-analysis/`:

1. `uv run pytest`
- First run: 1 failure in existing gradient test because new default constraints were active.
- Fix applied: explicit `enable_motion_constraints=False` in that legacy behavior test.
- Second run result: `35 passed, 1 warning`.

2. `uv run run_gui.py`
- Result: app started successfully (`NiceGUI ready to go ...`).
- Manual smoke used while running:
  - file table selection loaded TIFFs (confirmed by `tiff_loader` logs)
  - detection UI remained operational.
- Process stopped manually with `Ctrl+C` after startup checks.

## F) Summary of changes
- Added gradient-only motion constraints with 3 threshold types in µm.
- Violations now set offending values to NaN and add QC flags; no clamping/correction.
- Extended result model with per-frame QC booleans and persisted CSV columns.
- Added aligned QC array access via `DiameterAnalyzer.motion_qc_arrays(...)` / `last_motion_qc`.
- Detection Params UI now includes motion-control fields with dynamic disable when constraints are off.
- Added “Reset to Defaults” button to recreate default `DiameterDetectionParams()` and refresh UI.
- Added serialization planning TODO comments (scaffold only, no full implementation).

## Assumptions made
- Existing result API remains list-based, so per-frame QC booleans are attached to each `DiameterResult`; aligned bool arrays are exposed via `motion_qc_arrays(...)`.
- Reset action can use page reload after state replacement to guarantee fresh editor widget values.

## G) Risks / tradeoffs
- With constraints enabled by default, behavior changes for gradient method; legacy tests/calls that expect unconstrained behavior must set `enable_motion_constraints=False`.
- `ui.navigate.reload()` on reset is simple and robust, but heavy-handed.

## H) Self-critique
- Pros: implemented requested algorithmic constraints, UI controls, reset behavior, and planning TODOs with minimal architectural churn.
- Cons: result-structure wording in ticket referenced arrays explicitly; current model uses per-result booleans plus helper arrays rather than replacing primary return type.
- Drift risk: future serialization ticket should formalize dedicated detection result schema object to avoid ad-hoc CSV evolution.

No files outside `kymflow/sandbox/diameter-analysis/` were modified.
