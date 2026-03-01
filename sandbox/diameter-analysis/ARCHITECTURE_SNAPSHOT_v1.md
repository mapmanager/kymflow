# ARCHITECTURE_SNAPSHOT_v1

## 1) Scope and invariants
- Domain: diameter estimation from kymograph arrays.
- Axis convention (hard invariant): `dim0 = time`, `dim1 = space`.
- Computation invariant: all core analysis is done in pixel units (`px`), and conversion to microns (`um`) is performed only at output/finalization.
- Input expectations: 2D NumPy array with shape `(n_time, n_space)` and finite numeric values.
- Polarity invariant: supported values are `"bright_on_dark"` (default) and `"dark_on_bright"`.

## 2) Module and file roles
- `diameter_analysis.py`
  - Core OO API (`DiameterAnalyzer`) and parameter dataclass (`DiameterDetectionParams`).
  - Analysis entrypoint, lightweight persistence helpers, and plotting delegation.
- `synthetic_kymograph.py`
  - Deterministic synthetic kymograph generator for repeatable development/tests.
- `diameter_plots.py`
  - Composable plotting helpers.
  - Matplotlib render functions and Plotly dict-first payload builders.
- `run_example.py`
  - Minimal runnable script to show end-to-end skeleton usage.
- `tests/`
  - Pytest-based validation for synthetic generation, skeleton analysis, and params serialization.
- `docs/`
  - Usage notes and developer design notes.

## 3) Primary public API (v1 scaffold)
- `DiameterDetectionParams`
  - Dataclass for detection knobs.
  - `to_dict()` / `from_dict()` for stable JSON-compatible transport.
- `DiameterAnalyzer`
  - `__init__(kymograph, *, seconds_per_line, um_per_pixel, polarity="bright_on_dark")`
  - `analyze(params=None) -> dict`
  - `save_analysis(output_prefix, analysis, params)`
  - `load_analysis(output_prefix) -> dict`
  - `plot(analysis, *, backend="matplotlib")`
- Synthetic utility:
  - `generate_synthetic_kymograph(...) -> dict`

## 4) IO and sidecar conventions
- Prefix-based sidecars:
  - Parameters JSON: `<prefix>_params.json`
  - Results CSV: `<prefix>_results.csv`
- JSON (params): serialized `DiameterDetectionParams` dictionary.
- CSV (results): columns intended to include `time_s`, `diameter_px`, `diameter_um`.
- In `ticket_001`, this is a light scaffold and not a finalized schema contract.

## 5) Validation commands
Run from `kymflow/sandbox/diameter-analysis/`:
- `uv run pytest -q`
- `uv run python run_example.py`
