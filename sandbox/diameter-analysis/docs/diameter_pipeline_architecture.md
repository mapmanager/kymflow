# Diameter pipeline architecture (current)

This is a **one-page** view of how diameter analysis flows through the system, end-to-end.

## High-level flow

```text
┌───────────────────────────┐
│ GUI / caller (controller) │
│ - chooses kym image        │
│ - chooses roi_id           │
│ - asks kymflow for bounds  │
│ - chooses channel_id       │
│ - edits DetectionParams    │
└─────────────┬─────────────┘
              │
              │ analyze(..., roi_id, roi_bounds, channel_id, params)
              v
┌───────────────────────────┐
│ DiameterAnalyzer           │
│ 1) validate inputs         │
│    - roi_id, channel_id:   │
│      required, int         │
│    - roi_bounds: required  │
│      (t0,t1,x0,x1)         │
│ 2) crop / extract channel  │
│ 3) detect edges/diameter   │
│    - method-specific       │
│ 4) apply post-processing   │
│    - motion constraints    │
│      (per-constraint bool) │
│ 5) build DiameterResult(s) │
└─────────────┬─────────────┘
              │
              │ list[DiameterResult]
              v
┌───────────────────────────┐
│ In-memory container        │
│ DiameterAnalysisBundle     │
│ - keyed by (roi_id, ch_id) │
│ - stores per-run payload   │
│ - owns serialization rules │
└─────────────┬─────────────┘
              │
              ├───────────────────────────────┐
              │                               │
              │ to_dict() / to_json()          │ bundle_to_wide_csv_rows(...)
              v                               v
┌───────────────────────────┐         ┌──────────────────────────────┐
│ Sidecar JSON               │         │ Flat “wide” CSV               │
│ - full fidelity            │         │ - single header row           │
│ - all params + runs        │         │ - columns encode:             │
│ - schema versioned         │         │   field + roi_id + channel_id │
└─────────────┬─────────────┘         └─────────────┬────────────────┘
              │                                     │
              │ load (next session)                 │ load (next session)
              v                                     v
┌───────────────────────────┐         ┌──────────────────────────────┐
│ DiameterAnalysisBundle     │         │ Bundle reconstruction         │
│ from_dict()/from_json()    │         │ from wide CSV rows            │
│ - must fail fast if missing│         │ - must be drift-safe          │
│   required ids/fields      │         │ - must include time columns   │
└───────────────────────────┘         └──────────────────────────────┘
```

## Contracts we rely on

### Required inputs to analysis
- **roi_id**: required `int`.
- **channel_id**: required `int`.
- **roi_bounds**: required `(t0, t1, x0, x1)` in pixel indices (half-open).
- **params**: `DiameterDetectionParams` describing *how* to detect.

No defaults, no back-compat fallbacks: the pipeline should **fail fast** if anything required is missing or the wrong type.

### What goes into results
Each `DiameterResult` must carry:
- `roi_id` (int)
- `channel_id` (int)
- time axis info (at minimum, enough to map rows to time)
- measured edges/diameter arrays and any additional per-row fields

### Persistence
- **JSON**: authoritative and full fidelity.
- **CSV**: user-friendly export; still must be loadable.
  - We treat CSV as a *structured* artifact: column naming + required fields are part of the contract.

## Current known risk areas (what tickets target)
- **Wide CSV “field registry drift”**: if the set/order of fields changes, CSV load can silently break.
- **Roundtrip guarantees**: bundle → csv/json → bundle should be tested for multi-run (roi, channel).
- **Per-constraint motion gating**: bool flags must actually be respected inside the constraint logic.
