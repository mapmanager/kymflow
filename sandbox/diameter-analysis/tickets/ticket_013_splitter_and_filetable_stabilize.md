# Ticket: ticket_013_splitter_and_filetable_stabilize.md

## Goal
1) Add a **vertical** `ui.splitter` to the home page layout:
   - **Before/left** pane: Synthetic Params section (“Diameter Explorer” synthetic controls)
   - **After/right** pane: TIFF Loader + Detection Params + Post Filter Params (and plots, as currently arranged)
   - The **before** pane must be able to collapse down to **0px** width.

2) Stabilize FileTableView integration and remove added complexity:
   - Remove `TaskStateChanged` / `set_task_state(...)` usage entirely.
   - Keep only `state.is_busy` + guard in `_on_file_selected` (warn + ignore when busy).
   - Replace any direct access like `state.kym_image_list.images` with a single adapter function in `gui/file_table_integration.py` so the views layer doesn’t depend on internal attributes.

3) Improve “seed folder missing” UX:
   - Do not call `ui.notify(...)` repeatedly from render/build loops.
   - Display a persistent warning label near the file table (and optionally notify once during init).

---

## Scope / Constraints
- Edit only: `kymflow/sandbox/diameter-analysis/`
- Commands:
  - `uv run run_gui.py`
  - `uv run pytest`
- Keep existing UI behavior (generate synthetic, open tiff, detect) intact.
- **Post Filter Params card must remain present and functional** (hard acceptance check).
- **Do NOT modify `gui/file_picker.py`** in this ticket.

---

## A) Splitter layout update (NiceGUI)
Reference: NiceGUI splitter docs (provided by user): `https://nicegui.io/documentation/splitter`

### Requirements
1) In `gui/views.py`, wrap the existing two-column layout in a `ui.splitter` with vertical split.
2) Use the splitter’s `before` / `after` containers:
   - `before`: Synthetic Params card + its dict textarea (keep your current values/defaults)
   - `after`: TIFF Loader card, Detection Params card (+ dict textarea), Post Filter Params card, and the plots
3) Splitter must allow the **before** section to collapse to **0px**.
   - Implement via splitter/Quasar limits props as appropriate (e.g. limits starting at 0).
4) Do not break the row/column structure you already stabilized (no-wrap etc.). Keep the plots on the right side as you have now.

### Acceptance
- App runs; layout shows splitter handle.
- Dragging handle can shrink left pane to 0 width.
- Everything still functions (generate, open tiff, detect).

---

## B) FileTableView stabilize + remove TaskStateChanged
### Requirements
1) Remove all imports/usage of:
   - `from kymflow.gui_v2.events_state import TaskStateChanged`
   - `file_table_view.set_task_state(...)`
2) Keep:
   - `state.is_busy` set True/False around detect
   - `_on_file_selected` checks `state.is_busy` and warns/returns without loading

### Adapter function
In `gui/file_table_integration.py`, add a single public helper:

- `def iter_kym_images(kml: KymImageList) -> Iterable[Any]:`
  - prefer `kml.images` if present
  - else fallback to `iter(kml)` if iterable
  - else fallback to any known public getter if exists
  - never raise; return empty iterable on failure

Then keep `filter_tiff_images(...)` and change `views.py` to use:

- `filter_tiff_images(iter_kym_images(state.kym_image_list))`

So **only** `file_table_integration.py` knows how to extract images from KymImageList.

### Acceptance
- File table still populates.
- Selecting a row loads the TIFF and updates the image plot.
- No TaskStateChanged references remain.

---

## C) Seed folder warning display without repeated notifications
### Requirements
1) Ensure warnings are not emitted repeatedly on every render.
2) Show a persistent `ui.label(...)` near the file table when the seed folder is missing or list build fails.
3) Optionally notify once at init (controller/app init) if you want, but never in a hot render loop.

---

## Tests
- Keep existing tests passing.
- If you need to update any tests due to refactors, do so.

---

## Acceptance Criteria (must be verified)
1) `uv run run_gui.py`:
   - Splitter present, collapsible to 0px on left.
   - File table still works.
   - Generate synthetic works.
   - Open TIFF fallback still works.
   - Detect works.
2) Post Filter Params card remains present and functional.
3) `uv run pytest` passes.
4) `gui/file_picker.py` unchanged.

---

## Codex Report Requirements
- List files changed
- Confirm:
  - “TaskStateChanged removed”
  - “Splitter collapses to 0px”
  - “Post Filter Params card present and functional”
  - “gui/file_picker.py unchanged”
- Include manual smoke-test steps performed
- Include pytest result summary
