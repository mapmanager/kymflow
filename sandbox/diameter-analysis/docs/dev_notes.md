# Developer Notes

## Design notes
- Analysis is intentionally scaffold-level for ticket_001.
- Pixel-first computation is enforced; unit conversion to `um` happens at result packaging.
- Plotting is decomposed into composable functions rather than a monolithic plotting API.
- Plotly output is dict-first to support downstream rendering without hard dependency on figure objects.

## Open questions
- Preferred edge detector for production: thresholding, gradient-based, or model-based?
- Sidecar schema versioning policy for persisted params/results.
- Missing-data handling strategy for low-SNR time points.

## Next steps
- Replace placeholder width estimator with robust edge detection.
- Add synthetic scenarios with motion artifacts and polarity edge cases.
- Add parameter validation constraints and schema version headers for saved artifacts.
