# Ticket 015 Codex Report

Final report path written: `sandbox/diameter-analysis/tickets/ticket_015_refactor_tiff_loader_widget_and_units_codex_report.md`

## Summary of changes
- Refactored the inline TIFF loader UI out of `gui/views.py` into a reusable `TiffLoaderCard` component.
- Added centralized card refresh logic (`TiffLoaderCard.refresh`) to replace repeated per-widget `try/except` update blocks.
- Added controller-level units resolution helper that prefers selected file units (`selected_kym_image`) and falls back to explicit overrides/state defaults.
- Added state support for selected file object and a path-to-KymImage lookup helper.
- Added unit tests for units resolution behavior.

## Screenshot-style layout description
- Left area still shows **Synthetic Params** and synthetic params JSON textarea.
- Right content row still has three vertical columns:
  - Column 1: **TIFF Loader** card (now componentized) + **Detection Params** card + detection params textarea.
  - Column 2: **Post Filter Params** card (still present).
  - Column 3: Image plotly panel (top) + diameter plotly panel (bottom).

## Confirmation checklist (acceptance criteria)
- [x] App starts without startup exception (`uv run python run_gui.py` reached `NiceGUI ready to go`).
- [x] TIFF loader card is rendered via new widget module; inline TIFF UI construction removed from `build_home_page()`.
- [x] File table selection still loads TIFF via controller path.
- [x] Detect flow code path unchanged and still uses loaded image/synthetic image.
- [x] Loaded TIFF metadata labels remain in UI and are updated via widget refresh.
- [x] Busy guard remains for file selection and open dialog.
- [x] Repetitive per-label `try/except` UI updates removed from `views.py` and replaced by helper calls + widget refresh.
- [x] `gui/file_picker.py` unchanged.
- [x] Post Filter Params card remains present and functional in `views.py`.

## A) Modified code files
- `sandbox/diameter-analysis/gui/views.py`
- `sandbox/diameter-analysis/gui/controllers.py`
- `sandbox/diameter-analysis/gui/models.py`
- `sandbox/diameter-analysis/gui/file_table_integration.py`
- `sandbox/diameter-analysis/gui/components/__init__.py`
- `sandbox/diameter-analysis/gui/components/tiff_loader_card.py`
- `sandbox/diameter-analysis/tests/test_units_resolution.py`

## B) Artifacts created
- `sandbox/diameter-analysis/tickets/ticket_015_refactor_tiff_loader_widget_and_units_codex_report.md`

## C) Unified diff (short, per edited code file)

### `sandbox/diameter-analysis/gui/views.py`
```diff
@@
-from .file_picker import prompt_tiff_path
-from .file_table_integration import filter_tiff_images, iter_kym_images
+from .components.tiff_loader_card import TiffLoaderCard
+from .file_table_integration import filter_tiff_images, find_kym_image_by_path, iter_kym_images
@@
-    tiff_seconds_el: Any | None = None
-    tiff_um_el: Any | None = None
+    tiff_loader_card = TiffLoaderCard(
+        controller,
+        initial_dir="/Users/cudmore/Dropbox/data/cell-shortening/fig1",
+    )
@@
-            _load_tiff_path(str(path))
+            selected_kym_image = find_kym_image_by_path(state.kym_image_list, str(path))
+            controller.load_tiff(str(path), selected_kym_image=selected_kym_image)
@@
-                with ui.card().classes("w-full"):
-                    ui.label("TIFF Loader").classes("text-lg font-semibold")
-                    ...
-                    ui.button("Open TIFF...", on_click=_on_open_tiff).props("outline")
+                tiff_loader_card.render()
@@
-                    try:
-                        ...
-                    except Exception:
-                        pass
+                    _set_textarea_from_dataclass(synthetic_dict_el, state.synthetic_params)
+                    _set_textarea_from_dataclass(detection_dict_el, state.detection_params)
+                    tiff_loader_card.refresh()
```

### `sandbox/diameter-analysis/gui/controllers.py`
```diff
@@
-from typing import Optional, Callable
+from typing import Any, Optional, Callable
@@
-    def load_tiff(self, path: str, *, seconds_per_line: float, um_per_pixel: float) -> None:
+    def resolve_units(... ) -> tuple[float, float]:
+        # prefer selected_kym_image units; fallback to explicit overrides/state
+
+    def load_tiff(
+        self,
+        path: str,
+        *,
+        seconds_per_line: float | None = None,
+        um_per_pixel: float | None = None,
+        selected_kym_image: Any | None = None,
+    ) -> None:
@@
-            seconds_per_line=seconds_per_line,
-            um_per_pixel=um_per_pixel,
+            seconds_per_line=resolved_seconds,
+            um_per_pixel=resolved_um,
@@
+            selected_kym_image=selected_kym_image,
```

### `sandbox/diameter-analysis/gui/models.py`
```diff
@@
 if TYPE_CHECKING:
+    from kymflow.core.image_loaders.kym_image import KymImage
@@
 else:
+    KymImage = Any
@@
     post_filter_params: Optional[Any] = None
+    selected_kym_image: KymImage | None = None
     kym_image_list: KymImageList | None = None
```

### `sandbox/diameter-analysis/gui/file_table_integration.py`
```diff
@@
 def filter_tiff_images(images: Iterable[Any]) -> list[Any]:
@@
     return out
+
+def find_kym_image_by_path(kml: KymImageList | None, path: str | Path) -> Any | None:
+    if kml is None:
+        return None
+    target = str(Path(path))
+    for img in iter_kym_images(kml):
+        ...
+```

### `sandbox/diameter-analysis/gui/components/__init__.py`
```diff
@@
+"""Reusable UI components for diameter-analysis GUI."""
```

### `sandbox/diameter-analysis/gui/components/tiff_loader_card.py`
```diff
@@
+class TiffLoaderCard:
+    def render(self) -> None:
+        # builds TIFF loader UI card
+
+    async def _on_open_tiff(self) -> None:
+        # busy guard + file dialog + load
+
+    def _load_path(self, path: str) -> None:
+        # loads with override inputs and selected KymImage when present
+
+    def refresh(self) -> None:
+        # centralized state -> UI update path
```

### `sandbox/diameter-analysis/tests/test_units_resolution.py`
```diff
@@
+def test_resolve_units_prefers_selected_kym_image() -> None:
+    ...
+
+def test_resolve_units_falls_back_to_explicit_override_then_state() -> None:
+    ...
```

## D) Search confirmation
- Searched pattern: `TIFF Loader` in `sandbox/diameter-analysis/gui`.
  - Result: only `gui/components/tiff_loader_card.py` now defines the loader card label.
- Searched pattern: `prompt_tiff_path|find_kym_image_by_path|resolve_units|selected_kym_image`.
  - Confirmed refactor wiring locations are limited to new component + controller + integration + views + new test.
- No other occurrences required edits for this ticket.

## E) Validation commands run
Run from: `kymflow/sandbox/diameter-analysis/`

1. `uv run pytest -q`
- Result: `37 passed, 1 warning in 1.47s`
- Warning: `PytestConfigWarning: Unknown config option: main_file`

2. `uv run python run_gui.py`
- First attempt in sandbox failed with permissions error from uv cache access.
- Re-ran with escalation approval and command started successfully.
- Observed: `NiceGUI ready to go on http://127.0.0.1:8001`
- Process was then interrupted with Ctrl-C (expected for local run loop).

## F) Summary of changes
- Introduced reusable TIFF loader widget component.
- Simplified state-to-UI updates in `views.py`.
- Centralized units resolution in controller with selected-file precedence.
- Added selected file object field in app state.
- Added unit tests for units resolution helper behavior.

## G) Risks / tradeoffs
- GUI interaction steps (manual clicking through open dialog / file table / detect) were not fully exercised interactively in this non-interactive run; startup and code paths were validated.
- `state.seconds_per_line` / `state.um_per_pixel` are still retained for compatibility; helper now governs precedence to reduce desync risk.

## H) Self-critique
- Pros: reduced view complexity, clearer ownership boundary, and explicit unit precedence logic.
- Cons: `views.py` still has some legacy style issues unrelated to this ticket (formatting/structure) that were intentionally not broadened.
- Drift risk: medium-low; if future code mutates units in new paths without `resolve_units`, precedence could diverge again.
- If revisiting: I would add an integration-level test around file-table selection -> controller.load_tiff unit precedence.

## Assumptions
- Existing behavior for detect and plotting pipelines should be preserved as long as `controller.load_tiff` contract remains backward compatible (it does).
- `KymImage` exposes `seconds_per_line` and `um_per_pixel` attributes when available.

No files outside `kymflow/sandbox/diameter-analysis/` were modified.
