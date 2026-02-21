# Codex Ticket 18–21

## Title
Incremental/Staleness Updates + First Real Indexer (Velocity Events) on KymDataset

Repo: `kymflow`  
Branch: `kymflow-zarr`

This ticket bundle builds on Tickets 14–17 (BaseIndexer + KymDataset + table discipline + provenance columns).

---

## Why this exists

We now have:
- `KymDataset.update_index(...)` that rebuilds tables by replacing rows per image_id
- Provenance columns: `image_id`, `analysis_version`, `params_hash`

Next we need:
1) **Incremental mode** so we can skip recompute for unchanged images
2) A **real, domain indexer** (`velocity_events`) that uses the framework

---

## Architectural Rules (critical)

- Do NOT add kymflow-specific logic inside `kymflow_zarr` (storage stays generic).
- `KymDataset` and indexers live in `kymflow.core`.
- Avoid broad `except Exception` (use targeted exceptions or re-raise).
- Public APIs: type hints + Google-style docstrings.

---

# Ticket 18 — Deterministic params hashing utilities

## Goal
Provide one canonical way to compute `params_hash` from a params dict.

## Requirements

1) Add helper module (preferred location):
- `src/kymflow/core/kym_dataset/provenance.py`

2) Implement:
- `def stable_json_dumps(obj: object) -> str`
  - must be deterministic for dict key order and basic types
  - recommended: `json.dumps(..., sort_keys=True, separators=(",", ":"), ensure_ascii=False)`
- `def params_hash(params: dict) -> str`
  - returns `sha256(stable_json_dumps(params).encode("utf-8")).hexdigest()`

3) Tests:
- same dict with different key order yields same hash
- small known params yields stable hash (snapshot string is optional)

---

# Ticket 19 — Incremental mode + staleness checks in KymDataset

## Goal
Add `mode="incremental"` to `KymDataset.update_index` so unchanged rows can be skipped.

## Requirements

1) Modify `KymDataset.update_index(...)` signature to accept:
- `mode: Literal["replace", "incremental"] = "replace"`

2) Incremental algorithm (minimal v0.1):
For each `image_id`:
- compute `current_hash = indexer.params_hash(rec)`
- `current_version = indexer.analysis_version()`
- load existing table (or the per-image slice of it) and find rows where `image_id == ...`
- if existing rows exist AND
  - all existing rows have `params_hash == current_hash` AND
  - all existing rows have `analysis_version == current_version`
  → **skip recompute for this image_id**
- else:
  - compute `df_rows = indexer.extract_rows(rec)`
  - ensure provenance columns exist/are set correctly
  - replace rows for that image_id

3) Logging:
- count `skipped`, `updated`, `missing` (no existing rows)
- log one summary line at end

4) Tests:
- create a tiny dataset with 2 records
- run update_index replace → table has rows
- run update_index incremental (no changes) → skips both
- mutate params_hash result (e.g., by changing the params JSON artifact for one record) → only that record updates

Notes:
- Do NOT implement file-change detection yet (sources mtime/size etc) — this is params/version only.
- It’s OK if `KymDataset` loads full table once and filters per image_id for v0.1.

---

# Ticket 20 — Implement VelocityEventIndexer (first real indexer)

## Goal
Create a concrete indexer that reads per-image velocity event results and builds a dataset table.

## Requirements

1) Add module:
- `src/kymflow/core/kym_dataset/indexers/velocity_events.py`

2) Implement:
- `class VelocityEventIndexer(BaseIndexer):`
  - `name = "velocity_events"`
  - `analysis_version()` returns a stable string (e.g. `"kymflow.velocity_events@0.1"`)
  - `params_hash(rec)`:
    - load params JSON artifact if present; else use defaults
    - use `kymflow.core.kym_dataset.provenance.params_hash(...)`
  - `extract_rows(rec)`:
    - loads per-image artifact(s) representing velocity events
    - returns a DataFrame with required columns plus event columns

3) Decide the per-image artifact names (use existing conventions if present in repo):
- Recommended v0.1 convention (if you don’t already have one):
  - params: `analysis/velocity_events/params.json`
  - results: `analysis/velocity_events/events.parquet` (or `.csv.gz` / `.parquet` whichever your store currently uses)
  - optional summary: `analysis/velocity_events/summary.json`

If your current pipeline already produces artifacts (e.g. via `VelocityEventDb`), adapt the indexer to read those artifacts rather than inventing new ones.

4) Table schema:
- Must include:
  - `image_id`, `analysis_version`, `params_hash`
- Plus event fields (example):
  - `roi_id`, `event_id`, `t_start_s`, `t_end_s`, `peak_t_s`, `peak_value`, `score`, etc.
Use whatever is already present in your existing velocity event report/DB format.

---

# Ticket 21 — Integration tests + demo snippet

## Goal
Prove the first real indexer works end-to-end and benefits from incremental mode.

## Requirements

1) Tests:
- Create a zarr dataset in a temp dir
- Add 1–2 images (toy arrays)
- For each record:
  - write params JSON artifact for velocity_events
  - write events table artifact (parquet preferred)
- Run:
  - `KymDataset.update_index(VelocityEventIndexer(), mode="replace")`
  - Verify dataset table exists: `tables/kym_velocity_events.parquet`
  - Verify expected row count
- Run again with `mode="incremental"` and assert it skips

2) Demo snippet script (small):
- `src/kymflow/core/zarr/examples/demo_kymdataset_velocity_events_v01.py`
  - creates dataset
  - writes a fake per-image events artifact
  - runs KymDataset update_index replace and incremental
  - prints skipped/updated counts

---

## Commands to run (acceptance)
- `uv run pytest src/kymflow/core/zarr/tests -q`
- plus any new tests you place under `src/kymflow/core/kym_dataset/tests`:
  - `uv run pytest src/kymflow/core/kym_dataset/tests -q`
- Run demo:
  - `uv run python src/kymflow/core/zarr/examples/demo_kymdataset_velocity_events_v01.py`

---

## Acceptance Criteria
- All tests pass.
- Demo runs and prints expected behavior (replace then incremental skip).
- No storage-layer coupling added to `kymflow_zarr`.
