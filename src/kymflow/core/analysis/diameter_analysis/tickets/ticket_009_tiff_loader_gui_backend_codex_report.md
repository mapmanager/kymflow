# Codex Report: ticket_009_tiff_loader_gui_backend.md

Final report path written: `kymflow/sandbox/diameter-analysis/tickets/ticket_009_tiff_loader_gui_backend_codex_report.md`

## Summary of changes
- Added a backend payload dataclass (`KymographPayload`) to standardize loaded image metadata for synthetic and TIFF sources.
- Added backend TIFF loader (`load_tiff_kymograph`) using `tifffile.imread` with strict 2D validation.
- Added GUI native file picker helper and a new `TIFF Loader` card in the UI, above Detection Params, while keeping Post Filter Params card intact.
- Updated controller/state wiring so detection uses state-provided `seconds_per_line`, `um_per_pixel`, and `polarity` for both synthetic and TIFF paths.
- Added tests for TIFF non-2D rejection and payload dataclass roundtrip.

## A) Modified code files
- `kymflow/sandbox/diameter-analysis/diameter_analysis.py`
- `kymflow/sandbox/diameter-analysis/tiff_loader.py` (new)
- `kymflow/sandbox/diameter-analysis/gui/models.py`
- `kymflow/sandbox/diameter-analysis/gui/controllers.py`
- `kymflow/sandbox/diameter-analysis/gui/views.py`
- `kymflow/sandbox/diameter-analysis/gui/file_picker.py` (new)
- `kymflow/sandbox/diameter-analysis/tests/test_ticket_009_tiff_loader_gui_backend.py` (new)

## B) Artifacts created
- `kymflow/sandbox/diameter-analysis/tickets/ticket_009_tiff_loader_gui_backend_codex_report.md` (this report)

## C) Unified diff (short)
```diff
diff --git a/diameter_analysis.py b/diameter_analysis.py
@@
+@dataclass(frozen=True)
+class KymographPayload:
+    kymograph: np.ndarray
+    seconds_per_line: float
+    um_per_pixel: float
+    polarity: str = "bright_on_dark"
+    source: str = "synthetic"
+    path: str | None = None
+    def to_dict(self) -> dict[str, Any]:
+        return dataclass_to_dict(self)
+    @classmethod
+    def from_dict(cls, payload: dict[str, Any]) -> "KymographPayload":
+        obj = dataclass_from_dict(cls, payload)
+        return cls(kymograph=np.asarray(obj.kymograph), ...)
```

```diff
diff --git a/tiff_loader.py b/tiff_loader.py
new file mode 100644
@@
+def load_tiff_kymograph(path, *, seconds_per_line, um_per_pixel, polarity="bright_on_dark") -> KymographPayload:
+    arr = np.asarray(tifffile.imread(str(Path(path))))
+    if arr.ndim != 2:
+        raise ValueError(f"TIFF kymograph must be 2D (time, space); got shape={arr.shape!r}.")
+    return KymographPayload(..., source="tiff", path=str(Path(path)))
```

```diff
diff --git a/gui/models.py b/gui/models.py
@@
 class AppState:
@@
+    polarity: str = "bright_on_dark"
+    source: str = "synthetic"
+    loaded_path: Optional[str] = None
```

```diff
diff --git a/gui/controllers.py b/gui/controllers.py
@@
-    def set_img(self, img: np.ndarray, *, seconds_per_line: float, um_per_pixel: float) -> None:
+    def set_img(self, img: np.ndarray, *, seconds_per_line: float, um_per_pixel: float, polarity: str = "bright_on_dark", source: str = "synthetic", path: str | None = None) -> None:
@@
+    def load_tiff(self, path: str, *, seconds_per_line: float, um_per_pixel: float) -> None:
+        payload = load_tiff_kymograph(...)
+        self.set_img(payload.kymograph, ..., polarity=payload.polarity, source=payload.source, path=payload.path)
@@
-            polarity="bright_on_dark",
+            polarity=self.state.polarity,
```

```diff
diff --git a/gui/views.py b/gui/views.py
@@
+from .file_picker import prompt_tiff_path
@@
+            with ui.card().classes("w-full"):
+                ui.label("TIFF Loader")
+                tiff_seconds_el = ui.number(label="seconds_per_line", value=float(state.seconds_per_line), ...)
+                tiff_um_el = ui.number(label="um_per_pixel", value=float(state.um_per_pixel), ...)
+                loaded_path_el = ui.label(f"Loaded path: {state.loaded_path if state.loaded_path else '(none)'}")
+                async def _on_open_tiff() -> None:
+                    chosen = await prompt_tiff_path(initial_dir="/Users/cudmore/Dropbox/data/cell-shortening/fig1")
+                    if chosen:
+                        controller.load_tiff(chosen, seconds_per_line=float(tiff_seconds_el.value or 0.001), um_per_pixel=float(tiff_um_el.value or 0.15))
+                ui.button("Open TIFF...", on_click=_on_open_tiff).props("outline")
```

```diff
diff --git a/gui/file_picker.py b/gui/file_picker.py
new file mode 100644
@@
+async def _prompt_for_path(*, dialog_type: str, directory: str, file_types: Sequence[str] | None = None) -> str | None:
+    native = getattr(app, "native", None)
+    main_window = getattr(native, "main_window", None) if native else None
+    selection = await main_window.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=False, directory=directory, file_types=[...])
+    return str(selection[0]) if selection else None
+
+async def prompt_tiff_path(*, initial_dir: str) -> str | None:
+    return await _prompt_for_path(dialog_type="file", directory=initial_dir, file_types=[...])
```

```diff
diff --git a/tests/test_ticket_009_tiff_loader_gui_backend.py b/tests/test_ticket_009_tiff_loader_gui_backend.py
new file mode 100644
@@
+def test_load_tiff_kymograph_rejects_non_2d(monkeypatch):
+    monkeypatch.setattr("tifffile.imread", lambda _path: np.zeros((3, 4, 5), dtype=np.uint16))
+    with pytest.raises(ValueError, match="must be 2D"):
+        load_tiff_kymograph("fake.tif", seconds_per_line=0.001, um_per_pixel=0.15)
+
+def test_kymograph_payload_roundtrip_to_dict_from_dict():
+    payload = KymographPayload(...)
+    loaded = KymographPayload.from_dict(payload.to_dict())
+    assert np.array_equal(loaded.kymograph, payload.kymograph)
```

## D) Search confirmation
- Searched patterns:
  - `KymographPayload|load_tiff_kymograph|TIFF Loader|Open TIFF|prompt_tiff_path|state\.polarity|loaded_path`
- Files searched:
  - `diameter_analysis.py`, `tiff_loader.py`, `gui/views.py`, `gui/controllers.py`, `gui/models.py`, `gui/file_picker.py`
- Result:
  - Added/updated all required callsites for payload, loader, GUI card, controller wiring, and state fields.
  - No extra unrelated occurrences were modified for this ticket.

## E) Validation commands run
Commands were run from `kymflow/sandbox/diameter-analysis/`.

1. `uv run pytest -q`
- Result: `29 passed, 1 warning in 0.78s`

2. `uv run run_gui.py`
- First attempt inside sandbox failed with permissions on uv cache.
- Re-ran with escalation.
- Startup result observed: `NiceGUI ready to go on http://127.0.0.1:8003`
- Process was then interrupted intentionally (`Ctrl+C`) after confirming startup.

## How to run GUI
- `cd kymflow/sandbox/diameter-analysis`
- `uv run run_gui.py`

## How to run tests
- `cd kymflow/sandbox/diameter-analysis`
- `uv run pytest -q`

## F) Summary
- Unified backend payload and TIFF loader added.
- GUI got a native TIFF loading flow without moving backend logic into views.
- Detection now uses state-driven dx/dt + polarity consistently.
- Synthetic workflow remains available (`Generate synthetic`).

## Assumptions made
- `tifffile` is already available in this environment (no pyproject edit needed in-scope).
- NiceGUI native mode provides `app.native.main_window.create_file_dialog(...)`.
- Keeping `source` and `loaded_path` in GUI state is sufficient for this ticket’s display requirements.

## G) Risks / tradeoffs
- GUI runtime validation in this environment was startup-only; interactive dialog selection was not executed end-to-end here.
- `KymographPayload.to_dict()` keeps `kymograph` as `np.ndarray` (not JSON-serializable by default), which is acceptable for in-memory roundtrip tests but not direct JSON persistence.
- File picker helper is intentionally minimal and native-only; browser mode will return `None`.

## H) Self-critique
- Pros: minimal, targeted changes; backend logic remains in backend modules; GUI integration is small and clear.
- Cons: `gui/models.py` still contains older local dataclass serialization helpers that are unused in this ticket path.
- Drift risk: if NiceGUI/pywebview dialog API changes, `gui/file_picker.py` may need a compatibility shim.
- Improvement if extending further: add a small controller-level test for `load_tiff` state transitions (source/path/metadata).

No files outside `kymflow/sandbox/diameter-analysis/` were modified.
