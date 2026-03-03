# Ticket 017 Codex Report

Final report path written: `sandbox/diameter-analysis/tickets/ticket_017_kymflow_facade_adapter_codex_report.md`

## Summary of changes
- Added a new adapter module `diameter_kymflow_adapter.py` as the real-kymograph integration entrypoint, wrapping only `kymflow.core.api.kym_external` facade functions.
- Updated GUI integration points to use the adapter for list loading, path lookup, ROI/channel validation, and real channel-data loading.
- Added tests for adapter behavior (missing ROI/channel errors, facade-wrapper behavior, defaults for `channel=1` and `roi_id=1`).
- Added an explicit facade guardrail to `tickets/CODEX_RULES.md`.

## A) Modified code files
- `sandbox/diameter-analysis/diameter_kymflow_adapter.py`
- `sandbox/diameter-analysis/gui/controllers.py`
- `sandbox/diameter-analysis/gui/file_table_integration.py`
- `sandbox/diameter-analysis/gui/views.py`
- `sandbox/diameter-analysis/tests/test_kymflow_adapter.py`
- `sandbox/diameter-analysis/tests/test_units_resolution.py`

## B) Artifacts created
- `sandbox/diameter-analysis/tickets/ticket_017_kymflow_facade_adapter_codex_report.md`

Non-code file updated:
- `sandbox/diameter-analysis/tickets/CODEX_RULES.md` (added facade guardrail section)

## C) Unified diff (short)

### `sandbox/diameter-analysis/diameter_kymflow_adapter.py`
```diff
+from kymflow.core.api.kym_external import (...)
+DEFAULT_CHANNEL_ID = 1
+DEFAULT_ROI_ID = 1
+
+def load_kym_list_for_folder(...)
+def get_kym_by_path(...)
+def get_kym_geometry_for(...)
+def get_kym_physical_size_for(...)
+def get_channel_ids_for(...)
+def load_channel_for(...)
+def get_roi_ids_for(...)
+def get_roi_pixel_bounds_for(...)
+def require_channel_and_roi(...)
```

### `sandbox/diameter-analysis/gui/file_table_integration.py`
```diff
-from kymflow.core.image_loaders.kym_image_list import KymImageList
+from diameter_kymflow_adapter import get_kym_by_path, iter_kym_items, load_kym_list_for_folder
@@
-        return KymImageList(path=folder), None
+        return load_kym_list_for_folder(folder), None
@@
-    return manual iteration / direct compare
+    return get_kym_by_path(kml, path)
```

### `sandbox/diameter-analysis/gui/controllers.py`
```diff
+from diameter_kymflow_adapter import (
+    DEFAULT_CHANNEL_ID, DEFAULT_ROI_ID,
+    get_kym_geometry_for, get_roi_pixel_bounds_for,
+    load_channel_for, require_channel_and_roi,
+)
@@
+def load_real_kym(self, kimg):
+    require_channel_and_roi(kimg, channel=1, roi_id=1)
+    get_roi_pixel_bounds_for(kimg, roi_id=1)
+    channel_data = load_channel_for(kimg, channel=1)
+    self.set_img(..., source="kymflow", selected_kym_image=kimg)
@@
-views file-selection path called load_tiff(...)
+real file-selection path now calls load_real_kym(...)
```

### `sandbox/diameter-analysis/gui/views.py`
```diff
- selected_kym_image = state.kym_image_list.find_by_path(str(path))
- controller.load_tiff(str(path), selected_kym_image=selected_kym_image)
+ selected_kym_image = find_kym_image_by_path(state.kym_image_list, str(path))
+ controller.load_real_kym(selected_kym_image)
```

### `sandbox/diameter-analysis/tests/test_kymflow_adapter.py`
```diff
+def test_require_channel_and_roi_raises_when_missing(...)
+def test_load_channel_for_calls_facade(...)
+def test_defaults_channel_one_and_roi_one_are_applied(...)
```

### `sandbox/diameter-analysis/tests/test_units_resolution.py`
```diff
+monkeypatch.setattr("gui.controllers.get_kym_geometry_for", ...)
```

### `sandbox/diameter-analysis/tickets/CODEX_RULES.md` (non-code)
```diff
+## 10) Real kymograph facade guardrail
+- use only kymflow.core.api.kym_external facade functions
+- do not access KymImage convenience properties directly
```

## D) Search confirmation
Searches run and outcomes:
- Pattern: `find_by_path\(` in `sandbox/diameter-analysis/gui`.
  - Result: direct `state.kym_image_list.find_by_path(...)` usage removed from active selection flow.
- Pattern: `kymflow.core.image_loaders` in updated integration files.
  - Result: removed from `gui/file_table_integration.py`; real-data access now routed through adapter.
- Pattern: `seconds_per_line|um_per_pixel` in controller.
  - Result: real-kym units resolve via adapter geometry; synthetic/manual paths retain explicit values where needed.

## E) Validation commands run
From `kymflow/sandbox/diameter-analysis/`:

1. `uv run pytest`
- Result: `42 passed, 1 warning`

2. `uv run python run_gui.py`
- First sandboxed attempt hit uv cache permissions; reran with escalation.
- Result: GUI launched successfully (`NiceGUI ready to go on http://127.0.0.1:8000`).
- Stopped with Ctrl-C (expected for local server run).

## F) Summary of changes
- Introduced adapter layer for real-kym facade calls.
- Real file selection now uses adapter-backed load path with required `channel=1`, `roi_id=1` validation.
- Added adapter-focused tests and facade-use guardrail documentation.

## G) Risks / tradeoffs
- File table rendering still passes through existing `FileTableView` + row dict behavior from the kym list object; this ticket focuses on selection/load semantics, not table model redesign.
- GUI interaction verification is startup-level in this environment (non-interactive). Manual click-through remains advisable.

## H) Self-critique
- Pros: centralizes real-data integration policy and defaults in one module; easier to enforce in later tickets.
- Cons: adapter includes one helper (`iter_kym_items`) that still materializes list objects based on underlying list behavior.
- Drift risk: medium-low; if future code adds new real-data paths bypassing adapter, guardrail violations could reappear.

## Assumptions
- Real-data path defaults remain hard-coded by ticket requirement: `roi_id=1`, `channel=1`.
- Synthetic path remains independent of ROI/channel and unchanged functionally.

No files outside `kymflow/sandbox/diameter-analysis/` were modified.
