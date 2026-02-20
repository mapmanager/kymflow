# Codex Ticket 30–32 (core-only)

## Title
Incremental/Staleness polish: explicit stats, typed staleness result, run-marker contract, and pandas warning cleanup

Repo: `kymflow`  
Branch: `kymflow-zarr`

Scope constraints:
- **Core-only**: touch only non-UI code under `kymflow/core/kym_dataset` and (if needed) `kymflow_zarr` table replace helper.
- Do **not** modify NiceGUI demos in this ticket batch.

---

## Why

Ticket 26–29 delivered correct behavior, but we want:
1) Unambiguous incremental stats (especially around “0 rows is computed”)
2) A typed staleness result (safer for GUI + future)
3) A single, documented run-marker schema contract used by all event detectors
4) Remove/avoid the pandas concat FutureWarning in replace-row logic

---

# Ticket 30 — Split incremental stats into explicit categories

## Goal
Make `KymDataset.last_update_stats` and logs accurately reflect what happened, without conflating “missing rows” with “computed zero rows”.

## Requirements
1) Replace the current stats shape with explicit counters:
- `updated` (int): rows were recomputed and written (replace_rows executed)
- `skipped_fresh` (int): skipped because table rows exist and match params_hash+analysis_version
- `skipped_zero_rows` (int): skipped because run marker exists and indicates n_rows==0 and matches params_hash+analysis_version
- `stale_missing_marker` (int): stale because no rows and no marker
- `stale_marker_table_mismatch` (int): stale because marker says n_rows==0 but table has rows (or other inconsistency)

Optionally keep:
- `total_images` (int)

2) Ensure logs print a single summary line with all counters.

3) Update tests:
- Existing tests should be updated to assert the correct counters increment for:
  - normal skip
  - zero-row marker skip
  - missing marker stale
  - marker/table mismatch stale

---

# Ticket 31 — Typed staleness result (dataclass) + stable “reason” enums

## Goal
Replace ad-hoc dict staleness results with a typed dataclass for safety and clarity.

## Requirements
1) Create:
- `src/kymflow/core/kym_dataset/staleness.py`

2) Add:
- `class StalenessReason(StrEnum)` or `Enum` (stdlib):
  - `FRESH_ROWS`
  - `FRESH_ZERO_ROWS`
  - `STALE_MISSING_MARKER`
  - `STALE_PARAMS_CHANGED`
  - `STALE_VERSION_CHANGED`
  - `STALE_MARKER_TABLE_MISMATCH`
  - `STALE_UNKNOWN`

3) Add dataclass:
- `@dataclass(frozen=True)`
  - `image_id: str`
  - `table_name: str`
  - `has_run_marker: bool`
  - `table_rows_present: bool`
  - `marker_n_rows: int | None`
  - `params_hash_matches: bool`
  - `analysis_version_matches: bool`
  - `is_stale: bool`
  - `reason: StalenessReason`

4) Update:
- `KymDataset.get_staleness(...)` to return `StalenessResult` instead of dict.

5) Update tests accordingly.

---

# Ticket 32 — Run-marker schema contract + pandas concat warning cleanup

## Part A: Run-marker contract

### Goal
Define and centralize a minimal run-marker schema so all indexers can use it consistently.

### Requirements
1) Add:
- `src/kymflow/core/kym_dataset/run_marker.py`

2) Define:
- `RUN_MARKER_VERSION = "1"`
- Typed helpers:
  - `def make_run_marker(*, indexer_name: str, params_hash: str, analysis_version: str, n_rows: int, ran_utc_epoch_ns: int | None = None, status: str = "ok") -> dict[str, object]`
  - `def validate_run_marker(d: dict[str, object]) -> None` (raise ValueError with helpful message)
  - `def marker_matches(d, *, params_hash, analysis_version) -> bool`

3) Update event indexers (VelocityEventIndexer at minimum) to use these helpers rather than hand-building dicts.

4) Update docs:
- Add a short module docstring explaining meaning and required fields.

## Part B: pandas concat warning cleanup (replace_rows_for_image_id)

### Goal
Avoid the FutureWarning in concat with empty/all-NA entries.

### Requirements
1) Locate the code path producing the warning (likely in `replace_rows_for_image_id`).
2) Fix by:
- If existing table is empty: write `df_rows` directly (after ensuring schema/provenance)
- Else if df_rows is empty: drop existing rows for image_id and write back remaining (no concat)
- Else: proceed with concat

3) Tests:
- case: existing empty + new non-empty
- case: existing non-empty + new empty (should remove rows cleanly)
- case: existing non-empty + new non-empty

---

## Commands / Acceptance
- `uv run pytest src/kymflow/core/zarr/tests -q`
- `uv run pytest src/kymflow/core/kym_dataset/tests -q`

All must pass with no new warnings ideally.

---

## Definition of Done
- Stats are explicit and correct.
- Staleness is a typed dataclass with stable reason enums.
- Run-marker schema is centralized and validated.
- pandas concat FutureWarning eliminated.
