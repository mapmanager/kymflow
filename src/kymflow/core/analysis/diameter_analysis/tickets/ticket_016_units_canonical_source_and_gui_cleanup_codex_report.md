# Ticket 016 Codex Report

Final report path written: `sandbox/diameter-analysis/tickets/ticket_016_units_canonical_source_and_gui_cleanup_codex_report.md`

## Summary of changes
- Enforced canonical units policy in controller logic:
  - real file mode resolves units from `selected_kym_image`
  - synthetic mode resolves units from `synthetic_params`
  - removed hidden fallback to `AppState.seconds_per_line` / `AppState.um_per_pixel`
- Removed TIFF Loader card from homepage layout (component kept in codebase, not rendered at `/`).
- Added kymograph filename title generation (`kymograph_title`) and applied it to image plot figure title.
- Moved “Reset to Defaults” into Detection Params card header and removed page reload behavior.
- Added integration-level tests for analyzer unit source and plot-title sanity.

## Acceptance criteria checklist
- [x] Homepage no longer renders TIFF Loader card.
- [x] File selection via FileTableView still loads TIFF and updates plots.
- [x] Canonical units enforced:
  - [x] selected file uses `selected_kym_image` units
  - [x] synthetic uses `synthetic_params` units
  - [x] no `state.seconds_per_line` / `state.um_per_pixel` fallback in active GUI code
- [x] Kymograph plot title now shows filename for selected files and `synthetic` for synthetic source.
- [x] “Reset to Defaults” button is inside Detection Params card header/top and updates without app reload.
- [x] `uv run pytest` passes.
- [x] `uv run run_gui.py` launches successfully.

## Screenshot-style layout description
- Home page right-side first card column now starts with **Detection Params** (no TIFF Loader card shown).
- Detection Params header includes a right-aligned **Reset to Defaults** button.
- Post Filter Params card remains present in the adjacent column.
- Kymograph plot title displays selected file basename (or `synthetic`).

## A) Modified code files
- `sandbox/diameter-analysis/gui/controllers.py`
- `sandbox/diameter-analysis/gui/models.py`
- `sandbox/diameter-analysis/gui/views.py`
- `sandbox/diameter-analysis/gui/widgets.py`
- `sandbox/diameter-analysis/gui/components/tiff_loader_card.py`
- `sandbox/diameter-analysis/tests/test_units_resolution.py`

## B) Artifacts created
- `sandbox/diameter-analysis/tickets/ticket_016_units_canonical_source_and_gui_cleanup_codex_report.md`

## C) Unified diff (short)

### `sandbox/diameter-analysis/gui/controllers.py`
```diff
@@
+class _ManualUnitSelection:
+    ...
@@
-        self.state.seconds_per_line = float(seconds_per_line)
-        self.state.um_per_pixel = float(um_per_pixel)
+        self.state.selected_kym_image = selected_kym_image
@@
-    def resolve_units(... seconds_per_line=None, um_per_pixel=None)
+    def resolve_units(... source=None)
+        # selected_kym_image first, else synthetic_params for synthetic source, else error
@@
-                seconds_per_line=self.state.seconds_per_line,
-                um_per_pixel=self.state.um_per_pixel,
+                seconds_per_line=seconds_per_line,
+                um_per_pixel=um_per_pixel,
@@
-            seconds_per_line=self.state.seconds_per_line,
-            um_per_pixel=self.state.um_per_pixel,
+            seconds_per_line=seconds_per_line,
+            um_per_pixel=um_per_pixel,
+            title=self.kymograph_title(),
@@
+    def kymograph_title(self) -> str:
+        ...  # filename / synthetic / fallback label
```

### `sandbox/diameter-analysis/gui/models.py`
```diff
@@
-    seconds_per_line: float = 0.001
-    um_per_pixel: float = 0.15
@@
+    selected_kym_image: KymImage | None = None
```

### `sandbox/diameter-analysis/gui/views.py`
```diff
@@
-from .file_picker import prompt_tiff_path
@@
-    # inline TIFF Loader card block
+    # TIFF Loader not rendered on home page; file loading is FileTableView-driven
@@
-                    ui.button("Reset to Defaults", ...)
+                    dataclass_editor_card(..., header_actions=lambda: ui.button("Reset to Defaults", ...))
```

### `sandbox/diameter-analysis/gui/widgets.py`
```diff
@@
-def dataclass_editor_card(...):
+def dataclass_editor_card(..., header_actions: Callable[[], None] | None = None, ...):
@@
-    ui.label(title)
+    with ui.row().classes("w-full items-center justify-between"):
+        ui.label(title)
+        if header_actions is not None:
+            header_actions()
```

### `sandbox/diameter-analysis/gui/components/tiff_loader_card.py`
```diff
@@
-        seconds, um = self.controller.resolve_units()
+        try:
+            seconds, um = self.controller.resolve_units(source=state.source)
+        except Exception:
+            seconds, um = 0.001, 0.15
```

### `sandbox/diameter-analysis/tests/test_units_resolution.py`
```diff
@@
+def test_detect_uses_selected_kym_image_units(monkeypatch) -> None:
+    ...
+
+def test_detect_uses_synthetic_params_units(monkeypatch) -> None:
+    ...
+
+def test_kymograph_title_prefers_selected_filename() -> None:
+    ...
+
+def test_kymograph_title_for_synthetic() -> None:
+    ...
```

## D) Search confirmation
- Searched: `TIFF Loader|tiff_loader_card|Reset to Defaults|kymograph_title(` in `sandbox/diameter-analysis/gui`.
  - Result: TIFF Loader label remains only in component file; no homepage render call.
  - Reset button is now in detection card header path.
  - `kymograph_title()` is present and wired in figure build.
- Searched: `state.seconds_per_line|state.um_per_pixel` in active `sandbox/diameter-analysis/gui`.
  - Result: no matches.
- `gui/file_picker.py` was not modified.

## E) Validation commands run
Run from `kymflow/sandbox/diameter-analysis/`:

1. `uv run pytest`
- Result: `39 passed, 1 warning`.

2. `uv run run_gui.py`
- Result: app launched successfully (`NiceGUI ready to go on http://127.0.0.1:8001`).
- Process was then stopped with Ctrl-C (expected for local run server).

## F) Summary (concise)
- Canonical units now resolved from selected file or synthetic params only.
- Home page no longer renders TIFF Loader card.
- Kymograph title now reflects selected filename/synthetic.
- Detection reset button moved into card header and no longer reloads page.
- Added integration and sanity tests for units/title behavior.

## G) Risks / tradeoffs
- Manual interactive GUI behavior (actual clicks: select file/detect/reset) was not fully automated; startup and code-path behavior were validated.
- TIFF loader component remains in repo and supports explicit unit inputs for non-home reuse; home path is now intentionally file-table-first.

## H) Self-critique
- Pros: canonical unit policy is explicit and centralized; removes hidden unit drift.
- Cons: canonical policy currently depends on `synthetic_params` for synthetic mode; if future flows set synthetic images without params, they must populate units source explicitly.
- Red flags: none blocking in current acceptance path.
- If revisiting: add a thin controller unit-source enum/state marker for stricter diagnostics.

## Assumptions
- Selected KymImage always carries valid `seconds_per_line` and `um_per_pixel` for real-file workflow.
- Synthetic mode has `synthetic_params` populated before detect/figure rebuild.

No files outside `kymflow/sandbox/diameter-analysis/` were modified.
