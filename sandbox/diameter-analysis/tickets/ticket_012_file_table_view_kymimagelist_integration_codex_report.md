# Codex Report: ticket_012_file_table_view_kymimagelist_integration.md

Final report path written: `kymflow/sandbox/diameter-analysis/tickets/ticket_012_file_table_view_kymimagelist_integration_codex_report.md`

## A) Modified code files
- `kymflow/sandbox/diameter-analysis/gui/file_table_integration.py` (new)
- `kymflow/sandbox/diameter-analysis/gui/models.py`
- `kymflow/sandbox/diameter-analysis/gui/app.py`
- `kymflow/sandbox/diameter-analysis/gui/controllers.py`
- `kymflow/sandbox/diameter-analysis/gui/views.py`
- `kymflow/sandbox/diameter-analysis/tests/test_file_table_integration.py` (new)

## B) Artifacts created
- `kymflow/sandbox/diameter-analysis/tickets/ticket_012_file_table_view_kymimagelist_integration_codex_report.md` (this report)

## C) Unified diff (short)
```diff
diff --git a/gui/file_table_integration.py b/gui/file_table_integration.py
new file mode 100644
@@
+from kymflow.core.image_loaders.kym_image_list import KymImageList
+
+SEED_FOLDER = "/Users/cudmore/Dropbox/data/cell-shortening/fig1"
+
+def build_kym_image_list(...) -> tuple[KymImageList | None, str | None]:
+    ...
+
+def filter_tiff_images(images: Iterable[Any]) -> list[Any]:
+    ... suffix in {".tif", ".tiff"} ...
```

```diff
diff --git a/gui/models.py b/gui/models.py
@@ class AppState:
+    kym_image_list: KymImageList | None = None
+    file_table_warning: Optional[str] = None
+    is_busy: bool = False
```

```diff
diff --git a/gui/app.py b/gui/app.py
@@
+from .file_table_integration import build_kym_image_list
@@
+    kym_image_list, warning = build_kym_image_list()
+    state.kym_image_list = kym_image_list
+    state.file_table_warning = warning
+    if warning:
+        logger.warning(warning)
```

```diff
diff --git a/gui/controllers.py b/gui/controllers.py
@@ def detect(self) -> None:
+        if self.state.is_busy:
+            raise RuntimeError("busy")
+        self.state.is_busy = True
+        self._emit()
+        try:
+            ... analyze ...
+        finally:
+            self.state.is_busy = False
+            self._emit()
```

```diff
diff --git a/gui/views.py b/gui/views.py
@@
+from kymflow.gui_v2.views.file_table_view import FileTableView
+from kymflow.gui_v2.events import FileSelection
+from kymflow.gui_v2.events_state import TaskStateChanged
@@
+    with ui.card().classes("w-full h-64"):
+        file_table_view = FileTableView(on_selected=_on_file_selected)
+        file_table_view.render()
+        file_table_view.set_files(filter_tiff_images(state.kym_image_list.images) if state.kym_image_list else [])
+        file_table_view.set_task_state(TaskStateChanged(... running=state.is_busy ...))
+        if state.file_table_warning:
+            ui.notify(state.file_table_warning, type="warning", ...)
@@
+    def _on_file_selected(file_selection: FileSelection) -> None:
+        if state.is_busy:
+            ui.notify("Busy... detect is running", type="warning")
+            return
+        _load_tiff_path(file_selection.path)
```

```diff
diff --git a/tests/test_file_table_integration.py b/tests/test_file_table_integration.py
new file mode 100644
@@
+def test_build_kym_image_list_missing_folder_returns_warning(...): ...
+
+def test_filter_tiff_images_with_kym_image_list(...): ...
```

## D) Search confirmation
- Searched for integration points:
  - `FileTableView|KymImageList|FileSelection|filter_tiff_images|is_busy|set_task_state`
  - Result: wiring exists in app/view/controller/models/helper module.
- Searched for Post Filter card presence in edited `gui/views.py`:
  - Pattern: `Post Filter Params`
  - Result: card remains present in the same section.

## E) Validation commands run
From `kymflow/sandbox/diameter-analysis/`:

1. `uv run pytest`
- Result: `32 passed, 1 warning`.

2. `uv run run_gui.py`
- Result: app started (`NiceGUI ready to go on http://127.0.0.1:8000`).
- During run, log confirmed TIFF load path through table selection flow (`tiff_loader | Loaded TIFF ...`).
- Process stopped manually with `Ctrl+C` after startup verification.

## F) Summary of changes
- Added top-of-page full-width `FileTableView` fed by `KymImageList` seeded from `/Users/cudmore/Dropbox/data/cell-shortening/fig1`.
- Added startup-safe `KymImageList` init with warning fallback (empty table + warning notify/label when missing).
- Wired row selection to the same TIFF load path used by the Open TIFF card helper (no auto-detect).
- Added busy guard for detect and selection blocking/ignoring while detect runs (`state.is_busy` + warning notify + FileTableView interaction state update).
- Kept Open TIFF button fallback intact.

## Manual verification steps (required)
1. Run app: `uv run run_gui.py`.
2. Confirm `FileTableView` appears at top of page, full width, above toolbar buttons.
3. Select a row in FileTableView:
- TIFF loads into image plot.
- TIFF metadata card updates (`Path`, `Shape`, `Dtype`, `Min`, `Max`).
4. Click `Detect` manually:
- Detection runs only on user click (not auto-run on table selection).
5. While detect is running, attempt row selection:
- Selection is blocked/ignored and warns `Busy... detect is running`.

## Note on selection blocking during detect
- Implemented via `state.is_busy` in `AppController.detect()` and callback guard in `FileTableView` selection handler.
- `FileTableView.set_task_state(TaskStateChanged(...running=state.is_busy...))` is also used to disable interactions visually/behaviorally while busy.

## Post Filter Params card confirmation
- `gui/views.py` was modified.
- Confirmed: **Post Filter Params card remains present and functional**.

## G) Risks / tradeoffs
- `KymImageList` default extension behavior may already prefilter `.tif`; explicit `.tiff` allowance is handled in the view-side filter function for supplied images.
- Selection blocking uses a simple busy flag suitable for current synchronous detect flow.

## H) Self-critique
- Pros: minimal UI plumbing using existing backend loader path; no algorithm/TIFF data handling changes.
- Cons: detect busy state is coarse-grained and synchronous; no background job state model added.
- Drift risk: if upstream `FileTableView` APIs change, adapter code in `gui/views.py` may need updates.

No files outside `kymflow/sandbox/diameter-analysis/` were modified.
