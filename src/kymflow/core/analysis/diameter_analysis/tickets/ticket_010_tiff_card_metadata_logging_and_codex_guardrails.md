# Ticket: ticket_010_tiff_card_metadata_logging_and_codex_guardrails.md

## Goal
1) In the GUI TIFF loader card, display the **loaded kymograph metadata**:
   - shape
   - dtype
   - min
   - max
2) On TIFF load failure:
   - Show `ui.notify(...)`
   - Display inline error inside the TIFF card
   - Log with `logger.error(...)`
3) Introduce a simple, centralized console logger (replace `print()` usage).
4) Strengthen Codex guardrails for frontend/backend separation.
5) Protect `gui/file_picker.py` from unintended rewrites.

---

## Scope / Constraints

- Work only in: `kymflow/sandbox/diameter-analysis/`
- Use uv:
  - `uv run run_gui.py`
  - `uv run pytest`
- Do NOT manipulate TIFF pixel data after load (no scaling, casting, normalization).
- Plot transpose remains allowed inside plotting layer only.
- Preserve working file picker implementation:
  - MUST use `webview.FileDialog.OPEN`
  - MUST NOT use `webview.OPEN_DIALOG`
- Keep changes minimal and incremental.

---

## Deliverables

### A) TIFF Loader Card: Metadata Display

When a TIFF is successfully loaded, display:

- `Path:` (already present)
- `Shape:` (e.g., `(1000, 128)`)
- `Dtype:` (e.g., `uint16`)
- `Min:`
- `Max:`

Requirements:
- Use raw loaded array (before any transpose).
- Values update immediately after load.
- If no TIFF loaded yet, show `(none)` placeholders.

Implementation guidance:
- Add state fields (preferred):
  - `state.loaded_shape: tuple[int, int] | None`
  - `state.loaded_dtype: str | None`
  - `state.loaded_min: float | None`
  - `state.loaded_max: float | None`
- Compute min/max once during load (not dynamically in view).

---

### B) TIFF Load Failure Handling

If load fails (wrong ndim, IO error, etc):

1. `ui.notify("Failed to load TIFF: ...", type="negative")`
2. Inline error message inside TIFF card (e.g., red text below button)
3. `logger.error("TIFF load failed: ...")`

Do not crash the app.

---

### C) Introduce Simple Logging System

Replace scattered `print()` calls with structured logging.

Requirements:
- Add small logging setup module (e.g., `gui/logging_setup.py` or `backend/logging_setup.py`).
- Use Python `logging` module.
- Configure once at startup in `app.py`:
  - Level: INFO default
  - DEBUG optionally enabled via env var
  - Format example:
    ```
    %(asctime)s | %(levelname)s | %(name)s | %(message)s
    ```
- Use:
  - `logger.debug(...)`
  - `logger.info(...)`
  - `logger.warning(...)`
  - `logger.error(...)`

No file logging required — console only.

Replace existing `print()` usage in:
- controller
- file picker
- TIFF loader

---

### D) Frontend / Backend Separation Guardrail

Update `tickets/CODEX_RULES.md`:

Add section:

- Backend logic (analysis, IO, filtering) lives outside `gui/`.
- `gui/` must only call backend APIs.
- Do NOT reimplement analysis inside views or widgets.
- Controller mediates state updates.

Keep concise.

---

### E) Protect file_picker.py

Update `tickets/CODEX_RULES.md` and `tickets/TICKET_TEMPLATE.md`:

Add rule:

- Do not modify `gui/file_picker.py` unless explicitly requested.
- When modifying it:
  - Must use `webview.FileDialog.OPEN`
  - Must not use legacy `webview.OPEN_DIALOG`
  - Must confirm dialog works in macOS native mode.

---

### F) Tests

Add lightweight backend test ensuring:

- After TIFF load:
  - shape matches array
  - dtype matches
  - min/max computed correctly

GUI tests not required.

---

## Acceptance Criteria

- GUI runs in native mode.
- Loading TIFF displays:
  - path
  - shape
  - dtype
  - min
  - max
- On failure:
  - notify shown
  - inline error shown
  - logger.error called
- Console logging replaces print statements.
- pytest passes.
- file_picker remains untouched in behavior.

---

## Codex Report Must Include

- List of modified files
- Manual verification steps:
  - Open TIFF → metadata visible
  - Load invalid TIFF → error notify + inline + logger.error
- pytest command used
