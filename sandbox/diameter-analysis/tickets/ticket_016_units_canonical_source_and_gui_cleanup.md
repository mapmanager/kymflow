# ticket_016 — Canonical units + remove TIFF loader from home + filename in plot + detection reset button placement

**ID:** ticket_016_units_canonical_source_and_gui_cleanup  
**Owner:** Codex  
**Scope:** `kymflow/sandbox/diameter-analysis/` only  
**Goal:** Remove remaining “multiple sources of truth” for spatial/temporal units, simplify GUI by relying on FileTableView (not the TIFF Loader card), improve visual verification by showing filename in the kymograph plot title, and move “Reset to defaults” into the Detection Params card header/top.

---

## Background / Why

We currently have drift risk from multiple unit sources (AppState fields vs selected KymImage vs synthetic payload). We also now have a modular TIFF Loader card, but we want the homepage to rely solely on FileTableView selection for loading files (the TIFF Loader card should remain in the codebase for potential later reuse, but not be rendered on `/`).

We also want the image plot to display the **current filename** at the top (instead of generic “kymograph”) for quick verification.

Finally, “Reset to defaults” should be **inside the Detection Params card** (top/header area) rather than as a separate control elsewhere.

---

## Requirements

### A) Canonical units (seconds_per_line, um_per_pixel)

**Make one canonical source of truth:**
1. **If a real file is selected** (via FileTableView): units must come from `state.selected_kym_image` (or equivalent selection object), not from AppState standalone fields.
2. **If synthetic**: units must live in the synthetic payload / synthetic params (whatever object currently owns `seconds_per_line` and `um_per_pixel` for generated data).
3. **Manual override:** only keep if explicitly required by current GUI UX. If not required, remove override UI and state fields. If you keep overrides, make it explicit and non-default (e.g., “Override units” toggle that is OFF by default).

**Implementation guidance (non-binding):**
- Prefer a single helper `resolve_units(state) -> (seconds_per_line, um_per_pixel)` that pulls from the canonical source and has a clear policy.
- Remove or deprecate `state.seconds_per_line` and `state.um_per_pixel` if they are no longer needed.
- Ensure analyzer construction always uses the resolved units (no silent fallbacks).

### B) Remove TIFF Loader card from homepage (do NOT delete implementation)

- Do **not** delete the modular TIFF loader component code.
- Do **remove it from the `/` UI** (home page layout) so the GUI relies on FileTableView for loading and selection.
- Ensure nothing else breaks (file selection still loads and displays kymograph, and detection still runs).

### C) Plot title should show filename

- When displaying the kymograph in Plotly, set the figure title to something like:
  - `"<filename>"` (or `"<filename> — <shape> <dtype>"` if you want, but filename is required).
- Source of filename:
  - If selected via FileTableView: use `state.selected_kym_image` path basename.
  - If synthetic: use a stable label like `"synthetic"` (optionally include preset name/seed).
- Update should occur whenever selection changes (same event that updates the image).

### D) “Reset to defaults” button location (Detection Params)

- Move the “Reset to defaults” button **into the Detection Params card**, at the top (header row).
- Prefer a small header layout such as:
  - Title on left, reset button on right (or directly under title).
- Reset behavior:
  - Reset should recreate the dataclass instance using its default constructor (factory defaults).
  - It should not reload the entire app.
  - It should immediately update the card UI and keep other state (image, results) unchanged.

---

## Tests

1. **Rename/keep tests non-ticket-specific**
   - Any tests created/modified must not include ticket numbers in filenames.

2. **Add integration-level test for units resolution**
   - Test that when a `selected_kym_image` is present, analyzer uses its units (seconds_per_line, um_per_pixel).
   - Test that for synthetic payload, units come from synthetic config/payload.
   - If override is removed, ensure no override path exists; if override remains, test that override is OFF by default and only applied when explicitly enabled.

3. **Basic GUI sanity (non-UI automated is fine)**
   - At minimum, ensure the plot title generator returns expected strings for:
     - selected file path
     - synthetic mode

---

## Acceptance Criteria

- Homepage no longer renders the TIFF Loader card, but file selection + detection continue to work.
- Units used for analysis are canonical:
  - real-file selection uses selected KymImage units
  - synthetic uses synthetic units
  - no hidden AppState unit fallbacks
- Plotly kymograph plot title shows filename (or “synthetic”) and updates on selection changes.
- “Reset to defaults” button appears inside Detection Params card at top, and works without page reload.
- `uv run pytest` passes.
- `uv run run_gui.py` launches and basic interactions work:
  - select file in table → image updates and title matches selected filename
  - click Detect → overlays + line plot update
  - reset detection defaults → detection params revert, UI updates

---

## Deliverables

- Code changes in `gui/`, backend as needed.
- Updated/added tests (non-ticket-specific filenames).
- Any updated docs/docstrings needed to reflect new canonical-units policy.

---

## Codex report

Write: `tickets/ticket_016_units_canonical_source_and_gui_cleanup_codex_report.md`  
Never overwrite; if exists, write `_v2`, `_v3`, etc.
