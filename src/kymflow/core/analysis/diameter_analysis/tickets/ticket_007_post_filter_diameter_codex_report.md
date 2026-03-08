# ticket_007_post_filter_diameter implementation report

Final report path written:
- kymflow/sandbox/diameter-analysis/tickets/ticket_007_post_filter_diameter_codex_report.md

## Summary of what changed
- Added optional post-processing filters for diameter time series via new enum/dataclass:
  - `PostFilterType` (`median`, `hampel`)
  - `PostFilterParams` with serialization and validation.
- Implemented NaN-safe median and Hampel filters that do not fill/spread NaNs.
- Preserved both raw and filtered values in results and CSV sidecar (`diameter_px` + `diameter_px_filt`).
- Added persistence of post-filter params in params JSON (`post_filter_params`).
- Integrated plotting defaults to filtered diameter with optional raw overlay.
- Added tests for median/Hampel behavior, NaN handling, determinism, analysis integration, and save/load roundtrip.
- Updated `run_example.py` to demonstrate filter params and raw/filtered summary.

## A) Modified code files
- `kymflow/sandbox/diameter-analysis/diameter_analysis.py`
- `kymflow/sandbox/diameter-analysis/diameter_plots.py`
- `kymflow/sandbox/diameter-analysis/run_example.py`
- `kymflow/sandbox/diameter-analysis/__init__.py`
- `kymflow/sandbox/diameter-analysis/tests/test_ticket_007_post_filter_diameter.py`

## B) Artifacts created
- `kymflow/sandbox/diameter-analysis/tests/test_ticket_007_post_filter_diameter.py`
- `kymflow/sandbox/diameter-analysis/tickets/ticket_007_post_filter_diameter_codex_report.md`

## File-by-file list of changes
- `diameter_analysis.py`
  - Added `PostFilterType` enum and `PostFilterParams` dataclass (`to_dict`/`from_dict`).
  - `analyze(...)` now accepts `post_filter_params` and applies filtering when enabled.
  - Added NaN-safe filter implementations:
    - `_nan_safe_median_filter(...)`
    - `_nan_safe_hampel_filter(...)`
  - Added `_apply_post_filter(...)` to update per-result filtered values and replacement mask.
  - Extended `DiameterResult` with:
    - `diameter_px_filt`
    - `diameter_was_filtered`
  - CSV save/load now includes filtered columns (`diameter_px_filt`, `diameter_um_filt`) and replacement mask.
  - Params JSON save/load now includes `post_filter_params` mapping by ROI.
  - `plot(...)` now supports `use_filtered` and `show_raw` toggles.
- `diameter_plots.py`
  - `plot_diameter_vs_time_mpl(...)` and plotly dict variant now default to filtered diameter and can overlay raw.
- `run_example.py`
  - Added `PostFilterParams` usage (Hampel example) and summary print of filter settings/replacements.
  - Plots now request filtered-with-raw-overlay behavior.
- `__init__.py`
  - Exported `PostFilterType`, `PostFilterParams`, and existing `SyntheticKymographParams`.
- `tests/test_ticket_007_post_filter_diameter.py`
  - Added required filter-specific tests (median, Hampel, NaN behavior, determinism, integration, persistence).

## C) Unified diff (short)
### `sandbox/diameter-analysis/diameter_analysis.py`
```diff
+class PostFilterType(str, Enum):
+    MEDIAN = "median"
+    HAMPEL = "hampel"
+
+@dataclass(frozen=True)
+class PostFilterParams:
+    enabled: bool = False
+    filter_type: PostFilterType = PostFilterType.MEDIAN
+    kernel_size: int = 3
+    hampel_n_sigma: float = 3.0
+    hampel_scale: str = "mad"
```

```diff
+    def _nan_safe_median_filter(...):
+        # ignores NaNs and does not fill NaNs
+
+    def _nan_safe_hampel_filter(...):
+        # robust MAD-based spike replacement
+
+    def _apply_post_filter(...):
+        # writes diameter_px_filt and diameter_was_filtered
```

### `sandbox/diameter-analysis/diameter_plots.py`
```diff
 def plot_diameter_vs_time_mpl(...,
+    use_filtered: bool = True,
+    show_raw: bool = False,
 ):
-    diameter = right_space - left_space
+    diameter_raw = right_space - left_space
+    diameter_filt = ...
+    diameter = diameter_filt if use_filtered else diameter_raw
```

### `sandbox/diameter-analysis/run_example.py`
```diff
+from diameter_analysis import ..., PostFilterParams, PostFilterType
@@
-    results = analyzer.analyze(params=params, backend="threads")
+    results = analyzer.analyze(
+        params=params,
+        backend="threads",
+        post_filter_params=post_filter_params,
+    )
+    print("post filter:", ...)
```

### `sandbox/diameter-analysis/tests/test_ticket_007_post_filter_diameter.py`
```diff
+def test_nan_safe_median_filter_removes_single_spike() -> None: ...
+def test_hampel_filter_replaces_spikes_and_mask() -> None: ...
+def test_filters_keep_nans_and_no_nan_spread() -> None: ...
+def test_filter_determinism() -> None: ...
```

## D) Search confirmation
Searched patterns:
- `PostFilterType|PostFilterParams|diameter_px_filt|diameter_was_filtered|post_filter_params|_nan_safe_median_filter|_nan_safe_hampel_filter|use_filtered|show_raw`

Result:
- New post-filter API, runtime integration, persistence fields, and plotting toggles are present in expected files.
- No edits outside `kymflow/sandbox/diameter-analysis/`.

## E) Validation commands run
Executed from `kymflow/sandbox/diameter-analysis/`:

1. `uv run pytest -q`
- Result: pass
- Output: `23 passed, 1 warning in 0.78s`

2. `uv run python run_example.py`
- Result: pass
- Output includes post-filter summary lines for both methods (raw + filtered counts and replacement count).

## F) Summary of changes
- Added configurable, optional post-filter stage.
- Added NaN-safe median and Hampel filters.
- Preserved and persisted both raw and filtered diameter outputs.
- Updated plotting defaults to filtered with optional raw.
- Added targeted tests and updated example usage.

## G) Risks / tradeoffs
- Median filter currently compares raw vs filtered with `np.isclose` to infer replacement mask; this is practical but threshold-free.
- Filtering only applies to diameter (not edges) by design to avoid left/right ordering regressions.

## H) Self-critique
- Pros: minimal invasive integration, backward-compatible defaults, comprehensive ticket-focused tests.
- Cons: did not add separate visual QC marker overlays for replaced points; could be a future enhancement.

## Scope confirmation
No files outside `kymflow/sandbox/diameter-analysis/` were modified.
