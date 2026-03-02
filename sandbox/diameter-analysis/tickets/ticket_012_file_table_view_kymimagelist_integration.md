# Ticket: ticket_012_file_table_view_kymimagelist_integration.md

## Goal
Add a top-of-page file browser using existing kymflow components:

- Build a `KymImageList` from the seed folder:
  `/Users/cudmore/Dropbox/data/cell-shortening/fig1`
- Render a `FileTableView` at the top of the NiceGUI home page.
- When the user selects a row, load that TIFF path into the app (same as “Open TIFF…” flow):
  - update image plot
  - do NOT auto-run detection (user still clicks Detect)
- Keep the existing “Open TIFF…” button as a fallback.

This ticket is UI plumbing only (uses existing tif loader). A later ticket may use KymImage/KymImageList APIs to load arrays directly.

---

## Scope / Constraints
- Work only in: `kymflow/sandbox/diameter-analysis/`
- Run:
  - `uv run run_gui.py`
  - `uv run pytest`
- Keep sandbox status: do not move code out of sandbox; imports from `kymflow` are allowed.
- Do not modify `gui/file_picker.py` unless explicitly required by this ticket (it is NOT required).
- **Post Filter Params card must remain present and functional** (if touching `gui/views.py`).

---

## Imports to Use (verified available)
```python
from kymflow.gui_v2.views.file_table_view import FileTableView
from kymflow.gui_v2.events import FileSelection
from kymflow.core.image_loaders.kym_image_list import KymImageList
```

---

## A) AppState: add KymImageList
1) Add a new attribute on `AppState`:
   - `kym_image_list: KymImageList | None`
2) Initialize it on app startup (first render / controller init) using the seed directory above.
   - Use KymImageList defaults (recursion/depth etc.); caller does not configure depth.
3) Ensure only `*.tif/*.tiff` entries are exposed to FileTableView. If KymImageList already filters, just use its output; otherwise filter the iterable before passing to FileTableView.

Acceptance:
- app starts without error even if folder is missing (show warning notify + empty table).

---

## B) Views: place FileTableView at top (full width)
1) In home page layout, place FileTableView:
   - after the “Diameter Explorer” title
   - before the buttons (“Generate synthetic”, “Open TIFF…”, “Detect”, etc.)
   - span full width across both columns (top row, not inside left-only column)
2) Keep the existing two-column layout underneath.

---

## C) Wire selection callback to load TIFF
1) Create an `on_selected(file_selection: FileSelection) -> None` callback.
2) When called, use `file_selection.path` as the TIFF path.
3) Load the TIFF exactly as the “Open TIFF…” flow does today:
   - call the same controller method / shared helper used by the button path
   - set `state.img`, update TIFF metadata (path/shape/dtype/min/max), rebuild figures, emit state
4) Do NOT run detection automatically.

Acceptance:
- Selecting a row updates the image plot and TIFF metadata card.
- Detection still requires clicking Detect.

---

## D) Block selection while detect is running
Simplest acceptable implementation:
- while detect() is executing, disable FileTableView selection interactions.
- re-enable once detect completes.

Notes:
- We are not adding true background jobs here. If detection is currently synchronous, disabling selection may be limited.
- If the FileTableView API supports enabling/disabling or overlay, use that. Otherwise, guard in callback:
  - if `state.is_busy` (or similar) then ignore selection and `ui.notify("Busy…", type="warning")`.

---

## E) Keep “Open TIFF…” fallback
Do not remove or hide the existing “Open TIFF…” button / card.

---

## Tests (lightweight)
No GUI tests required.
Add/update a small unit test that:
- builds KymImageList for a temp directory with mixed files
- ensures filtering to tif/tiff (if filtering is implemented in our code path).

If KymImageList itself handles filtering and our code doesn’t add filtering logic, skip this test and note it in the report.

---

## Acceptance Criteria
- `uv run run_gui.py` works in native mode.
- FileTableView appears at top, full width.
- It lists TIFFs from the seed directory (or shows empty + warning if directory missing).
- Selecting a row loads that TIFF into the app (image + metadata updated).
- Detect is still manual.
- Selection is blocked/ignored while detect is running.
- Post Filter Params card remains present/functional.
- `uv run pytest` passes.

---

## Codex Report Requirements
Must include:
- Files changed
- Manual verification steps:
  - app launch
  - FileTableView appears
  - select a row → TIFF loads
  - click Detect
- Note on how selection is blocked during detect
- `uv run pytest` output/summary
