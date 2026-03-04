# Ticket 026 — DetectionParams cleanup + make dataclass_editor_card generic (no detection-specific logic)

## Goal
Cleanly separate **detection parameters** (“how”) from **ROI/channel selection** (“what to analyze”), and remove detection-specific special-casing from the generic GUI dataclass editor.

This ticket focuses ONLY on:
- Making `gui/widgets.py::dataclass_editor_card()` fully **generic** (no DetectionParams-specific behavior).
- Refactoring `DiameterDetectionParams` to remove ROI and replace the global motion toggle with per-constraint toggles.

**Do not change diameter detection algorithm behavior** beyond what is strictly required by the refactor (i.e., no new heuristics, no parameter semantics changes except the explicit changes below).

## Constraints / Rules
- Edit only under: `kymflow/sandbox/diameter-analysis/`
- Do **not** modify anything under `kymflow/` outside the sandbox.
- Keep Google-style docstrings.
- Keep logging lines intact if present (do not strip `logger = logging.getLogger(__name__)`).
- Keep the “Post Filter Params” card present and functional if any GUI files are touched.

## Scope A — Make dataclass_editor_card generic (remove DetectionParams special cases)
**File:** `sandbox/diameter-analysis/gui/widgets.py`

### Required changes
1) Remove “motion constraints” special casing entirely:
- Remove the local set:
  ```py
  motion_fields = {"max_edge_shift_um", "max_diameter_change_um", "max_center_shift_um"}
  ```
- Remove `motion_controls` list and `_set_motion_controls_enabled()`.
- Remove any logic that checks field names in `motion_fields`.
- Remove any logic that checks for `enable_motion_constraints` and enables/disables other controls.

2) Remove the special-case event handler for `enable_motion_constraints`:
- Delete the branch:
  ```py
  if name == "enable_motion_constraints":
      ...
  ```

### Acceptance checks
- The editor renders any dataclass without *any* DetectionParams-specific behavior.
- All fields are editable like before (bool -> switch; numeric -> ui.number; Enum -> ui.select; fallback -> ui.input).
- No references to `enable_motion_constraints`, `motion_fields`, or motion control enabling/disabling remain.

## Scope B — Refactor DiameterDetectionParams
**File:** `sandbox/diameter-analysis/diameter_analysis.py`

### B1) Remove `roi` from `DiameterDetectionParams`
Remove the field:
```py
roi: tuple[int, int, int, int] | None = field(
    default=None,
    metadata={...},
)
```

**Rationale:** ROI selection is a global/runtime selection (ROI id -> bounds), not a “how to detect” knob.

### B2) Replace `enable_motion_constraints` with per-constraint toggles
Remove:
```py
enable_motion_constraints: bool = field(default=True, metadata={...})
```

Add 3 new boolean fields (Google docstring + metadata matching the style used elsewhere):
- `max_edge_shift_um_on: bool`
- `max_diameter_change_um_on: bool`
- `max_center_shift_um_on: bool`

Each should follow the existing pattern, e.g.:
```py
max_edge_shift_um_on: bool = field(
    default=True,
    metadata={
        "description": "...",
        "units": "unitless",
        "methods": ["gradient_edges"],
        "constraints": "...",
    },
)
```

### Notes
- Keep the numeric fields as-is (whatever they currently are), and do NOT redefine their types in this ticket.
- Any code that used `enable_motion_constraints` must be updated to use the corresponding per-constraint toggle(s).
- If the algorithm currently gates ALL constraints with a single toggle, the new logic should be:
  - Only apply a constraint if its `_on` boolean is True **and** the corresponding numeric value is not None (or otherwise valid).

## Tests
- Update unit tests affected by these changes.
- Add or adjust tests so the refactor is covered:
  - `DiameterDetectionParams` no longer has `.roi`.
  - `enable_motion_constraints` removed; new booleans exist and default correctly.
  - Motion constraints apply only when the per-constraint toggle is enabled.

## Deliverables
- Updated `gui/widgets.py` with no detection-specific logic in `dataclass_editor_card`.
- Updated `diameter_analysis.py` with the `DiameterDetectionParams` refactor above.
- All tests pass: `uv run pytest`.

## Out of scope (explicit)
- Do NOT introduce ROI/channel arguments to `DiameterAnalyzer.analyze()` in this ticket.
- Do NOT add new algorithm steps or change detection behavior beyond the refactor.
