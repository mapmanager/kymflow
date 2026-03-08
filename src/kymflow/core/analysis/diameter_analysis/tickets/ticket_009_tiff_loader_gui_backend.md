# Ticket: ticket_009_tiff_loader_gui_backend.md

## Goal
Add a minimal, reliable TIFF kymograph loader path (load-only) and integrate it into the NiceGUI Diameter Explorer so users can:
1) load a .tif into a 2D numpy array,
2) set seconds_per_line + um_per_pixel for that loaded image,
3) run existing diameter detection + plotting using the **same backend API** as synthetic images.

This ticket MUST NOT break the existing synthetic workflow.

## Scope / Constraints
- Work only in: `kymflow/sandbox/diameter-analysis/` (and its subfolders).
- Use `uv` commands (run via `uv run ...`).
- Use `tifffile` for **loading only** (do not add any tif writing).
- GUI is NiceGUI and already exists under `diameter-analysis/gui/`.
- Keep MVC structure (controller/state/views/widgets). Do not re-architect unless required.
- IMPORTANT: The GUI must call backend APIs; do not copy/paste backend logic into GUI.

## Codex Orientation (Read First)
- This sandbox now has:
  - Backend analysis API (e.g. `diameter_analysis.DiameterAnalyzer`, dataclasses for params/results, synthetic generator).
  - Frontend NiceGUI app under `diameter-analysis/gui/` that should *use* backend APIs.
- When adding new GUI features, treat the existing GUI folder as source-of-truth; make small, incremental edits.
- Prefer creating small backend functions/types that the GUI calls, instead of embedding logic in GUI files.

## Deliverables
### A) Backend: a unified "payload" dataclass for loaded images
Add a dataclass (name is your choice, but keep it obvious) in backend (prefer `diameter_analysis.py` or a new backend module):
- Fields:
  - `kymograph: np.ndarray` (2D, dtype arbitrary)
  - `seconds_per_line: float`
  - `um_per_pixel: float`
  - `polarity: str` (reuse existing naming, default `"bright_on_dark"`)
  - `source: str` (e.g. `"synthetic"` or `"tiff"`)
  - `path: str | None` (None for synthetic)
- Implement `to_dict()` / `from_dict()` in the project's preferred style (follow current serialization conventions; do NOT introduce brittle hand-written dicts if we are moving toward DRY patterns).

### B) Backend: TIFF loader function
Create a backend function (new module ok, e.g. `tiff_loader.py`):
`load_tiff_kymograph(path: str | Path, *, seconds_per_line: float, um_per_pixel: float, polarity: str="bright_on_dark") -> <payload_dataclass>`
- Uses `tifffile.imread`.
- Validates the array:
  - Must be 2D. If not 2D: raise a clear `ValueError` describing the found shape and expected shape.
- Does not modify intensities.
- Does not transpose (internal convention remains: dim0=time, dim1=space).
- Returns the payload dataclass with `source="tiff"` and `path=<string>`.

### C) GUI: Add "TIFF Loader" card (left column)
In `gui/views.py`, add a new card **above** "Detection Params" and keep "Post Filter Params" card present (do not drop it):
- Title: `TIFF Loader`
- Controls:
  1) Button: `Open TIFF...`
  2) Numeric inputs:
     - `seconds_per_line` (default reasonable value, e.g. 0.001)
     - `um_per_pixel` (default reasonable value, e.g. 0.15)
  3) Label showing currently loaded path (or "(none)").
- Behavior:
  - Clicking `Open TIFF...` opens a native file dialog via pywebview in NiceGUI native mode.
  - Hard-code initial directory:
    `/Users/cudmore/Dropbox/data/cell-shortening/fig1`
  - Filter for `.tif` (and optionally `.tiff` if easy).
  - If user cancels: no changes.
  - If file chosen: call backend `load_tiff_kymograph(...)`, update app state to:
    - set `state.img` to the loaded array
    - store `seconds_per_line` and `um_per_pixel` in state so detection uses them
    - store `state.loaded_path` (or similar) for display
    - rebuild plots immediately (so kymograph appears without needing detection)

### D) GUI: Minimal native file picker helper
Add `gui/file_picker.py` (or similar) containing a **refactored** async `_prompt_for_path(...)` based on the user-provided function:
- Remove AppContext/gate logic entirely.
- Keep only:
  - get `nicegui.app.native.main_window`
  - call `create_file_dialog(...)`
  - return `str(path)` or `None`
- It should work for dialog_type="file" for `.tif`.
- Keep logs minimal or use prints; do not add a logging framework if none exists.

### E) Controller: pass dx/dt into DiameterAnalyzer
Update `gui/controller.py` (or wherever `detect()` creates `DiameterAnalyzer`) so it calls:
`DiameterAnalyzer(self.state.img, seconds_per_line=self.state.seconds_per_line, um_per_pixel=self.state.um_per_pixel, polarity=self.state.polarity)`
(or equivalent state fields)
This must work for both synthetic and loaded TIFF.

### F) Tests
Add at least minimal tests under `tests/`:
- Backend `load_tiff_kymograph` rejects non-2D shapes (you can mock `tifffile.imread` to return 3D array).
- Backend payload dataclass round-trip (to_dict/from_dict) sanity.

If adding tifffile dependency requires a pyproject change, do it in this ticket.

## Acceptance Criteria
- `uv run run_gui.py` starts without errors in native=True mode.
- Synthetic workflow still works.
- TIFF workflow:
  - Open TIFF dialog → selecting a file loads image and updates image plot.
  - Clicking Detect runs detection and updates overlays + diameter plot.
- No removal of the Post Filter Params card.
- Backend loader errors are clear and show up as GUI notifications (or logged) without crashing the app.

## Codex Report
- Write the report following the no-overwrite + versioning rules.
- Include:
  - files changed/added
  - how to run GUI
  - how to run tests

