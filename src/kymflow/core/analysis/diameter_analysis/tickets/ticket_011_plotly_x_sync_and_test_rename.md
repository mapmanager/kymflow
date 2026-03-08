# Ticket: ticket_011_plotly_x_sync_and_test_rename.md

## Goal
1) Plotly zoom/pan axis sync: **sync X-axis only** between the image (heatmap) plot and the diameter (1D) plot.
2) Rename tests so they are **not ticket-number-specific**.
3) Strengthen governance guardrails to prevent recurring regressions:
   - Post Filter Params card must remain present/functional when editing `gui/views.py`.
   - Do not modify `gui/file_picker.py` unless explicitly requested.

---

## Scope / Constraints
- Work only in: `kymflow/sandbox/diameter-analysis/`
- Run commands:
  - `uv run run_gui.py`
  - `uv run pytest`
- Keep changes minimal and focused.
- Do not change analysis algorithms.
- Do not change TIFF pixel data handling.

---

## A) Plotly X-axis sync only (relayout callback)

### Background
Right now, zooming one plot triggers Plotly relayout events. We want:
- User zoom rectangle or pan should update that plot normally (both axes as Plotly does).
- When we sync to the other plot, **only sync X-axis range/autorange**, and do **not** set Y-axis on the other plot.

### Requirements
1) Find where we currently listen for Plotly relayout events (`plotly_relayout`, `relayoutData`, or NiceGUI plotly event wiring).
2) Implement sync such that only these keys are propagated from source → target:
   - `xaxis.range[0]`
   - `xaxis.range[1]`
   - `xaxis.autorange`
   - (if present) `xaxis.range` or `xaxis2.*` variants depending on plot config
3) Explicitly **ignore** any y-axis keys:
   - `yaxis.range[0/1]`, `yaxis.autorange`, etc.
4) Prevent feedback loops:
   - When we apply a synced range to the other plot, that will emit another relayout event.
   - Add a small guard flag (e.g. `state._syncing_axes: bool`) or compare ranges to skip no-op updates.
5) Acceptance check:
   - Zoom on image plot changes its view.
   - Diameter plot x-axis updates to match.
   - Diameter plot y-axis does NOT get overwritten by image plot y-range.
   - Same behavior in the opposite direction (zoom on diameter plot updates only x on image plot).

### Manual verification steps (must include in report)
- Start app: `uv run run_gui.py`
- Generate synthetic
- Detect
- In image plot: drag zoom rectangle. Confirm diameter plot x-range matches, y unchanged.
- In diameter plot: drag zoom rectangle. Confirm image plot x-range matches, y unchanged.

---

## B) Rename tests file(s) to be stable

### Motivation
Ticket_010 added/edited tests in a ticket-number-specific file from ticket_009. We want stable naming.

### Requirements
1) Rename the ticket-numbered test file(s) to something stable, e.g.:
   - `tests/test_tiff_loader.py` or `tests/test_kymograph_payload.py`
2) Update any references/imports accordingly.
3) Ensure `uv run pytest` passes.

### Acceptance
- No tests files should include ticket numbers in their filenames.
- Tests still cover TIFF metadata extraction (shape/dtype/min/max or at least shape/dtype).

---

## C) Governance guardrails updates

### 1) Views regression guardrail
Update `tickets/CODEX_RULES.md` (and optionally `tickets/TICKET_TEMPLATE.md`) to add:

- If a ticket modifies `gui/views.py`, acceptance criteria must include:
  - **“Post Filter Params card must remain present and functional.”**
- Codex must explicitly confirm this in the report when it touches `views.py`.

### 2) Protect file picker
Update `tickets/CODEX_RULES.md` and `tickets/TICKET_TEMPLATE.md` to add/strengthen:

- Do not modify `gui/file_picker.py` unless the ticket explicitly requests it.
- If modification is requested, must:
  - use `webview.FileDialog.OPEN`
  - not use `webview.OPEN_DIALOG`
  - include a manual smoke-test note in the report: “Open TIFF dialog works in macOS native mode.”

---

## Deliverables
- Code changes implementing X-only sync.
- Renamed test file(s) with passing pytest.
- Updated governance docs as above.
- Codex report that includes:
  - files changed
  - verification steps run
  - confirmation of Post Filter Params card if `views.py` changed

---

## Out of Scope
- Adding FileTableView / KymImageList integration (separate ticket).
- Reworking plot styling or adding new plots.
- Changing backend algorithm logic.
