# ticket_006.md — Marimo diameter explorer notebook (synthetic + detection + Plotly overlay)

## Mode
Exploration

## Context
We want an interactive Marimo notebook app for rapid algorithm exploration using:
- Synthetic kymograph generation (with explicit noise controls and uint16/11-bit options)
- Diameter detection (choose method + set detection params)
- Plotting with Plotly (reuse existing plotly dict-first plot helpers) including:
  - transposed kymograph display (x=time, y=space)
  - overlay detected left/right edges
  - diameter vs time plot

Constraints / assumptions:
- Marimo is already available in the uv environment (marimo==0.20.2).
- Notebook location: `kymflow/sandbox/diameter-analysis/notebooks/diameter_explorer.py`
- Default action should run detection across full `n_time` (e.g., 30,000) when requested by user.

## Scope (STRICT)

### Allowed edits
- `kymflow/sandbox/diameter-analysis/**`

### Forbidden edits
- Anything outside `kymflow/sandbox/diameter-analysis/`

## Requirements

### R1: Create Marimo notebook app
Create `kymflow/sandbox/diameter-analysis/notebooks/diameter_explorer.py` as a Marimo notebook.

The notebook must:
- run with: `uv run marimo run notebooks/diameter_explorer.py`
- be usable in both `marimo run` and `marimo edit` modes (no hard dependency on interactive-only APIs).

### R2: UI sections and widget controls

#### Section A: Synthetic data controls
Expose widgets to configure `SyntheticKymographParams` (or the preferred generator interface in this sandbox):

Required controls:
- Shape: `n_time` (int), `n_space` (int)
- Metadata: `seconds_per_line` (float), `um_per_pixel` (float)
- Polarity: dropdown ("bright_on_dark", "dark_on_bright")
- Seed: int
- Output dtype: dropdown ("float32","float64","uint16")
- Effective bits: int (only enabled when dtype=="uint16", default 11)
- Baseline: `baseline_counts` (float; enabled when dtype=="uint16" or when a "use_counts_model" toggle is on)
- Peak scaling: `signal_peak_counts` (float; same enable logic)
- Clip/saturate: checkbox `clip`

Noise/artifact toggles + params (at minimum):
- Additive Gaussian noise: enable + sigma (counts and/or fraction)
- Drift: enable + amp + period
- Fixed pattern columns: enable + sigma
- Speckle: enable + sigma_frac
- Wall jitter: enable + jitter_px
- Bright band artifact:
  - enable
  - x_center_px
  - width_px
  - amplitude_counts
  - saturate checkbox

Behavior:
- Include a “Generate” button that regenerates the synthetic kymograph and displays it.
- Persist the current `synthetic_params` dict in Marimo state so it can be shown/exported.

#### Section B: Detection controls
Expose widgets for detection configuration.

Required controls:
- ROI: (t0, t1, x0, x1) integer inputs, with a helper button “Set ROI to full image”.
- Window rows odd: int (odd)
- Stride: int
- Binning method: dropdown (mean/median)
- Diameter method: dropdown (THRESHOLD_WIDTH, GRADIENT_EDGES)
- Polarity dropdown (should default to synthetic polarity, but user can override)
- If method == THRESHOLD_WIDTH:
  - threshold mode dropdown (e.g., half_max)
  - any existing threshold params
- If method == GRADIENT_EDGES:
  - gradient_sigma float

Execution controls:
- Backend dropdown: serial/threads (default threads)
- Detect button: runs analysis and updates plots
- Show summary text: elapsed time, number of windows, counts of QC flags.

Note: We will NOT add an execution-level chunk_size control here unless it already exists in the API. (That change will be a later ticket.)

### R3: Plotly visualization (reuse existing plot helpers)
Use the existing Plotly dict-first plotting utilities in `diameter_plots.py`:
- Kymograph image plot (transpose-aware, x=time, y=space)
- Overlay left/right edges from results
- Diameter vs time plot

UI layout:
- Two vertically stacked plots (image on top, diameter vs time below).
- Aim to share/align x-axis visually (true linked axes if feasible, but not required).
- It is acceptable to render Plotly using Marimo’s built-in plotly support.

### R4: Matplotlib optional (nice-to-have)
If easy, add an optional mpl preview toggle, but Plotly is primary.

### R5: Data export / reproducibility
Add:
- A small code cell / button to print or display:
  - `synthetic_params` dict
  - detection params dict (e.g., `DiameterDetectionParams.to_dict()`)
- Optional: a button to save current synthetic params + detection params + results to a timestamped folder under `notebooks/output/` (OK to omit if this becomes scope creep).

### R6: Documentation
Add a short doc page:
- `docs/marimo_explorer.md` describing how to run the notebook, what controls exist, and workflow tips.

### R7: Validation
- `uv run python -m py_compile notebooks/diameter_explorer.py`
- `uv run python run_example.py` must still pass.
- If marimo CLI is available in uv env:
  - `uv run marimo --version` should succeed (best-effort; do not fail ticket if marimo CLI isn't exposed, but it should be if installed).

## Acceptance criteria
- Notebook file exists at the required path and runs under marimo.
- User can:
  1) configure synthetic parameters (including dtype uint16 + effective_bits=11),
  2) generate kymograph,
  3) configure detection params,
  4) click Detect,
  5) see Plotly image with overlays + diameter-vs-time plot.
- No edits outside allowed scope.

## Validation commands
- `uv run python -m py_compile notebooks/diameter_explorer.py`
- `uv run python run_example.py`

## Codex implementation report
Save:
- `kymflow/sandbox/diameter-analysis/tickets/ticket_006_marimo_diameter_explorer_codex_report.md`
