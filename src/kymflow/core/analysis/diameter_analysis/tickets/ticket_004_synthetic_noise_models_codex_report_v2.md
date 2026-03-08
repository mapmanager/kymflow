# ticket_004_synthetic_noise_models implementation report

Final report path written:
- `kymflow/sandbox/diameter-analysis/tickets/ticket_004_synthetic_noise_models_codex_report_v2.md`

## Summary of changes
- Added `SyntheticKymographParams` dataclass with reproducible serialization via `to_dict()/from_dict()` and derived `max_counts`.
- Expanded `generate_synthetic_kymograph(...)` to support both legacy args and a params-object path, with serialized `synthetic_params` in output payload.
- Implemented count-domain noise/artifact pipeline (baseline, drift, fixed pattern, additive gaussian, speckle, bright-band, clipping, dtype conversion).
- Added uint16 quantized realism for 11-bit output and bright-band saturation support.
- Added analysis safeguard note and removed hardcoded [0,1]-style saturation assumptions in QC.
- Added synthetic modeling documentation and test coverage for compatibility, quantization, bright band, determinism, and analysis-on-quantized data.

## A) Modified code files
- `kymflow/sandbox/diameter-analysis/synthetic_kymograph.py`
- `kymflow/sandbox/diameter-analysis/diameter_analysis.py`
- `kymflow/sandbox/diameter-analysis/__init__.py`
- `kymflow/sandbox/diameter-analysis/run_example.py`
- `kymflow/sandbox/diameter-analysis/tests/test_ticket_004_synthetic_noise_models.py`

## B) Artifacts created
- `kymflow/sandbox/diameter-analysis/docs/synthetic.md`
- `kymflow/sandbox/diameter-analysis/tests/test_ticket_004_synthetic_noise_models.py`
- `kymflow/sandbox/diameter-analysis/tickets/ticket_004_synthetic_noise_models_codex_report_v2.md`

## File-by-file list of changes
- `synthetic_kymograph.py`
  - Added `SyntheticKymographParams` dataclass with full noise/quantization config and `max_counts`.
  - Added strict validation for params.
  - Updated generator to accept either old args or `synthetic_params`.
  - Implemented ordered count-domain pipeline and optional uint16 quantization.
  - Added `meta` and always-added `synthetic_params` output keys.
- `diameter_analysis.py`
  - Added explicit comment/assertion behavior that analysis is float-based and not tied to normalized [0,1] input.
  - Replaced hardcoded saturation checks (`<=0.005`/`>=0.995`) with dynamic-range-relative percentile heuristic.
- `__init__.py`
  - Exported `SyntheticKymographParams`.
- `run_example.py`
  - Added opt-in synthetic-noise demo path (`DIAMETER_EXAMPLE_NOISE_DEMO=1`) comparing uint16 realism settings.
  - Made plotting display blocking opt-in (`DIAMETER_EXAMPLE_SHOW=1`) so validation run completes headless.
- `tests/test_ticket_004_synthetic_noise_models.py`
  - Added ticket-required tests for backward compatibility, quantized mode, bright-band saturation, determinism, and analysis sanity.
- `docs/synthetic.md`
  - Added documentation for intensity model, parameter meanings, noise/artifact order, bright-band behavior, and 11-bit parameter ranges.

## C) Unified diff (short)
### `sandbox/diameter-analysis/synthetic_kymograph.py`
```diff
+@dataclass(frozen=True)
+class SyntheticKymographParams:
+    ...
+    output_dtype: OutputDType = "float64"
+    effective_bits: int = 11
+    baseline_counts: float = 0.0
+    signal_peak_counts: float = 2047.0
+    ...
+
+def generate_synthetic_kymograph(..., synthetic_params: SyntheticKymographParams | None = None):
+    ...
+    return {
+        ...,
+        "meta": {...},
+        "synthetic_params": params.to_dict(),
+    }
```

### `sandbox/diameter-analysis/diameter_analysis.py`
```diff
-        saturated = bool(pmin <= 0.005 or pmax >= 0.995)
+        dynamic_range = pmax - pmin
+        if dynamic_range > 0:
+            p01 = float(np.nanpercentile(profile, 1))
+            p99 = float(np.nanpercentile(profile, 99))
+            low_tail = (p01 - pmin) / dynamic_range
+            high_tail = (pmax - p99) / dynamic_range
+            saturated = bool(low_tail < 0.01 or high_tail < 0.01)
+        else:
+            saturated = True
```

### `sandbox/diameter-analysis/__init__.py`
```diff
-from synthetic_kymograph import generate_synthetic_kymograph
+from synthetic_kymograph import SyntheticKymographParams, generate_synthetic_kymograph
@@
+    "SyntheticKymographParams",
```

### `sandbox/diameter-analysis/run_example.py`
```diff
+from synthetic_kymograph import SyntheticKymographParams, generate_synthetic_kymograph
@@
+    if os.environ.get("DIAMETER_EXAMPLE_SHOW", "0") == "1":
+        plt.show()
+    else:
+        plt.close("all")
+    if os.environ.get("DIAMETER_EXAMPLE_NOISE_DEMO", "0") == "1":
+        noisy_params = SyntheticKymographParams(...)
+        noisy_payload = generate_synthetic_kymograph(synthetic_params=noisy_params)
```

### `sandbox/diameter-analysis/tests/test_ticket_004_synthetic_noise_models.py`
```diff
+def test_backward_compatible_default_float_range_and_params_key() -> None:
+    ...
+
+def test_uint16_quantized_11bit_and_nonzero_baseline() -> None:
+    ...
+
+def test_bright_band_saturates_to_max_counts() -> None:
+    ...
```

## D) Search confirmation
Searched patterns:
- `SyntheticKymographParams|synthetic_params|output_dtype|effective_bits|bright_band|bg_gaussian_sigma|signal_peak_counts|baseline_counts`
- `0.995|0.005|[0,1]`

Outcome:
- New synthetic params/noise controls appear in generator, tests, docs, and example.
- Hardcoded QC saturation assumptions tied to [0,1] were removed from active analysis path.
- No out-of-scope files were modified.

## E) Validation commands run
Executed from `kymflow/sandbox/diameter-analysis/`:

1. `uv run pytest -q`
- Result: pass
- Output: `17 passed, 1 warning in 0.72s`

2. `uv run python run_example.py`
- Result: pass
- Output summary:
  - `kym shape: (2000, 80) min:0.0 max:1.0 float64`
  - `method: threshold_width` and `method: gradient_edges` both produced finite outputs.

## F) Summary of changes
- Added synthetic-generation parameters dataclass + serialization.
- Added count-domain synthetic noise/artifact model with optional uint16/11-bit realism.
- Added bright-band artifact saturation behavior.
- Added docs and tests for new synthetic features.
- Removed [0,1]-assumption in QC saturation detection.

## G) Risks / tradeoffs
- Float output now derives from count-domain scaling by default; visually similar but distribution details can differ from earlier legacy normalization.
- `run_example.py` contained existing local modifications before this ticket; changes were limited to ticket requirements and validation robustness.
- Bright-band saturation behavior is deterministic and explicit, but real hardware behavior may include blooming effects not modeled here.

## H) Self-critique
- Pros: meets ticket requirements with reproducible params serialization and robust test coverage.
- Cons: fallback noise model is still simplified; no camera-specific read-noise/shot-noise calibration model yet.
- Drift risk: moderate if later tickets change payload schema keys; current tests lock key behavior.

## Scope confirmation
No files outside `kymflow/sandbox/diameter-analysis/` were modified.
