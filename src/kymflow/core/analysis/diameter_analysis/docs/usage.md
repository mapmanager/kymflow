# Usage

Run from this folder:

```bash
uv run python run_example.py
```

This script:
1. Generates a synthetic kymograph (`dim0=time`, `dim1=space`).
2. Runs the skeleton `DiameterAnalyzer.analyze(...)` pipeline.
3. Creates matplotlib figures.
4. Builds Plotly figure dictionaries and prints summary keys.

## Minimal API

```python
from diameter_analysis import DiameterAnalyzer, DiameterDetectionParams
from synthetic_kymograph import generate_synthetic_kymograph

payload = generate_synthetic_kymograph()
analyzer = DiameterAnalyzer(
    payload["kymograph"],
    seconds_per_line=payload["seconds_per_line"],
    um_per_pixel=payload["um_per_pixel"],
    polarity=payload["polarity"],
)
params = DiameterDetectionParams(threshold_fraction=0.5, min_diameter_px=2.0)
analysis = analyzer.analyze(params=params)
```

## Validation

```bash
uv run pytest -q
uv run python run_example.py
```
