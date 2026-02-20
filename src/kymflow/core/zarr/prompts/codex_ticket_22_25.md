# Codex Ticket 22–25

## Title
Event-Detection “0 results” correctness + Radon (ROI-based) Indexer v0.1

Repo: `kymflow`  
Branch: `kymflow-zarr`

This bundle addresses a critical edge case for **event detection** analyses (like velocity events):
- A valid run can produce **0 events**
- We must persist “analysis ran and found 0 events” so incremental/staleness does NOT rerun forever

Then we implement the first ROI-driven indexer (Radon) to validate:
- params_hash includes ROI envelope
- ROI edits trigger staleness

---

## Architectural Rules (critical)

- Do NOT put kymflow-specific analysis into `kymflow_zarr`.
- `KymDataset` and all indexers live in `kymflow.core`.
- Avoid broad `except Exception` unless re-raised immediately.
- Public APIs: type hints + Google-style docstrings.

---

# Ticket 22 — Introduce “analysis run marker” concept for empty-result analyses

## Problem
In `mode="incremental"`, KymDataset decides “skip” based on existing table rows for `image_id`.
For event detection, a correct result may be **0 rows**, which looks identical to “never computed”.

## Goal
Add a minimal, generic mechanism to persist “computed” even when the result table is empty.

## Requirements

### A) Per-record summary artifact (recommended v0.1)
For any event-detection indexer, persist a per-record JSON summary artifact with:
- `analysis_version`
- `params_hash`
- `computed_utc` or `computed_local_epoch_ns` (optional)
- `n_events` (integer)

This summary must be written even when `n_events == 0`.

### B) Indexer hook to read the marker
Extend the indexer protocol **optionally** (do not break existing indexers):
- Add optional method:
  - `def load_run_marker(self, rec: ZarrImageRecord) -> dict[str, object] | None:`
  - returns marker dict if present else None

Alternative acceptable: expose a helper function specific to velocity events, but prefer a generic optional hook.

### C) KymDataset incremental logic enhancement
In `mode="incremental"`:
- If there are **existing rows** for image_id:
  - current logic remains: compare `params_hash` + `analysis_version`
- If there are **no existing rows**:
  - consult `indexer.load_run_marker(rec)`
  - if marker exists and matches `params_hash` + `analysis_version`:
    - treat as **skippable** (computed with 0 rows)
  - else:
    - recompute

### Tests
Add tests that prove:
- event detection with 0 rows is considered computed and is skippable in incremental mode
- changing params invalidates marker and triggers recompute

---

# Ticket 23 — Update VelocityEventIndexer to support run marker + empty results

## Goal
Ensure velocity events indexer writes/reads the run marker and that empty events do not trigger perpetual recompute.

## Requirements
1) Define canonical artifact keys (align with your current conventions):
- params: `velocity_events/params` (JSON)
- events: `velocity_events/events` (parquet) — may be empty table with schema
- marker: `velocity_events/summary` (JSON)

2) Implement in `VelocityEventIndexer`:
- `load_run_marker(rec)` reads `velocity_events/summary` and returns dict
- Ensure `extract_rows(rec)` can return an empty DataFrame with a stable schema (columns present)
- Add helper (can be internal to indexer):
  - `def write_run_marker(rec, *, params_hash, analysis_version, n_events) -> None`
  - This may be used by pipeline code later; for v0.1 tests can write it directly.

3) Update/extend tests:
- Create record with params + marker n_events=0 + empty events parquet
- Run `KymDataset.update_index(..., mode="replace")`
  - table rows for that image_id should be 0
- Run again `mode="incremental"` and assert it skips due to marker

Notes:
- It is OK if the marker is written by the pipeline rather than indexer; but the indexer must be able to read it.
- Prefer storing empty parquet for events so schema remains stable.

---

# Ticket 24 — Implement RadonIndexer (ROI-driven) with ROI included in params_hash

## Goal
Add a second real indexer that is ROI-driven to validate the “ROI edits invalidate results” story.

## Requirements
1) Add module:
- `src/kymflow/core/kym_dataset/indexers/radon.py`

2) Implement `RadonIndexer(BaseIndexer)`:
- `name = "radon"`
- `analysis_version()` returns stable string
- `params_hash(rec)` MUST include ROI envelope (or a hash of it) if ROI is used in analysis
  - For v0.1, choose one:
    - include `roi.to_dict()` in the params dict before hashing
    - OR include `roi_hash` derived from stable_json_dumps(roi_envelope)
- `extract_rows(rec)`:
  - reads per-record radon results artifacts (use existing conventions if present)
  - returns a DataFrame (radon will normally have rows)

3) Artifacts (v0.1 conventions if none exist yet):
- params: `radon/params` (JSON)
- results: `radon/results` (parquet)
- marker (optional): `radon/summary` (JSON) (not required if results always non-empty)

4) Tests:
- Create record with radon params that include ROI id/envelope and results parquet
- Build dataset table via KymDataset
- Mutate ROI geometry (or params) to change params_hash and assert incremental recomputes

(For tests, it’s OK to fabricate radon results parquet; we’re validating framework + provenance, not radon math.)

---

# Ticket 25 — Demo scripts: empty-event correctness + ROI invalidation

## Add / update demo scripts
1) `src/kymflow/core/zarr/examples/demo_kymdataset_velocity_events_empty_v01.py`
- Create dataset with 1 record
- Write params + marker with n_events=0 + empty events parquet
- Run update_index replace then incremental and print updated/skipped/missing

2) `src/kymflow/core/zarr/examples/demo_kymdataset_radon_roi_staleness_v01.py`
- Create dataset with 1 record + RectROI
- Write radon params including ROI envelope + radon results parquet
- Run incremental once (skip)
- Edit ROI geometry in metadata, update params/marker, run incremental again and show it recomputes

---

## Commands to run (acceptance)
- `uv run pytest src/kymflow/core/zarr/tests -q`
- `uv run pytest src/kymflow/core/kym_dataset/tests -q`
- Run demos:
  - `uv run python src/kymflow/core/zarr/examples/demo_kymdataset_velocity_events_empty_v01.py`
  - `uv run python src/kymflow/core/zarr/examples/demo_kymdataset_radon_roi_staleness_v01.py`

---

## Acceptance Criteria
- Incremental mode does NOT rerun velocity events when n_events=0 and marker matches.
- Changing velocity event params triggers recompute.
- Radon indexer incremental skip works; ROI edit triggers recompute.
- No storage-layer coupling added to `kymflow_zarr`.
