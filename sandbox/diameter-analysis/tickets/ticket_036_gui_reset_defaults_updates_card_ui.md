# Ticket 036 — GUI: “Reset to Defaults” updates Detection Params card UI

## Goal
When the user clicks **Reset to Defaults** in the **Detection Params** card, the GUI should immediately show the default values (not just apply them on the next Detect run).

## Scope
- Only fix the reset behavior for **Detection Params** in the GUI.
- Do **not** change diameter analysis behavior.
- Do **not** add backward-compat defaults or defensive fallbacks.

## Current behavior (bug)
- Clicking **Reset to Defaults** appears to reset runtime params (Detect uses defaults),
  but the form controls in the Detection Params card do not visually update.

## Likely cause
The current reset handler replaces `controller.state.detection_params` (and emits),
but the `dataclass_editor_card()` widgets are not re-bound / refreshed to the new object values.
`controller._on_state_change` refresh currently updates figures + textareas, but not the editor widgets.

## Requirements
1. Clicking **Reset to Defaults** must:
   - Set `controller.state.detection_params = DiameterDetectionParams()` (or equivalent default constructor)
   - Trigger a UI update so every widget in the Detection Params editor reflects the new values.

2. The fix should be generic and DRY:
   - Prefer a reusable pattern in `gui/widgets.py` so other dataclass cards could support refresh later.
   - Avoid peppering `dataclass_editor_card()` with DetectionParams-specific special cases.

## Implementation plan (one of these; choose simplest that fits current structure)

### Option A (recommended): Add a “refreshable editor” handle
- In `gui/widgets.py`, modify `dataclass_editor_card()` to return BOTH:
  - the card container
  - a `refresh(obj)` callable that updates each control’s `.value` from the dataclass fields
- Store that `refresh` callable in `views.py` (for Detection Params card instance).
- In the Reset handler (currently defined in `views.py`), after updating `controller.state.detection_params`,
  call `refresh(controller.state.detection_params)`.

### Option B: Re-render the Detection Params card on reset
- In `views.py`, build the Detection Params card inside a container (e.g., `ui.column()` or `ui.element()`),
  keep a reference `detection_card_container`.
- On Reset:
  - update `controller.state.detection_params = DiameterDetectionParams()`
  - `detection_card_container.clear()` then rebuild the card
- Ensure this does not break other references (tooltips, handlers).

## Files to touch
- `gui/views.py` (Reset button handler location)
- `gui/widgets.py` (add refresh support OR support re-render cleanly)
- (Optional) `gui/controllers.py` only if you decide to centralize resetting logic there, but keep view plumbing minimal.

## Tests
Add a small GUI-unit-ish test where possible (no browser):
- If you implement Option A:
  - Test `dataclass_editor_card(...).refresh(...)` updates underlying widget values (may require lightweight stubs/mocks).
If GUI testing is too heavy in this sandbox, add at least a unit test that:
- Reset handler sets `state.detection_params` to a fresh default instance AND triggers `_emit()`.

## Acceptance criteria
- Repro steps:
  1) Run `uv run python run_gui.py`
  2) Select a file
  3) Change at least 2 detection params (including a boolean + a float)
  4) Click **Reset to Defaults**
- Expected:
  - The Detection Params UI immediately shows default values for all fields.
  - Clicking **Detect** uses the default values (confirm via the Detection Params JSON textarea).
- `uv run pytest` passes.
