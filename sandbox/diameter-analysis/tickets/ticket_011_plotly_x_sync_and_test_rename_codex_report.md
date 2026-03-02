# Codex Report: ticket_011_plotly_x_sync_and_test_rename.md

Final report path written: `kymflow/sandbox/diameter-analysis/tickets/ticket_011_plotly_x_sync_and_test_rename_codex_report.md`

## A) Modified code files
- `kymflow/sandbox/diameter-analysis/gui/controllers.py`
- `kymflow/sandbox/diameter-analysis/gui/models.py`
- `kymflow/sandbox/diameter-analysis/tickets/CODEX_RULES.md`
- `kymflow/sandbox/diameter-analysis/tickets/TICKET_TEMPLATE.md`
- `kymflow/sandbox/diameter-analysis/tests/test_scaffold.py` (renamed from `test_ticket_001_scaffold.py`)
- `kymflow/sandbox/diameter-analysis/tests/test_analysis_hardened.py` (renamed from `test_ticket_002_hardened.py`)
- `kymflow/sandbox/diameter-analysis/tests/test_gradient_edges.py` (renamed from `test_ticket_003_gradient_edges.py`)
- `kymflow/sandbox/diameter-analysis/tests/test_synthetic_noise_models.py` (renamed from `test_ticket_004_synthetic_noise_models.py`)
- `kymflow/sandbox/diameter-analysis/tests/test_post_filter_diameter.py` (renamed from `test_ticket_007_post_filter_diameter.py`)
- `kymflow/sandbox/diameter-analysis/tests/test_dataclass_serialization_refactor.py` (renamed from `test_ticket_008_dataclass_serialization_refactor.py`)
- `kymflow/sandbox/diameter-analysis/tests/test_tiff_loader.py` (renamed from `test_ticket_009_tiff_loader_gui_backend.py`)

## B) Artifacts created
- `kymflow/sandbox/diameter-analysis/tickets/ticket_011_plotly_x_sync_and_test_rename_codex_report.md` (this report)

## C) Unified diff (short)
```diff
diff --git a/gui/controllers.py b/gui/controllers.py
@@
-    def on_relayout(self, source: str, relayout: dict) -> None:
-        rng = None
-        if "xaxis.range[0]" in relayout and "xaxis.range[1]" in relayout:
-            rng = (float(relayout["xaxis.range[0]"]), float(relayout["xaxis.range[1]"]))
-        elif "xaxis.range" in relayout:
-            r = relayout["xaxis.range"]
-            if isinstance(r, (list, tuple)) and len(r) == 2:
-                rng = (float(r[0]), float(r[1]))
-        if rng is None:
-            return
-        self.state.x_range = rng
-        self._rebuild_figures()
-        self._emit()
+    def on_relayout(self, source: str, relayout: dict) -> None:
+        if self.state._syncing_axes:
+            return
+        new_range: tuple[float, float] | None = None
+        autorange_reset = False
+        for axis_name in ("xaxis", "xaxis2"):
+            ... # parse only x-axis keys (xaxis/xaxis2 range/autorange)
+        if not autorange_reset and new_range is None:
+            return
+        if autorange_reset and self.state.x_range is None:
+            return
+        if new_range is not None and self.state.x_range == new_range:
+            return
+        self.state._syncing_axes = True
+        try:
+            self.state.x_range = None if autorange_reset else new_range
+            self._rebuild_figures()
+            self._emit()
+        finally:
+            self.state._syncing_axes = False
```

```diff
diff --git a/gui/models.py b/gui/models.py
@@
 class AppState:
@@
     x_range: Optional[tuple[float, float]] = None  # seconds
+    _syncing_axes: bool = False
```

```diff
diff --git a/tickets/CODEX_RULES.md b/tickets/CODEX_RULES.md
@@
+## 9) Views regression guardrail
+- If a ticket modifies `gui/views.py`, acceptance criteria must include:
+  - "Post Filter Params card must remain present and functional."
+- When `gui/views.py` is modified, the report must explicitly confirm this.
@@
+- If modification is explicitly requested for `gui/file_picker.py`:
+  - use `webview.FileDialog.OPEN`
+  - not `webview.OPEN_DIALOG`
+  - include manual smoke-test note: "Open TIFF dialog works in macOS native mode."
```

```diff
diff --git a/tickets/TICKET_TEMPLATE.md b/tickets/TICKET_TEMPLATE.md
@@
+- Views regression guardrail:
+  - If editing `gui/views.py`, acceptance criteria must state:
+    - "Post Filter Params card must remain present and functional."
+  - Report must explicitly confirm this when touched.
+- File picker guardrail includes smoke-test note text requirement.
```

```diff
diff --git a/tests/test_ticket_009_tiff_loader_gui_backend.py b/tests/test_tiff_loader.py
similarity index 100%
rename from tests/test_ticket_009_tiff_loader_gui_backend.py
rename to tests/test_tiff_loader.py
```

## D) Search confirmation
- X-sync search:
  - `rg -n "xaxis\.range\[0\]|xaxis\.range\[1\]|xaxis\.range|xaxis\.autorange|xaxis2\.range|xaxis2\.autorange|_syncing_axes|yaxis" gui/controllers.py gui/views.py`
  - Result: only x-axis keys are parsed in controller; no y-axis propagation logic added.
- Test rename check:
  - `ls -1 tests | rg 'ticket_' || true`
  - Result: no test filenames include `ticket_`.

## E) Validation commands run
From `kymflow/sandbox/diameter-analysis/`:

1. `uv run pytest`
- Result: `30 passed, 1 warning`.

2. `uv run run_gui.py`
- Result: app started: `NiceGUI ready to go on http://127.0.0.1:8001`.
- Stopped manually with `Ctrl+C` after startup confirmation.

## F) Summary of changes
- Implemented X-axis-only relayout sync with support for:
  - `xaxis.range[0]`, `xaxis.range[1]`, `xaxis.range`, `xaxis.autorange`
  - `xaxis2.range[0]`, `xaxis2.range[1]`, `xaxis2.range`, `xaxis2.autorange`
- Added sync loop/no-op guard (`state._syncing_axes`) to prevent relayout feedback loops.
- Renamed all ticket-numbered tests to stable non-ticket filenames.
- Updated governance docs/template for:
  - `gui/views.py` Post Filter Params regression guardrail
  - stricter `gui/file_picker.py` modification rule + required smoke-test note.

## Manual verification steps (as requested)
- Start app: `uv run run_gui.py`
- Generate synthetic
- Detect
- In image plot: drag zoom rectangle. Confirm diameter plot x-range matches, y unchanged.
- In diameter plot: drag zoom rectangle. Confirm image plot x-range matches, y unchanged.

## G) Risks / tradeoffs
- GUI interactive zoom/pan behavior was validated at startup level only in this environment; full interactive axis-sync verification requires manual UI interaction.
- `_syncing_axes` guard assumes relayout events happen during figure update cycles; this is standard for Plotly/NiceGUI but should be observed in manual smoke test.

## H) Self-critique
- Pros: minimal focused implementation in controller/state; no analysis/TIFF algorithm changes.
- Cons: current x-sync still relies on full figure rebuild path (existing design), not direct target-only relayout patching.
- Drift risk: future changes to Plotly axis naming conventions may require extending key parsing.

No files outside `kymflow/sandbox/diameter-analysis/` were modified.
