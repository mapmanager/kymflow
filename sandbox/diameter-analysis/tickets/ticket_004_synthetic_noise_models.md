# ticket_004.md — SyntheticKymographParams + explicit noise models + 11-bit/uint16 realism + bright band artifact

## Mode
Exploration

## Context
Current synthetic kymograph output is float64 in [0,1] (e.g., min=0.0 max=1.0), but real data are stored as uint16 with an ~11-bit effective range (0..2047) and a nonzero baseline (pixels are never black due to autofluorescence + detector physics). We need systematic and reproducible control over synthetic generation, including:

- explicit baseline offset,
- background noise and foreground noise controls (toggle + params),
- optional saturation/clipping,
- a stable bright band artifact (non-biological, often saturated, fixed-ish x location),
- ability to output either float or uint16 quantized data,
- serialization of synthetic-generation parameters (like detection params) so datasets are reproducible.

This ticket adds a dedicated parameters dataclass and expands `synthetic_kymograph.py` accordingly, while keeping current default behavior backward compatible (existing tests should keep passing or be updated with minimal changes).

## Scope (STRICT)

### Allowed edits
- `kymflow/sandbox/diameter-analysis/**`

### Forbidden edits
- Anything outside `kymflow/sandbox/diameter-analysis/`

## Requirements

### R1: Add `SyntheticKymographParams` dataclass with to_dict()/from_dict()
Create a new dataclass (new file OK, e.g. `synthetic_params.py`, or keep in `synthetic_kymograph.py`) with:
- Shape/metadata:
  - `n_time: int`
  - `n_space: int`
  - `seconds_per_line: float`
  - `um_per_pixel: float`
  - `polarity: str` ("bright_on_dark" | "dark_on_bright")
  - `seed: int`
- Intensity model / quantization:
  - `output_dtype: str` in {"float32","float64","uint16"} (default should preserve current behavior)
  - `effective_bits: int` (default 11; used when output_dtype=="uint16")
  - `baseline_counts: float` (nonzero baseline offset in counts; default should preserve current float baseline unless explicitly enabled)
  - `signal_peak_counts: float` (target peak above baseline, in counts; only used for quantized mode)
  - `clip: bool` (whether to clip/saturate to max range before casting; important for realism)
  - derived:
    - `max_counts = (2**effective_bits - 1)` when effective_bits provided
- Background noise toggles/params (all optional; defaults off or match current behavior):
  - `bg_gaussian_sigma_counts: float` (additive Gaussian noise in counts)
  - `bg_gaussian_sigma_frac: float | None` (optional convenience as fraction of signal_peak_counts; if provided convert to counts)
  - `bg_drift_amp_counts: float` and `bg_drift_period_lines: int` (slow baseline drift over time)
  - `fixed_pattern_col_sigma_counts: float` (per-column fixed pattern noise)
- Foreground noise / artifacts toggles/params:
  - `speckle_sigma_frac: float` (multiplicative noise as fraction; applied to signal component)
  - `wall_jitter_px: float` (jitter left/right boundaries over time; may be per-line iid or random walk; document choice)
  - Bright band artifact (stable along time, semi-fixed x):
    - `bright_band_enabled: bool`
    - `bright_band_x_center_px: int`
    - `bright_band_width_px: int`
    - `bright_band_amplitude_counts: float` (added to intensity before clipping)
    - `bright_band_saturate: bool` (if True, ensure it reaches max_counts when quantized+clip enabled)

Notes:
- Document clearly what `baseline_counts` and `signal_peak_counts` mean:
  - baseline_counts: constant offset added everywhere (camera offset + autofluorescence)
  - signal_peak_counts: target signal amplitude ABOVE baseline in counts (helps scale float model into counts)
- Defaults must preserve existing behavior when params not provided (float in [0,1], minimal noise).

### R2: Update `generate_synthetic_kymograph(...)` to accept params
Modify synthetic generator so callers can either:
- pass the existing simple arguments (backward compatible), OR
- pass a `SyntheticKymographParams` instance (preferred).

The function must return a payload dict that includes:
- `"kymograph": np.ndarray`
- `"meta": {"seconds_per_line": ..., "um_per_pixel": ..., "polarity": ...}`
- `"truth": { ... }` (keep existing truth_diameter_px if present)
- `"synthetic_params": <SyntheticKymographParams.to_dict()>`  (NEW; always include)

### R3: Implement baseline offset + quantization pipeline
Implement synthetic image generation in float space, then (optionally) quantize:

1) Build an idealized float image (signal component + baseline component).
2) Apply noise/artifacts in a well-defined order (document it):
   - baseline offset
   - background drift
   - fixed pattern
   - additive gaussian
   - speckle (multiplicative on signal component)
   - bright band artifact (additive, then optional saturate)
   - final clipping
3) If `output_dtype` is uint16:
   - Convert float model to counts using baseline_counts + signal_peak_counts scaling.
   - Apply clipping to [0, max_counts] if `clip=True`.
   - Cast to `np.uint16`.

Important:
- Even if output is uint16, keep calculations in float internally to avoid uint overflow/wraparound.

### R4: Bright band artifact behavior (decision)
Implement bright band as **additive in counts** (adds to existing intensity) and then rely on clipping/saturation to emulate camera max.
- If `bright_band_saturate=True` and quantized+clip enabled, ensure the band reaches `max_counts` (e.g., by setting amplitude sufficiently high or explicitly clamping band region to max_counts).

### R5: Detection algorithm safety check (no hardcoded thresholds)
Add a lightweight safeguard to analysis code:
- Ensure profiles are converted to float before processing (if they aren’t already).
- Add a small doc note and/or assertion that no code assumes intensities are in [0,1].
- Search for any hardcoded absolute thresholds and remove/parameterize them.
  - Half-max and percentile-based methods are fine.
  - Any fixed numeric threshold must be clearly documented and tied to params (counts or fractions).

### R6: Docs update
Update `docs/dev_notes.md` (or add a new doc `docs/synthetic.md`) documenting:
- intensity model (float vs counts vs uint16 quantization),
- meaning of baseline_counts and signal_peak_counts,
- each noise model toggle and its effect,
- recommended parameter ranges for 11-bit effective counts.

### R7: Tests
Add pytest coverage:
1) Backward compatibility:
   - calling `generate_synthetic_kymograph()` with no params still returns float in [0,1] (or consistent with existing baseline behavior).
2) Quantized mode:
   - with `output_dtype="uint16"` and `effective_bits=11`, output dtype is uint16 and max <= 2047 when clip=True.
   - baseline is nonzero when baseline_counts > 0.
3) Bright band:
   - when enabled + saturate, the band region hits max_counts (for quantized mode with clip).
4) Determinism:
   - same seed + params → identical output array and truth.
5) Analysis tolerance sanity (optional but recommended):
   - run a small analysis pass on quantized synthetic and ensure it does not crash and returns finite results for many windows.

### R8: Example script additions (opt-in)
Update `run_example.py` to optionally demonstrate:
- float mode vs uint16 (11-bit) mode
- enabling baseline + bright band
Do NOT change the default example behavior unless necessary to keep tests consistent.

## Acceptance criteria
- `uv run pytest -q` passes.
- `uv run python run_example.py` runs.
- Synthetic generator can produce:
  - current default float output (backward compatible),
  - uint16 output constrained to 11-bit max when requested,
  - nonzero baseline when requested,
  - saturated bright band artifact when requested.
- Synthetic params are serialized in output payload (`synthetic_params` key).
- No edits outside allowed scope.

## Validation commands
- `uv run pytest -q`
- `uv run python run_example.py`

## Codex implementation report
Save:
- `kymflow/sandbox/diameter-analysis/tickets/ticket_004_synthetic_noise_models_codex_report.md`
