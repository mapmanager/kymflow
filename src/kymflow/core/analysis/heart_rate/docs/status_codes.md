# Status Codes

This document defines `HRStatus`, the structured status enum used by heart-rate
estimators and pipeline summaries.

## Enum values

- `ok`: estimate path is acceptable for milestone-1 reporting.
- `insufficient_valid`: too few valid samples for a reliable estimate.
- `no_peak_lomb`: Lomb-Scargle did not provide a valid peak in band.
- `no_peak_welch`: Welch did not provide a valid peak in band.
- `method_disagree`: both methods produced estimates but disagree beyond tolerance.
- `other_error`: unexpected processing error.

## Usage notes

- `estimate_heart_rate_global()` includes `dbg["status"]` and optional `dbg["note"]`.
- Pipeline method-level results store `status` and `status_note` per method.
- ROI-level summary status is derived from method statuses plus agreement logic.
- Mini summary serializes status as string (`HRStatus.value`).
