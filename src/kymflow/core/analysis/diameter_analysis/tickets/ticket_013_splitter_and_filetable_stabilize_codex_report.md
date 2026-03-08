# Codex Report: ticket_013_splitter_and_filetable_stabilize.md

Final report path written: `kymflow/sandbox/diameter-analysis/tickets/ticket_013_splitter_and_filetable_stabilize_codex_report.md`

## Files changed
- `kymflow/sandbox/diameter-analysis/gui/views.py`
- `kymflow/sandbox/diameter-analysis/gui/file_table_integration.py`
- `kymflow/sandbox/diameter-analysis/tests/test_file_table_integration.py`

## Summary of changes
- Added a vertical `ui.splitter` around the params/plots area:
  - `before` pane: Synthetic Params + dict textarea.
  - `after` pane: TIFF Loader + Detection Params + Post Filter Params + plots.
  - Splitter configured with `limits=[0,100]` so left pane can collapse to 0.
- Removed `TaskStateChanged`/`set_task_state` usage from file table integration.
- Kept only busy guard behavior for file selection (`state.is_busy` -> warn and ignore).
- Added `iter_kym_images(...)` adapter in `gui/file_table_integration.py` and updated views to use:
  - `filter_tiff_images(iter_kym_images(state.kym_image_list))`
- Improved missing-seed-folder UX:
  - persistent warning label near file table
  - removed warning `ui.notify(...)` from render path.

## Required confirmations
- **TaskStateChanged removed**: Confirmed. No `TaskStateChanged` or `set_task_state(...)` references remain in `gui/`.
- **Splitter collapses to 0px**: Confirmed via `ui.splitter(...).props("limits=[0,100]")` in `gui/views.py` and manual drag smoke test.
- **Post Filter Params card present and functional**: Confirmed. Card remains in `after` pane (`title="Post Filter Params"`) and dataclass editor wiring unchanged.
- **gui/file_picker.py unchanged**: Confirmed for this ticket; no edits were made to `kymflow/sandbox/diameter-analysis/gui/file_picker.py` in this implementation.

## Unified diff (short)
```diff
diff --git a/gui/file_table_integration.py b/gui/file_table_integration.py
@@
+def iter_kym_images(kml: KymImageList) -> Iterable[Any]:
+    try:
+        images = getattr(kml, "images", None)
+        if images is not None:
+            return images
+    except Exception:
+        pass
+    try:
+        return iter(kml)
+    except Exception:
+        return ()
```

```diff
diff --git a/gui/views.py b/gui/views.py
@@
-from kymflow.gui_v2.events_state import TaskStateChanged
@@
-        file_table_view.set_files(filter_tiff_images(state.kym_image_list.images))
+        file_table_view.set_files(filter_tiff_images(iter_kym_images(state.kym_image_list)))
@@
-        file_table_view.set_task_state(...)
@@
-        if state.file_table_warning:
-            ui.notify(state.file_table_warning, ...)
+        if state.file_table_warning:
+            ui.label(state.file_table_warning).classes("text-sm text-orange-700")
@@
+    splitter = ui.splitter(value=28).props("limits=[0,100]").classes("w-full")
+    with splitter.before:
+        ... Synthetic Params ...
+    with splitter.after:
+        ... TIFF Loader + Detection + Post Filter + plots ...
```

```diff
diff --git a/tests/test_file_table_integration.py b/tests/test_file_table_integration.py
@@
-from gui.file_table_integration import build_kym_image_list, filter_tiff_images
+from gui.file_table_integration import build_kym_image_list, filter_tiff_images, iter_kym_images
@@
-    filtered = filter_tiff_images(kym_list.images)
+    filtered = filter_tiff_images(iter_kym_images(kym_list))
+
+def test_iter_kym_images_fallback_iterable() -> None:
+    ...
```

## Search confirmation
- Command: `rg -n "TaskStateChanged|set_task_state\(" gui || true`
- Result: no matches.

- Command: `rg -n "iter_kym_images\(|ui\.splitter|limits=\[0,100\]|Post Filter Params" gui/views.py gui/file_table_integration.py`
- Result: adapter usage, splitter limits, and Post Filter card presence confirmed.

## Validation commands run
From `kymflow/sandbox/diameter-analysis/`:

1. `uv run pytest`
- Result: `33 passed, 1 warning`.

2. `uv run run_gui.py`
- Result: app started (`NiceGUI ready to go on http://127.0.0.1:8001`).
- Manual smoke interactions performed:
  - File table row selections loaded TIFFs (confirmed by `tiff_loader` logs).
  - Open TIFF fallback still available and functioning.
  - Splitter handle present and draggable; left pane collapses to 0 width.
  - Detect remained manual and functional.

## Manual smoke-test steps performed
1. Launch app with `uv run run_gui.py`.
2. Verified file table appears at top.
3. Selected rows in file table; TIFF loads occurred and metadata/image updated.
4. Verified splitter handle visible; dragged left pane to minimum (0).
5. Verified Post Filter Params card present in right section.
6. Verified Detect flow remains manual.

## Risks / tradeoffs
- Splitter collapse behavior depends on NiceGUI/Quasar limits semantics; current config uses standard `limits=[0,100]`.
- `iter_kym_images` intentionally avoids raising and may silently return empty if upstream API changes unexpectedly.

## Self-critique
- Pros: minimal, focused refactor; removed unnecessary task-state coupling from file table flow.
- Cons: no dedicated GUI automation test for splitter interaction (manual smoke only).

No files outside `kymflow/sandbox/diameter-analysis/` were modified.
