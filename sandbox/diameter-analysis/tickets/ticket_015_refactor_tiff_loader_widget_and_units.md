# Ticket: Refactor TIFF Loader UI into a reusable widget + unify units source of truth

**Ticket ID:** ticket_015_refactor_tiff_loader_widget_and_units  
**Area:** `kymflow/sandbox/diameter-analysis/gui/` (NiceGUI frontend)  
**Owner:** Codex  
**Mode:** Implementer  
**Status:** Ready

---

## Context

`gui/views.py::build_home_page()` currently contains substantial inline UI + logic for the TIFF loader card (fields, labels, open dialog callback, status labels, plus a long `_on_state_change` section that manually updates many UI elements with repeated try/except blocks).

This is making the view brittle and difficult to evolve. We also have duplicated “units” state (`state.seconds_per_line`, `state.um_per_pixel`) even though the selected file (via `KymImage` / `KymImageList`) is the canonical source of these values for real data.

We want to refactor toward modular, reusable components and one clear source of truth for units.

---

## Goals

1. **Modularize TIFF loader UI**:
   - Move the entire TIFF loader card (all UI controls + callbacks + state-to-UI refresh logic) out of `build_home_page()` into a dedicated widget component.
   - `build_home_page()` should only instantiate and place the widget (like `TiffLoaderCard(controller).render()` or `build_tiff_loader_card(controller)`), not embed the implementation.

2. **Simplify state → UI updates**:
   - Replace repetitive per-label `try: ... update()` blocks with a small, maintainable strategy:
     - either a single `refresh()` method on the widget, or
     - centralized “binding” helpers (e.g., `set_text(label, value)` and `set_value(input, value)`).

3. **Units source-of-truth cleanup**:
   - Remove or de-emphasize `AppState.seconds_per_line` / `AppState.um_per_pixel` as global mutable “truth”.
   - Prefer deriving units from the selected file (KymImage / selection) when available.
   - Synthetic generation still needs units; treat synthetic as its own payload that carries units.

4. **Preserve behavior**:
   - “Open TIFF…” loads the selected file, updates plots, and does not auto-detect.
   - “Detect” runs detection and updates overlays + diameter plot.
   - Loaded TIFF metadata (path, shape, dtype, min, max) displayed.
   - Existing guard: do not allow file selection while `state.is_busy`.

5. **Guardrails**:
   - **Do not modify** the working `gui/file_picker.py` implementation. If you must touch it, STOP and ask for explicit approval in the Codex report, but default is no changes.
   - **Post Filter Params** card must remain present and functional (we have a history of it disappearing from `views.py`).

---

## Non-goals

- No new algorithms.
- No new threading backend.
- No persistence/serialization changes.
- No refactor outside `sandbox/diameter-analysis/`.

---

## Proposed design

### A) New widget module

Create a new module under `gui/widgets/` or `gui/components/` (choose one and stick to it), e.g.:

- `gui/components/tiff_loader_card.py` containing:
  - `class TiffLoaderCard:`
    - `__init__(self, controller: AppController, *, initial_dir: str)`
    - `render(self) -> None`
    - `refresh(self) -> None` (reads controller.state and updates the card controls)
    - internal: `_on_open_tiff()` (async), `_load_path(path: str)` (sync wrapper calling controller.load_tiff)

The widget should own references to its UI elements (`ui.number`, `ui.label`, etc.) as instance attributes, so refresh is simple and centralized.

### B) Units handling

Introduce *one* helper in controller or models to answer “what units should we use right now”:

- If a TIFF file is loaded from file table / open dialog, treat units as coming from:
  1) `state.selected_kym_image` (if present) OR
  2) the TIFF loader card override values (seconds_per_line, um_per_pixel inputs)

- If synthetic is the active source, use units from `state.synthetic_params` (or the resulting `KymographPayload`).

**Implementation note:** It’s OK if we keep `state.seconds_per_line` / `state.um_per_pixel` temporarily for backward compatibility inside the sandbox, but the widget should:
- read from `state.selected_kym_image` when possible,
- and only fall back to those state fields if no file is selected.

Also: eliminate duplicated state mutations that desynchronize the card from the actual selected file.

---

## Acceptance criteria

### Functional
- App runs with no exceptions on startup.
- TIFF loader card renders via the new widget (no inline “TIFF Loader” UI construction inside `build_home_page()`).
- Clicking “Open TIFF…” opens the dialog and loads a TIFF; UI updates show:
  - loaded path
  - shape
  - dtype
  - min/max
  - no extra manipulation of loaded ndarray (except transpose for plotting)
- Selecting a file from FileTableView loads it (same behavior as open dialog).
- Clicking “Detect” works on loaded TIFF and on synthetic.
- `state.is_busy` guard still blocks selection and shows a warning notification.

### Code quality / structure
- `views.py` becomes shorter and primarily layout code.
- No repeated try/except blocks for each UI element update.
- `gui/file_picker.py` unchanged (unless explicitly justified + called out in report).
- Post Filter Params card still present and functional.

### Tests
- If there are GUI tests, update them to not be ticket-number-specific:
  - Rename any test files like `test_ticket_010_*.py` to a stable name.
- Add at least one small unit test for the “units resolution helper” (if introduced) OR for `filter_tiff_images/iter_kym_images` adapter if touched.

---

## Implementation steps

1. Create new widget module `tiff_loader_card.py` (or similar).
2. Move TIFF loader UI + callbacks from `views.py` into the widget.
3. Replace manual UI element updating with `refresh()`.
4. Update `views.py` to instantiate and place the widget in the existing layout (respect the current splitter/columns).
5. If needed, introduce a single helper to resolve units.
6. Run:
   - `uv run python run_gui.py`
   - Open a TIFF from the hardcoded initial directory:
     `/Users/cudmore/Dropbox/data/cell-shortening/fig1`
   - Select from FileTableView and confirm it loads.
7. Ensure Post Filter Params card remains present.

---

## Codex report requirements

In `tickets/<ticket>_codex_report*.md`, include:

- Summary of what changed (files/modules).
- Screenshot-style description (text) of resulting layout.
- Confirmation checklist for each acceptance criterion.
- Explicit statement: “file_picker.py unchanged” (or if changed, explain exactly why and how).

