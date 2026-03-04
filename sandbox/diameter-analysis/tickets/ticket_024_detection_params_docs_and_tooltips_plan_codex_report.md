# ticket_024_detection_params_docs_and_tooltips_plan_codex_report

## Final report path
- `kymflow/sandbox/diameter-analysis/tickets/ticket_024_detection_params_docs_and_tooltips_plan_codex_report.md`

## A) Modified code files
- `kymflow/sandbox/diameter-analysis/diameter_analysis.py`
- `kymflow/sandbox/diameter-analysis/gui/widgets.py`
- `kymflow/sandbox/diameter-analysis/tests/test_detection_params_docs_and_metadata.py`

## B) Artifacts created
- `kymflow/sandbox/diameter-analysis/docs/detection_params.md`
- `kymflow/sandbox/diameter-analysis/tickets/ticket_024_detection_params_docs_and_tooltips_plan_codex_report.md`

## C) Unified diff (short)
### `diameter_analysis.py`
```diff
@@
-from dataclasses import dataclass
+from dataclasses import dataclass, field
@@
 @dataclass(frozen=True)
 class DiameterDetectionParams:
+    """Configuration for the diameter detection pipeline.
+    ... Google-style Attributes with units and method applicability ...
+    """
-    roi: tuple[int, int, int, int] | None = None
+    roi: tuple[int, int, int, int] | None = field(default=None, metadata={"description": ..., "units": ..., "methods": ..., "constraints": ...})
+    ... (metadata added for every field)
@@
     def _apply_motion_constraints(...):
+        """Apply frame-to-frame QC gates for `gradient_edges` outputs.
+        Reads: max_edge_shift_um, max_diameter_change_um, max_center_shift_um.
+        """
@@
     def _analyze_center(...):
+        """Analyze one center row; documents method-specific parameter usage."""
@@
     def _threshold_width(...):
+        """Consumes threshold_mode/threshold_value; ignores gradient and motion params."""
@@
     def _gradient_edges(...):
+        """Consumes gradient_* params; ignores threshold params."""
```

### `gui/widgets.py`
```diff
+def _field_help_text(metadata: Any) -> str:
+    ...  # builds help text from metadata["description"], units, methods
@@
-                # no per-field help text
+                help_text = _field_help_text(f.metadata)
+                if help_text:
+                    ui.label(help_text).classes("col-span-2 text-xs text-gray-500 -mt-2")
```

### `tests/test_detection_params_docs_and_metadata.py`
```diff
+def test_detection_params_doc_contains_all_field_names() -> None:
+    ...
+
+def test_detection_params_metadata_has_description() -> None:
+    ...
+
+def test_widget_help_text_uses_detection_param_metadata() -> None:
+    ...
```

## D) Search confirmation
Searched:
- `class DiameterDetectionParams`
- `_threshold_width(`
- `_gradient_edges(`
- `_apply_motion_constraints(`
- `dataclass_editor_card`
- `description` metadata usage

Changed occurrences:
- Updated `DiameterDetectionParams` declarations/docstring in `diameter_analysis.py`.
- Updated method docstrings where params are consumed.
- Added metadata-based help text rendering in `gui/widgets.py`.
- Added new docs page and tests verifying docs+metadata+help-text wiring.

## E) Validation commands run
Executed from `kymflow/sandbox/diameter-analysis/`.

1. `uv run pytest`
- Outcome: **failed** (5 controller-axis tests currently failing in existing x-sync/autoreset area outside this ticket’s docs/tooltips scope).

2. `uv run pytest tests/test_detection_params_docs_and_metadata.py -q`
- Outcome: **passed** (`3 passed, 1 warning`).

3. `uv run python -c 'from pathlib import Path; from dataclasses import fields; from diameter_analysis import DiameterDetectionParams; txt=Path("docs/detection_params.md").read_text(encoding="utf-8"); missing=[f.name for f in fields(DiameterDetectionParams) if f"`{f.name}`" not in txt]; assert not missing, missing; print("ok")'`
- Outcome: **passed** (`ok`).

## F) Summary of changes
- Added `docs/detection_params.md` with full parameter reference and tuning cookbook.
- Implemented canonical metadata decision **A** (`field(metadata=...)`) on every `DiameterDetectionParams` field.
- Added/expanded Google-style docstrings describing units, constraints, and method applicability.
- Added minimal GUI wiring in `dataclass_editor_card` to display metadata-derived help text per field.
- Added tests to verify docs coverage and metadata-driven help text.

## G) Risks / tradeoffs
- Metadata strings now carry user-facing guidance; future parameter renames must update metadata/docs in lockstep.
- GUI help text uses inline labels (minimal UI change) rather than hover tooltips.
- Full-suite pytest currently has unrelated controller-axis failures; this ticket focuses on docs/tooltips plan scope.

## H) Self-critique
- Pros:
  - Single canonical source for descriptions is now in code metadata.
  - Docs, code docstrings, and UI help are aligned.
  - Added automated checks to prevent docs/metadata drift.
- Cons:
  - Help text is textual inline guidance, not icon tooltip UX.
  - Did not resolve unrelated controller-axis regressions discovered by full-suite run.
- Drift risk / red flags:
  - If new fields are added to `DiameterDetectionParams`, docs and metadata must both be updated (tests will catch docs name omissions).
- What I would do differently next:
  - Add a structured metadata key for “failure_mode_guidance” and render collapsible advanced help in GUI.

## Required confirmation
No files outside `kymflow/sandbox/diameter-analysis/` were modified.
