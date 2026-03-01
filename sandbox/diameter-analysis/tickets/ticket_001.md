# ticket_001.md — Initialize diameter-analysis scaffold + snapshot + synthetic + plotting

## Mode
Exploration

## Context
We are starting a new pure-python (NumPy/SciPy allowed) kymograph diameter-analysis sandbox module under:
`kymflow/sandbox/diameter-analysis/`

We need:
- an architecture snapshot as the source of truth,
- minimal OO API skeleton,
- docs + tests,
- a synthetic kymograph generator for repeatable development,
- plotting helpers (matplotlib + plotly dict-first) from the beginning,
- validation via `uv`.

## Scope (STRICT)

### Allowed edits
- `kymflow/sandbox/diameter-analysis/**`

### Forbidden edits
- Anything outside `kymflow/sandbox/diameter-analysis/` (including any other `kymflow/` modules and any other `sandbox/` folders)

## Requirements
R1: Create `ARCHITECTURE_SNAPSHOT_v1.md` in `kymflow/sandbox/diameter-analysis/` describing:
- scope and invariants (dim0=time, dim1=space; compute in pixels; unit conversion at end),
- module/file roles,
- primary public API (classes/functions),
- IO/sidecar conventions (json params + csv results; may be stubs for ticket_001),
- validation commands.

Use the architecture snapshot template structure.

R2: Create a minimal package layout with an OO entry class (skeleton only) supporting:
- init with ndarray + metadata: `seconds_per_line` and `um_per_pixel`, plus `polarity` option,
- `analyze(...)` (placeholder implementation acceptable),
- `save_analysis(...)` / `load_analysis(...)` stubs that define file naming conventions and intended formats,
- `plot(...)` or helper calls into plotting module.

R3: Create `docs/` with at least:
- `docs/usage.md` — how to run example + brief API intro,
- `docs/dev_notes.md` — design notes, open questions, and planned next steps.

R4: Create `tests/` with at least one pytest that:
- generates a synthetic kymograph,
- runs a trivial analysis placeholder (can return empty results for now),
- asserts basic types/shapes,
- asserts `DiameterDetectionParams` (or equivalent params dataclass created in this ticket) round-trips via `to_dict()/from_dict()`.

R5: Add plotting module `diameter_plots.py` with separate, composable functions:
Matplotlib:
- `plot_kymograph_with_edges_mpl(...)`
- `plot_diameter_vs_time_mpl(...)`
Plotly (dict-first):
- `plot_kymograph_with_edges_plotly_dict(...) -> dict`
- `plot_diameter_vs_time_plotly_dict(...) -> dict`

These may internally use a Plotly Figure if needed, but must return a dict representation and keep the dict available.

R6: Add an example script `run_example.py` that:
1) generates a synthetic kymograph,
2) runs the skeleton analysis,
3) produces at least one matplotlib figure and one plotly dict (printing keys/summary is OK).

R7: Ensure all code runs from `kymflow/sandbox/diameter-analysis/` with:
- `uv run python ...`
- `uv run pytest ...`

## Acceptance criteria
- Folder contains:
  - `ARCHITECTURE_SNAPSHOT_v1.md`
  - `docs/usage.md`, `docs/dev_notes.md`
  - `tests/` with passing pytest
  - `diameter_plots.py`
  - `run_example.py`
- No edits outside the allowed scope.
- Validation commands pass.

## Validation commands
- `uv run pytest -q`
- `uv run python run_example.py`

## Notes / constraints
- Dim0 is time; dim1 is space.
- Compute in pixels; convert to um at the end.
- Polarity option must exist: `polarity="bright_on_dark" | "dark_on_bright"` (default bright_on_dark).
- Keep plotting functions separate and composable (do not force a single monolithic plotting call).

## Codex implementation report
Save:
- `kymflow/sandbox/diameter-analysis/tickets/ticket_001_codex_report.md`
