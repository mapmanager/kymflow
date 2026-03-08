# Ticket 040 — Persist detection params in JSON per run; load into runtime + GUI

## Goal
When saving analysis for a kymimage, persist the **exact** `DiameterDetectionParams` used for each `(roi_id, channel_id)` run into the `.diameter.json`, and on load:
- restore those params into runtime,
- and in the GUI populate the Detection Params editor with loaded values (no autosave behavior).

## Requirements
### A. Save params (JSON)
- Under each run key (e.g. `roi1_ch1`), store:
  - `detection_params`: `DiameterDetectionParams.to_dict()` (or equivalent stable dict)
  - (optionally) `post_filter_params` if that’s part of the current pipeline
- No defaults/back-compat: if missing during load, **fail fast** (schema is new; pipeline expects it).

### B. Load params (runtime)
- On load of sidecars, parse `detection_params` back into `DiameterDetectionParams`.
- Ensure runtime controller state uses these loaded params as the active detection params.

### C. GUI: load on file select
When user selects a file:
1. load TIFF (already happens),
2. if `.diameter.json` and `.diameter.csv` exist:
   - load analysis bundle,
   - set controller/state results,
   - set controller/state detection params to the loaded values,
   - refresh plots and detection params UI.

### D. UX on save
- Save only when user clicks “Save analysis”.
- On successful save, `ui.notify` should show **filenames only** (not full paths), e.g.:
  - `Saved: cell10_C001T001.diameter.json, cell10_C001T001.diameter.csv`

## Acceptance criteria
1. Save writes detection params into JSON for each run.
2. Load restores detection params exactly.
3. GUI file selection loads existing analysis + params and updates plots/UI.
4. No defaulting of missing params/ids; missing required keys raises.

## Files likely involved
- `sandbox/diameter-analysis/diameter_analysis.py`
- `sandbox/diameter-analysis/gui/controllers.py`
- `sandbox/diameter-analysis/gui/views.py` (only if wiring is needed)
- tests: extend round-trip serialization tests

