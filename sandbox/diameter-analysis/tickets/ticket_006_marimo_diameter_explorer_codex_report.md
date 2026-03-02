# ticket_006_marimo_diameter_explorer implementation report

Final report path written:
- kymflow/sandbox/diameter-analysis/tickets/ticket_006_marimo_diameter_explorer_codex_report.md

## Summary of what changed
- Added a Marimo notebook app at `notebooks/diameter_explorer.py` with:
  - synthetic generation controls (including uint16/effective bits/noise/bright band),
  - detection controls (ROI, method, params, backend),
  - Plotly transposed kymograph + edge overlay and diameter-vs-time visualization,
  - reproducibility display of `synthetic_params` and detection params dict.
- Added docs page `docs/marimo_explorer.md` covering run instructions and workflow.

## A) Modified code files
- `kymflow/sandbox/diameter-analysis/notebooks/diameter_explorer.py`

## B) Artifacts created
- `kymflow/sandbox/diameter-analysis/docs/marimo_explorer.md`
- `kymflow/sandbox/diameter-analysis/tickets/ticket_006_marimo_diameter_explorer_codex_report.md`

## File-by-file list of changes
- `notebooks/diameter_explorer.py`
  - New Marimo app with Section A synthetic controls and Generate button.
  - Uses `SyntheticKymographParams` and `generate_synthetic_kymograph`.
  - Includes Section B detection controls with ROI helper button, method-specific params, backend selector, and Detect button.
  - Uses existing plotly dict-first helpers from `diameter_plots.py` and renders two stacked Plotly plots.
  - Shows run summary (elapsed time, windows, finite counts, QC flag counts).
  - Displays/exportable JSON for synthetic and detection params.
- `docs/marimo_explorer.md`
  - Added run commands for marimo edit/run and workflow notes.

## C) Unified diff (short)
### `sandbox/diameter-analysis/notebooks/diameter_explorer.py`
```diff
--- /dev/null
+++ sandbox/diameter-analysis/notebooks/diameter_explorer.py
@@ -0,0 +1,497 @@
+import marimo
+app = marimo.App(width="full")
+...
+generate_btn = mo.ui.run_button(label="Generate")
+...
+detect_btn = mo.ui.run_button(label="Detect")
+...
+plot_kymograph_with_edges_plotly_dict(...)
+plot_diameter_vs_time_plotly_dict(...)
```

### `sandbox/diameter-analysis/docs/marimo_explorer.md`
```diff
--- /dev/null
+++ sandbox/diameter-analysis/docs/marimo_explorer.md
@@ -0,0 +1,28 @@
+# Marimo Diameter Explorer
+...
+uv run marimo edit notebooks/diameter_explorer.py
+uv run marimo run notebooks/diameter_explorer.py
```

## D) Search confirmation
Patterns searched:
- `diameter_explorer.py`
- `run_button`
- `plot_kymograph_with_edges_plotly_dict`
- `plot_diameter_vs_time_plotly_dict`
- `SyntheticKymographParams`
- `DiameterDetectionParams`

Result:
- Notebook contains required widgets and execution controls.
- Plotting reuses existing plotly dict-first helpers.
- Docs file for explorer exists and references required run commands.

## E) Validation commands run
Executed from `kymflow/sandbox/diameter-analysis/`:

1. `uv run python -m py_compile notebooks/diameter_explorer.py`
- Result: pass

2. `uv run python run_example.py`
- Result: pass
- Output summary included both methods and finite results.

Best-effort (requested in ticket notes):
3. `uv run marimo --version`
- Result: pass
- Output: `0.20.2`

## F) Summary of changes
- Implemented interactive Marimo explorer notebook in required path.
- Added synthetic + detection parameter controls and Plotly visualization workflow.
- Added short usage doc for the explorer.

## G) Risks / tradeoffs
- The notebook uses a large default `n_time=30000`; full detection runs can be computationally heavy depending on hardware/settings.
- Optional UI control enable/disable logic is represented through toggles and parameter wiring rather than deep dynamic widget-state management.

## H) Self-critique
- Pros: meets required functionality and validation commands; reuses existing plotting helpers.
- Cons: no optional save-to-folder button was added to avoid scope creep.

## Scope confirmation
No files outside `kymflow/sandbox/diameter-analysis/` were modified.
