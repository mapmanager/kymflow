# ticket_025_detection_params_docs_metadata_tooltips.md

## Goal
Implement the **documentation + param metadata + minimal GUI tooltips/help text + acceptance checks** for `DiameterDetectionParams`, **without changing any algorithm behavior**.

This is the immediate follow-up to ticket_024.

## Scope / Constraints
- **EDIT ONLY**: `sandbox/diameter-analysis/**`
- **DO NOT EDIT**: anything under `kymflow/**`
- **NO algorithm behavior changes**:
  - Do not change detection math, thresholds, defaults, or runtime logic.
  - This ticket is docs + metadata + UI display + tests only.

## Motivation
We need a single, authoritative explanation of each detection parameter (units, meaning, how it influences behavior, and which detection method uses it), and we want the GUI to surface that information inline so users can tune confidently.

## Deliverables

### 1) Add documentation page
Create: `sandbox/diameter-analysis/docs/detection_params.md`

Include:
- Short overview of detection methods (`threshold_width`, `gradient_edges`) and the shared pipeline stages.
- A table covering **every field** in `DiameterDetectionParams`:
  - **name**
  - **type**
  - **default**
  - **units** (or “unitless”)
  - **used by**: `threshold_width`, `gradient_edges`, or both
  - **description** (clear, one-paragraph)
  - **tuning guidance** (what happens if increased/decreased)
  - **common failure modes** (e.g., “centerline jumps”)
- A “Tuning cookbook” section:
  - “Edges jumping / centerline jitter”
  - “False edges / background texture”
  - “Missing edges / low contrast”
  - “Over-smoothing / under-smoothing”
  - Give **actionable heuristics** and note typical trade-offs.

### 2) Update Google-style docstrings (source of truth)
Update Google docstrings for:
- `DiameterDetectionParams` (class docstring + field-level meaning in the docstring)
- Any public enums used by detection params (brief docstrings)
- Any serialization helpers touched by this ticket (if necessary)

**Important**: Docstrings should:
- State **units**, method applicability, and effect of changing each param.
- Be consistent with `docs/detection_params.md`.

### 3) Add param metadata to `DiameterDetectionParams`
Implement `dataclasses.field(metadata={...})` on each field in `DiameterDetectionParams`, using keys:

- `description`: short sentence suitable for GUI display
- `units`: e.g. `"um"`, `"px"`, `"s"`, `"unitless"`
- `methods`: list like `["gradient_edges"]` or `["threshold_width","gradient_edges"]` (optional but recommended)

No changes to defaults. Metadata only.

### 4) Minimal GUI help/tooltip rendering
In the GUI dataclass editor (`sandbox/diameter-analysis/gui/widgets.py`), implement **minimal** support to display metadata:

- For each control:
  - render a small help line under the widget (preferred) OR
  - render a tooltip icon next to the label
- Use `field.metadata.get("description")` and optionally include units/method applicability in the help text.

Rules:
- Keep styling subtle (`text-xs`, muted color).
- No layout breakage: must work with existing card layout.
- Do not add new dependencies.

### 5) Acceptance checks / tests
Add/extend tests under `sandbox/diameter-analysis/tests/`:

**A. Docs coverage test**
- Parse the `DiameterDetectionParams` dataclass fields and assert every field name appears in `docs/detection_params.md`.
- This prevents drift when fields change.

**B. Metadata coverage test**
- Assert each field has `metadata["description"]` (and `metadata["units"]` if you implement it for all fields).

**C. GUI smoke test (minimal)**
- Instantiate the editor for `DiameterDetectionParams` and confirm it renders without exception (no need to run NiceGUI server; keep it unit-test level).

## Files Likely Touched
- `sandbox/diameter-analysis/diameter_analysis.py` (docstrings + dataclass field metadata)
- `sandbox/diameter-analysis/docs/detection_params.md` (new)
- `sandbox/diameter-analysis/gui/widgets.py` (render metadata help)
- `sandbox/diameter-analysis/tests/test_detection_params_docs.py` (new)
- `sandbox/diameter-analysis/tests/test_detection_params_metadata.py` (new)
- Potentially `sandbox/diameter-analysis/tests/test_gui_dataclass_editor_smoke.py` (new)

## Non-goals
- No changes to detection algorithms, defaults, or behavior.
- No redesign of GUI layout.
- No changes to kymflow APIs or imports.

## Validation
- `uv run pytest` passes.
- `docs/detection_params.md` exists and includes all detection params fields.
- GUI shows per-field help text/tooltips derived from metadata for detection params card.
- No functional behavior changes in detection.
