# Codex Report: ticket_010_tiff_card_metadata_logging_and_codex_guardrails.md

Final report path written: `kymflow/sandbox/diameter-analysis/tickets/ticket_010_tiff_card_metadata_logging_and_codex_guardrails_codex_report.md`

## Summary of changes
- Added TIFF metadata flow (shape, dtype, min, max) from backend loader to GUI state and TIFF card labels.
- Added TIFF load failure UX handling: negative notify, inline card error, and `logger.error(...)`.
- Added centralized console logging configuration and replaced `print()` in requested paths.
- Updated ticket governance docs with frontend/backend separation and file picker guardrails.
- Added backend test validating TIFF metadata values.

## A) Modified code files
- `kymflow/sandbox/diameter-analysis/diameter_analysis.py`
- `kymflow/sandbox/diameter-analysis/tiff_loader.py`
- `kymflow/sandbox/diameter-analysis/gui/app.py`
- `kymflow/sandbox/diameter-analysis/gui/models.py`
- `kymflow/sandbox/diameter-analysis/gui/controllers.py`
- `kymflow/sandbox/diameter-analysis/gui/views.py`
- `kymflow/sandbox/diameter-analysis/gui/file_picker.py`
- `kymflow/sandbox/diameter-analysis/gui/logging_setup.py` (new)
- `kymflow/sandbox/diameter-analysis/tests/test_ticket_009_tiff_loader_gui_backend.py`
- `kymflow/sandbox/diameter-analysis/tickets/CODEX_RULES.md`
- `kymflow/sandbox/diameter-analysis/tickets/TICKET_TEMPLATE.md`

## B) Artifacts created
- `kymflow/sandbox/diameter-analysis/tickets/ticket_010_tiff_card_metadata_logging_and_codex_guardrails_codex_report.md` (this report)

## C) Unified diff (short)
```diff
diff --git a/diameter_analysis.py b/diameter_analysis.py
@@ class KymographPayload:
+    loaded_shape: tuple[int, int] | None = None
+    loaded_dtype: str | None = None
+    loaded_min: float | None = None
+    loaded_max: float | None = None
@@
+            loaded_shape=(None if obj.loaded_shape is None else tuple(int(v) for v in obj.loaded_shape)),
+            loaded_dtype=None if obj.loaded_dtype is None else str(obj.loaded_dtype),
+            loaded_min=None if obj.loaded_min is None else float(obj.loaded_min),
+            loaded_max=None if obj.loaded_max is None else float(obj.loaded_max),
```

```diff
diff --git a/tiff_loader.py b/tiff_loader.py
@@
+logger = logging.getLogger(__name__)
@@
+    loaded_min = float(np.nanmin(arr))
+    loaded_max = float(np.nanmax(arr))
+    logger.info("Loaded TIFF path=%s shape=%s dtype=%s min=%s max=%s", ...)
@@
+        loaded_shape=(int(arr.shape[0]), int(arr.shape[1])),
+        loaded_dtype=str(arr.dtype),
+        loaded_min=loaded_min,
+        loaded_max=loaded_max,
```

```diff
diff --git a/gui/models.py b/gui/models.py
@@ class AppState:
+    loaded_shape: Optional[tuple[int, int]] = None
+    loaded_dtype: Optional[str] = None
+    loaded_min: Optional[float] = None
+    loaded_max: Optional[float] = None
+    tiff_error: Optional[str] = None
```

```diff
diff --git a/gui/controllers.py b/gui/controllers.py
@@ def set_img(...):
+        loaded_shape: tuple[int, int] | None = None,
+        loaded_dtype: str | None = None,
+        loaded_min: float | None = None,
+        loaded_max: float | None = None,
@@
+        self.state.loaded_shape = loaded_shape
+        self.state.loaded_dtype = loaded_dtype
+        self.state.loaded_min = loaded_min
+        self.state.loaded_max = loaded_max
+        self.state.tiff_error = None
@@ def load_tiff(...):
+            loaded_shape=payload.loaded_shape,
+            loaded_dtype=payload.loaded_dtype,
+            loaded_min=payload.loaded_min,
+            loaded_max=payload.loaded_max,
```

```diff
diff --git a/gui/views.py b/gui/views.py
@@
+logger = logging.getLogger(__name__)
@@ TIFF Loader card
+                loaded_shape_el = ui.label("Shape: (none)")
+                loaded_dtype_el = ui.label("Dtype: (none)")
+                loaded_min_el = ui.label("Min: (none)")
+                loaded_max_el = ui.label("Max: (none)")
+                tiff_error_el = ui.label("").classes("text-sm text-red-600")
@@ load failure
+                        msg = f"Failed to load TIFF: {e}"
+                        logger.error("TIFF load failed: %s", e)
+                        controller.state.tiff_error = msg
+                        controller._emit()
+                        ui.notify(msg, type="negative", timeout=8000)
@@ refresh
+                    loaded_shape_el.text = ...
+                    loaded_dtype_el.text = ...
+                    loaded_min_el.text = ...
+                    loaded_max_el.text = ...
+                    tiff_error_el.text = state.tiff_error or ""
```

```diff
diff --git a/gui/file_picker.py b/gui/file_picker.py
@@
+logger = logging.getLogger(__name__)
@@
-        print("file picker unavailable: app.native is not available")
+        logger.error("file picker unavailable: app.native is not available")
@@
-        print("file picker unavailable: app.native.main_window is not available")
+        logger.error("file picker unavailable: app.native.main_window is not available")
@@
-        dialog_type_enum,
+        webview.FileDialog.OPEN,
```

```diff
diff --git a/gui/app.py b/gui/app.py
@@
+from .logging_setup import configure_logging
+logger = logging.getLogger(__name__)
@@
-        print("Failed to import SyntheticKymographParams:", e)
+        logger.warning("Failed to import SyntheticKymographParams: %s", e)
@@
-        print("Failed to build detection params:", e)
+        logger.warning("Failed to build detection params: %s", e)
@@
-        print("Failed to build post_filter_params:", e)
+        logger.warning("Failed to build post_filter_params: %s", e)
@@
+    configure_logging()
```

```diff
diff --git a/gui/logging_setup.py b/gui/logging_setup.py
new file mode 100644
@@
+def configure_logging() -> None:
+    level_name = os.environ.get("DIAMETER_GUI_LOG_LEVEL", "INFO").upper()
+    level = getattr(logging, level_name, logging.INFO)
+    ...
+    logging.basicConfig(level=level, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
```

```diff
diff --git a/tests/test_ticket_009_tiff_loader_gui_backend.py b/tests/test_ticket_009_tiff_loader_gui_backend.py
@@
+def test_load_tiff_kymograph_includes_metadata(...):
+    ...
+    assert payload.loaded_shape == arr.shape
+    assert payload.loaded_dtype == str(arr.dtype)
+    assert payload.loaded_min == float(arr.min())
+    assert payload.loaded_max == float(arr.max())
```

```diff
diff --git a/tickets/CODEX_RULES.md b/tickets/CODEX_RULES.md
@@
+## 7) Frontend/backend separation guardrail
+... backend logic outside `gui/`; controller mediates state ...
+
+## 8) File picker guardrail
+... only modify when requested; must use `webview.FileDialog.OPEN`; no `webview.OPEN_DIALOG` ...
```

```diff
diff --git a/tickets/TICKET_TEMPLATE.md b/tickets/TICKET_TEMPLATE.md
@@
+- Frontend/backend guardrail: backend logic outside `gui/`; controller mediation.
+- File picker guardrail: no edits unless requested; require `webview.FileDialog.OPEN`; no `webview.OPEN_DIALOG`.
```

## D) Search confirmation
- Pattern search for removed prints in requested files:
  - `rg -n "\bprint\(" gui/controllers.py gui/file_picker.py tiff_loader.py`
  - Result: no matches.
- Pattern search for file picker enum:
  - `rg -n "FileDialog.OPEN|OPEN_DIALOG" gui/file_picker.py`
  - Result: `webview.FileDialog.OPEN` present, `OPEN_DIALOG` absent.
- Pattern search for metadata/error fields:
  - `loaded_shape|loaded_dtype|loaded_min|loaded_max|tiff_error|TIFF load failed|Shape:|Dtype:|Min:|Max:`
  - Result: new fields and UI labels are present in backend/state/controller/view.

## E) Validation commands run
From `kymflow/sandbox/diameter-analysis/`:

1. `uv run pytest`
- Result: `30 passed, 1 warning`

2. `uv run run_gui.py`
- First attempt in sandbox failed due uv cache permissions.
- Re-ran with approval outside sandbox restrictions.
- Observed startup line: `NiceGUI ready to go on http://127.0.0.1:8000`
- Stopped manually with `Ctrl+C` after confirming startup.

## Manual verification steps
1. Run GUI: `uv run run_gui.py`.
2. In TIFF Loader card, click `Open TIFF...` and choose a valid 2D TIFF.
3. Confirm card shows `Path`, `Shape`, `Dtype`, `Min`, and `Max` values.
4. Attempt invalid load (non-2D TIFF or unreadable file) and confirm:
- negative `ui.notify("Failed to load TIFF: ...")`
- inline red error text in TIFF card
- `logger.error("TIFF load failed: ...")` output in console

## Assumptions made
- `tifffile` and native dialog dependencies are already available in this environment.
- Metadata min/max should reflect raw loaded array values without any scaling or type conversion.

## Risks / limitations / what to do next
- Interactive invalid-file path was not exercised headlessly; behavior is implemented and requires manual GUI interaction to observe.
- `KymographPayload.to_dict()` still carries `numpy.ndarray` for `kymograph`, which is fine for in-memory usage but not direct JSON serialization.

## Self-critique
- Pros: minimal incremental changes; metadata computed once at load; clear error path in UI and logs.
- Cons: this reuses ticket_009 test file for ticket_010 metadata assertions instead of creating a separate ticket_010 test file.
- Drift risk: if pywebview changes dialog enums again, file picker guardrails and tests should be extended to catch it.

No files outside `kymflow/sandbox/diameter-analysis/` were modified.
