# ticket_007.md — Post-processing filters for 1D diameter time series (median + Hampel)

## Mode
Exploration

## Context
Diameter detection can contain occasional single-sample “pops” (spikes) in the 1D time series outputs. We want an explicit, optional post-analysis filtering stage that:

- is configurable via a dataclass (like detection params),
- can be turned on/off,
- supports filter type selection (enum),
- ignores NaNs (does not spread them),
- defaults to no NaN filling,
- preserves raw results (never lose information),
- writes both raw + filtered outputs for reproducibility,
- integrates into plotting (option to show filtered by default, raw optional).

We will implement two filters now:
- Median filter (kernel=3 default)
- Hampel filter (robust outlier replacement using median/MAD)

## Scope (STRICT)

### Allowed edits
- `kymflow/sandbox/diameter-analysis/**`

### Forbidden edits
- Anything outside `kymflow/sandbox/diameter-analysis/`

## Requirements

### R1: Add filter enum + dataclass with serialization
Add:

- `PostFilterType` enum:
  - `MEDIAN = "median"`
  - `HAMPEL = "hampel"`

- `PostFilterParams` dataclass with `to_dict()/from_dict()`:
  - `enabled: bool = False`
  - `filter_type: PostFilterType = PostFilterType.MEDIAN`
  - `kernel_size: int = 3` (odd, >=3) — used by MEDIAN and as Hampel window size
  - Hampel-specific:
    - `hampel_n_sigma: float = 3.0` (threshold)
    - `hampel_scale: str = "mad"` (keep simple; MAD default)

Validation:
- enforce odd kernel size; raise ValueError with clear message.

### R2: Implement NaN-safe median filter
Implement a 1D median filter that:
- does NOT smear NaNs into neighbors,
- does NOT replace NaNs by default,
- filters only valid values using local window valid entries.

Implementation options:
- Use SciPy if available (`scipy.ndimage.median_filter`) ONLY if NaN behavior is correct; otherwise implement explicitly with numpy.

### R3: Implement NaN-safe Hampel filter
Implement Hampel spike filter:
- For each point i with finite value:
  - compute window median (ignoring NaNs)
  - compute MAD (median(|x - median|)) ignoring NaNs
  - convert MAD to sigma estimator (1.4826 * MAD) (document)
  - if |x_i - median| > n_sigma * sigma_est → replace with median
- Keep a boolean mask `replaced_mask` per signal (optional but useful for QC/plot).

Must ignore NaNs and not fill NaNs.

### R4: Apply filters to results (raw + filtered)
Decide on one of these representations (pick the least invasive to current code):
A) Add new columns alongside existing numeric fields when converting to DataFrame/CSV:
   - `diameter_px_filt`, `diameter_um_filt`, etc.
   - Keep `diameter_px` as raw.
B) Or create a parallel Results object for filtered series.

Requirement: preserve raw values and store filtered values.

Minimum signals to filter:
- `diameter_px` (and derived `diameter_um` if present)
Optionally also filter:
- `left_edge_px`, `right_edge_px` (only if it improves stability; document choice)
If you filter edges, ensure `right >= left` remains true (otherwise keep raw edges and only filter diameter).

### R5: Persist post-filter params in sidecar JSON
When saving analysis:
- include `post_filter_params` serialized dict alongside detection params.
- If results are saved as CSV:
  - include filtered columns or generate a second CSV with suffix `_filtered.csv`.
  - Prefer single CSV with both raw+filtered columns to reduce file sprawl.

### R6: Plotting integration
Update plotting functions so:
- default plots use filtered diameter if available and filter enabled
- provide a simple toggle/parameter to show raw series as well

Do not change transpose convention for kymograph image (already established).

### R7: Tests
Add tests:
1) Median filter removes a single spike without shifting baseline:
   - create series with one big spike; verify filtered value at spike ~ neighborhood median.
2) Hampel filter replaces spikes and returns a correct replaced_mask.
3) NaN handling:
   - series with NaNs; ensure NaNs remain NaN and do not contaminate neighbors.
4) Determinism:
   - filters deterministic for same input.

### R8: Example usage
Update `run_example.py` (or a small demo script) to show:
- raw diameter
- filtered diameter
- note filter type and params in printed summary

## Acceptance criteria
- `uv run pytest -q` passes.
- Filter can be enabled/disabled.
- Both median and Hampel implemented and selectable.
- NaNs are not spread; no NaN fill by default.
- Raw + filtered results preserved and saved.
- Plotting can show filtered series (default) and raw optionally.

## Validation commands
- `uv run pytest -q`
- `uv run python run_example.py`

## Codex implementation report
Save:
- `kymflow/sandbox/diameter-analysis/tickets/ticket_007_post_filter_diameter_codex_report.md`
