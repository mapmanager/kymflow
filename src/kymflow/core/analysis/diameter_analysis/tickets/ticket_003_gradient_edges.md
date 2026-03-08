# ticket_003.md — Add GRADIENT_EDGES diameter method + transpose-aware plotting (mpl + plotly)

## Mode
Exploration

## Context
We currently have:
- stepping + binning + stride + ROI
- THRESHOLD_WIDTH diameter method
- serial + threaded backends (chunked) and QC scaffolding
- plotting utilities (matplotlib + plotly dict)

Next step: implement a second method: **GRADIENT_EDGES** using a smoothed 1D gradient to detect left/right walls.

Also update plotting conventions:
- Raw kymograph arrays are always `shape == (time, space)`.
- For display, plot image as **transpose()** so plot x-axis is time and y-axis is space.
- Use physical units when metadata exists: x in seconds, y in micrometers; fallback to pixels.

## Scope (STRICT)

### Allowed edits
- `kymflow/sandbox/diameter-analysis/**`

### Forbidden edits
- Anything outside `kymflow/sandbox/diameter-analysis/`

## Requirements

### R1: Add new diameter method enum
Add enum value:
- `DiameterMethod.GRADIENT_EDGES = "gradient_edges"`

Keep "one method per run" (no multi-method outputs in a single result).

### R2: Params for gradient method (configurable smoothing)
Extend `DiameterDetectionParams` to include gradient-specific parameters:

- `gradient_sigma: float` (default reasonable value; must be configurable)
- `gradient_kernel: str` optional (default `"central_diff"`), but OK to omit if not needed
- Any other params required for robust peak finding must be explicit and documented.

### R3: Implement GRADIENT_EDGES algorithm (per 1D spatial profile)
For each binned 1D profile (after polarity normalization):
1) Smooth profile with Gaussian filter using `gradient_sigma`.
   - Use SciPy if available (`scipy.ndimage.gaussian_filter1d`) or a small fallback implementation.
2) Compute first derivative along space axis using a central difference.
3) Find edges:
   - Left edge = index of global maximum of derivative (strongest positive slope)
   - Right edge = index of global minimum of derivative (strongest negative slope)
4) Validate:
   - If left >= right → mark invalid; set edges/diameter to NaN; set QC flags.
5) Diameter:
   - `diameter_px = right_edge_px - left_edge_px`
   - keep pixel-level edges/diameter for this ticket (no subpixel refinement).

### R4: QC updates for gradient method
Reuse existing QC structure and add:

- `edge_strength_left` and `edge_strength_right` (e.g., abs(derivative at edge))
- Add QC flags:
  - `gradient_invalid_order`
  - `gradient_low_edge_strength` (if below threshold heuristic)

Update `qc_score` weighting to incorporate edge strengths in a simple, documented way.

### R5: Plotting must use transpose() for image display + physical units
Update `diameter_plots.py`:

#### Image plotting (mpl + plotly dict)
- Always compute a display image as:
  - `img_disp = kymograph.transpose()`
- Plot coordinates:
  - x-axis is time (seconds if `seconds_per_line` given, else row index)
  - y-axis is space (um if `um_per_pixel` given, else column index)
- Axis labels MUST reflect this:
  - x label: "time (s)" (or "time (rows)" fallback)
  - y label: "space (um)" (or "space (px)" fallback)

#### Edge overlays must match transpose coordinate system
- Each result is one time point; overlay edges as:
  - x = `time_s` (or `center_row` if missing)
  - y = `left_edge_um/right_edge_um` (or px fallback)
- Ensure overlay lines align with the transposed image.

#### Diameter-vs-time plots
- x is time (s), y is diameter (um preferred, else px).
- Keep existing composable API (optional ax for mpl; dict return for plotly).

### R6: Tests
Add pytest coverage verifying:

1) Gradient method runs end-to-end on deterministic synthetic data:
   - `diameter_method=GRADIENT_EDGES` returns results with valid ordering for most windows.
2) Accuracy check with parameterized tolerance (use synthetic truth):
   - compare predicted `diameter_px` vs `truth_diameter_px` over emitted centers,
   - allow a looser tolerance than threshold-width if needed.
3) Plot orientation sanity test (lightweight):
   - Ensure plotting helpers call `transpose()` (not `.T`) by verifying output shape assumptions:
     - For mpl, the rendered image array should be `space x time` (you may check internal array shape before plotting).
     - For plotly dict, ensure `z` passed into heatmap/image is `img_disp` with shape `(space, time)`.

### R7: Example script update
Update `run_example.py` to allow quick switching between:
- THRESHOLD_WIDTH
- GRADIENT_EDGES

Produce both stacked plots (mpl + plotly dict summaries), using transpose-aware plotting.

## Acceptance criteria
- `uv run pytest -q` passes.
- `uv run python run_example.py` runs and produces:
  - stacked 2×1 mpl view with correct axis conventions (x=time, y=space),
  - plotly dict summaries for the same.
- `GRADIENT_EDGES` works for both `backend="serial"` and `backend="threads"`.
- Plotting uses `transpose()` (not `.T`) and overlays match the transposed coordinate system.
- No edits outside the allowed scope.

## Validation commands
- `uv run pytest -q`
- `uv run python run_example.py`

## Codex implementation report
Save:
- `kymflow/sandbox/diameter-analysis/tickets/ticket_003_gradient_edges_codex_report.md`
