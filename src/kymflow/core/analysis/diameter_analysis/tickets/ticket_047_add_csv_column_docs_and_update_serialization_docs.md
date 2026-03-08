
# Ticket 047 — Add user documentation for diameter CSV columns and update serialization docs

## Goal
Provide end-user documentation for the `.diameter.csv` file and update serialization docs so they match the current save/load contract.

Contract (already implemented):
- JSON sidecar = metadata only
- CSV = numeric analysis results source of truth

This ticket adds documentation only.

---

# Part 1 — Create CSV column documentation

Create:

docs/diameter_csv_columns.md

The document must list every column written to `.diameter.csv`.

Explain:

- each row corresponds to one `time_s`
- `time_s` is the global time axis of the kymograph
- ROI columns use suffix `_roi{roi_id}`

Document column groups:

Time axis
Edge positions
Diameter values
Intensity values
Edge strength
Quality control fields

Use tables with columns:

Column | Units | Description

---

# Part 2 — Update serialization documentation

Update:

docs/multi_run_serialization.md

Ensure it describes the finalized contract:

JSON (.diameter.json):
- schema_version
- source_path
- rois
    - roi_id
    - roi_bounds_px
    - channel_id
    - detection_params

CSV (.diameter.csv):
- numeric analysis results

Add example JSON structure.

Clarify:

CSV is the authoritative numeric data.
JSON records analysis metadata.

---

# Acceptance Criteria

- docs/diameter_csv_columns.md exists
- multi_run_serialization.md reflects metadata-only JSON design
- no code changes
