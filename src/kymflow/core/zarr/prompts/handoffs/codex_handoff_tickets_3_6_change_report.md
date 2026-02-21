# Codex Handoff Tickets 3–6 — Strict Technical Change Report

## 1) Branch name used
- `kymflow-zarr` (confirmed via `git rev-parse --abbrev-ref HEAD`)

## 2) Commands run and exact outcomes

Validation commands run for this implementation:

1. `uv run pytest src/kymflow/core/zarr/tests -q`
- Outcome: `..................... [100%]` (all zarr tests passing after Tickets 3–6 changes)

2. `uv run python src/kymflow/core/zarr/examples/demo_export_import_v01.py`
- Outcome: pass
- Observed output includes refresh behavior:
  - initial sources rows `2`
  - refresh ingested one new image id
  - sources rows after refresh `3`

3. `uv run python src/kymflow/core/zarr/examples/demo_gui_flow_v01.py`
- Outcome: pass
- Observed output includes channel API usage (`Channels available: [1]`) and successful ingest/order/metadata print.

Supporting verification commands used:
- `grep -RIn "kymflow.core.utils.logging|get_logger" src/kymflow/core/zarr/src/kymflow_zarr` -> no matches after stdlib logging migration
- `grep -RIn "\.key\b" src/kymflow/core/zarr/tests src/kymflow/core/zarr/examples` -> no runtime use of old `img.key` remained in zarr tests/examples

## 3) Files modified (full relative paths) with per-file details

### Cross-cutting logging migration (Ticket 3)
The following files were changed to replace `get_logger` import/usage with stdlib logging (`import logging`, `logger = logging.getLogger(__name__)`).

1. `src/kymflow/core/zarr/src/kymflow_zarr/__init__.py`
- What: logger import/assignment switched to stdlib logging.
- Why: remove dependency on `kymflow.core.utils.logging` from `kymflow_zarr`.
- Behavior: refactor-only.

2. `src/kymflow/core/zarr/src/kymflow_zarr/dataset.py`
- What: logger import/assignment switched to stdlib; additional Ticket 6 API work (detailed below).
- Why: decouple logging + implement sources/refresh APIs.
- Behavior: behavior changed (due Ticket 6 APIs), logging part refactor-only.

3. `src/kymflow/core/zarr/src/kymflow_zarr/experimental_stores/__init__.py`
- What: logger import/assignment switched to stdlib.
- Why: decouple logging.
- Behavior: refactor-only.

4. `src/kymflow/core/zarr/src/kymflow_zarr/experimental_stores/acq_image.py`
- What: logger migration + Ticket 4 rename and API updates (detailed below).
- Why: decouple logging + clarify source identity.
- Behavior: behavior changed (field/method semantics).

5. `src/kymflow/core/zarr/src/kymflow_zarr/experimental_stores/acq_image_list.py`
- What: logger import/assignment switched to stdlib.
- Why: decouple logging.
- Behavior: refactor-only.

6. `src/kymflow/core/zarr/src/kymflow_zarr/experimental_stores/stores/__init__.py`
- What: logger import/assignment switched to stdlib.
- Why: decouple logging.
- Behavior: refactor-only.

7. `src/kymflow/core/zarr/src/kymflow_zarr/experimental_stores/stores/base.py`
- What: logger import/assignment switched to stdlib.
- Why: decouple logging.
- Behavior: refactor-only.

8. `src/kymflow/core/zarr/src/kymflow_zarr/experimental_stores/stores/factory.py`
- What: logger import/assignment switched to stdlib.
- Why: decouple logging.
- Behavior: refactor-only.

9. `src/kymflow/core/zarr/src/kymflow_zarr/experimental_stores/stores/sidecar.py`
- What: logger import/assignment switched to stdlib.
- Why: decouple logging.
- Behavior: refactor-only.

10. `src/kymflow/core/zarr/src/kymflow_zarr/experimental_stores/stores/tiff_store.py`
- What: logger import/assignment switched to stdlib.
- Why: decouple logging.
- Behavior: refactor-only.

11. `src/kymflow/core/zarr/src/kymflow_zarr/experimental_stores/stores/zarr_store.py`
- What: logger import/assignment switched to stdlib.
- Why: decouple logging.
- Behavior: refactor-only.

12. `src/kymflow/core/zarr/src/kymflow_zarr/io_export.py`
- What: logger import/assignment switched to stdlib; Ticket 5 JSON export fallback update (detailed below).
- Why: decouple logging + support new/legacy JSON artifact export.
- Behavior: behavior changed.

13. `src/kymflow/core/zarr/src/kymflow_zarr/io_import.py`
- What: logger import/assignment switched to stdlib; Ticket 6 ingest restructuring (detailed below).
- Why: decouple logging + shared ingest path + sources index population.
- Behavior: behavior changed.

14. `src/kymflow/core/zarr/src/kymflow_zarr/manifest.py`
- What: logger import/assignment switched to stdlib; Ticket 5 metadata read order changed (`metadata.json` then legacy `.json.gz`).
- Why: decouple logging + support JSON format transition.
- Behavior: behavior changed.

15. `src/kymflow/core/zarr/src/kymflow_zarr/record.py`
- What: logger import/assignment switched to stdlib; Ticket 5 JSON write/read semantics changed (detailed below).
- Why: decouple logging + canonical uncompressed JSON writes with legacy read fallback.
- Behavior: behavior changed.

16. `src/kymflow/core/zarr/src/kymflow_zarr/schema.py`
- What: logger import/assignment switched to stdlib.
- Why: decouple logging.
- Behavior: refactor-only.

17. `src/kymflow/core/zarr/src/kymflow_zarr/utils.py`
- What: logger import/assignment switched to stdlib; docs updated to reflect `.json` canonical + `.json.gz` legacy compatibility.
- Why: decouple logging + align docs to behavior.
- Behavior: doc/comment change only for Ticket 5 part.

### Ticket 4: `AcqImageV01.key -> source_key` + identity clarity

18. `src/kymflow/core/zarr/src/kymflow_zarr/experimental_stores/acq_image.py`
- What:
  - Dataclass field renamed `key` -> `source_key`.
  - Updated all PixelStore/ArtifactStore calls to use `source_key`.
  - Added `display_name` property.
  - Updated class docstring to define source identity semantics for TIFF vs Zarr modes.
- Why: make image identity explicit as PixelStore identity.
- Behavior: behavior changed (public attribute rename; callsites updated).

19. `src/kymflow/core/zarr/examples/demo_gui_flow_v01.py`
- What: print uses `src_img.source_key` instead of `src_img.key`.
- Why: align demo with renamed public field.
- Behavior: behavior-equivalent output field name changed.

20. `src/kymflow/core/zarr/examples/demo_api_tour_v01.py`
- What: print uses `img.source_key` instead of `img.key`.
- Why: align demo with renamed public field.
- Behavior: behavior-equivalent output field name changed.

21. `src/kymflow/core/zarr/tests/test_acq_image_compat.py`
- What: constructors updated to `source_key=...`.
- Why: align tests with renamed field.
- Behavior: test-only.

22. `src/kymflow/core/zarr/tests/test_metadata_roundtrip.py`
- What: constructors updated to `source_key=...`.
- Why: align tests with renamed field.
- Behavior: test-only.

### Ticket 5: JSON `.json` canonical write + dual read

23. `src/kymflow/core/zarr/src/kymflow_zarr/record.py`
- What:
  - `save_json()` now writes `analysis/<name>.json` (raw JSON bytes, no gzip).
  - `load_json()` now read order: `<name>.json` then legacy `<name>.json.gz`.
  - Metadata payload docstrings updated to `.json` canonical wording.
- Why: human-browsable canonical JSON while preserving backward compatibility.
- Behavior: behavior changed (write format/path changed, read fallback added).

24. `src/kymflow/core/zarr/src/kymflow_zarr/manifest.py`
- What: `_extract_acquired_ns_from_metadata()` now reads `analysis/metadata.json` first, then fallback `analysis/metadata.json.gz`.
- Why: manifest compatibility with new JSON path and legacy stores.
- Behavior: behavior changed.

25. `src/kymflow/core/zarr/src/kymflow_zarr/io_export.py`
- What:
  - Skip metadata for both `metadata.json` and legacy `metadata.json.gz` in artifact iteration.
  - Export JSON artifacts from either `.json` or legacy `.json.gz` using `rec.load_json(name)`.
- Why: support mixed legacy/new stores during export.
- Behavior: behavior changed.

26. `src/kymflow/core/zarr/tests/test_record_api.py`
- What:
  - Deletion suffix test switched from `.json.gz` to `.json`.
  - Added test that `save_json()` writes `.json` key.
  - Added legacy read compatibility test for `.json.gz` artifact.
- Why: enforce new JSON canonical write + backward-compatible read.
- Behavior: test-only.

27. `src/kymflow/core/zarr/tests/test_manifest_resilience.py`
- What: malformed metadata resilience test now injects invalid `metadata.json` content (not `.json.gz`).
- Why: validate robustness against malformed new canonical JSON.
- Behavior: test-only.

### Ticket 6: sources index + refresh ingest

28. `src/kymflow/core/zarr/src/kymflow_zarr/dataset.py`
- What:
  - Added sources index API:
    - `load_sources_index()`
    - `save_sources_index(df)`
    - `refresh_from_folder(folder, pattern="*.tif", mode="skip"|"reingest_if_changed")`
  - Updated `ingest_legacy_folder()` to populate `tables/sources.parquet` and update manifest.
  - Wired to shared ingest internals in `io_import.py`.
- Why: explicit refresh ingest and persistent mapping from source file -> image_id with mtime/size metadata.
- Behavior: behavior changed (new ingest bookkeeping, new public APIs).

29. `src/kymflow/core/zarr/src/kymflow_zarr/io_import.py`
- What:
  - Added `SOURCES_COLUMNS` constant.
  - Added `_source_row_for_image(...)`.
  - Added `ingest_legacy_file(...) -> (image_id, source_row)` shared ingest primitive.
  - Refactored `ingest_legacy_folder(...)` to return ingested rows instead of mutating sources table/manifest directly.
  - Provenance JSON now uses `source_primary_path` key.
- Why: centralize ingest logic for both full ingest and refresh workflows.
- Behavior: behavior changed.

30. `src/kymflow/core/zarr/examples/demo_export_import_v01.py`
- What: demo now shows `load_sources_index()`, adds new TIFF, calls `refresh_from_folder(mode="skip")`, prints ingested IDs and updated sources row count.
- Why: demonstrate explicit refresh behavior required by Ticket 6.
- Behavior: demo behavior changed.

31. `src/kymflow/core/zarr/tests/test_import_export_v01.py`
- What: updated provenance assertion to `source_primary_path`; added assertion that sources index has one row after ingest.
- Why: align tests with sources index + provenance key changes.
- Behavior: test-only.

32. `src/kymflow/core/zarr/tests/test_sources_refresh.py`
- What: new test for ingest+refresh semantics (`N` ingest, `+1` on new file, `0` on repeated refresh without changes).
- Why: validate sources index and refresh API contract.
- Behavior: new test coverage.

## 4) Files added

1. `src/kymflow/core/zarr/tests/test_sources_refresh.py`
2. `src/kymflow/core/zarr/prompts/codex_ticket_template.md`
3. `src/kymflow/core/zarr/prompts/runners/codex_change_report_prompt.md`

## 5) Files deleted
- None.

## 6) Public API changes (functions/methods/signatures)

### `kymflow_zarr.experimental_stores.acq_image.AcqImageV01`
- **Renamed public dataclass field**:
  - `key: str` -> `source_key: str`
- **Added public property**:
  - `display_name(self) -> str`
- Existing methods retained; behavior updated internally to use `source_key`.

### `kymflow_zarr.dataset.ZarrDataset`
- **Added public methods**:
  - `load_sources_index(self) -> pd.DataFrame`
  - `save_sources_index(self, df: pd.DataFrame) -> None`
  - `refresh_from_folder(self, folder: str | Path, pattern: str = "*.tif", *, mode: str = "skip") -> list[str]`
- Existing method changed semantically:
  - `ingest_legacy_folder(...)` now updates `tables/sources.parquet` and manifest when ingest occurs.

### `kymflow_zarr.record.ZarrImageRecord`
- No signature additions/removals.
- Semantics changed in `save_json` / `load_json` (see sections 7–9).

### `AcqImageListV01`
- No API signature changes.

### Store protocols (`PixelStore` / `ArtifactStore`)
- No signature changes.

## 7) Exception handling changes

- `ZarrImageRecord.load_json(name)`:
  - still raises `KeyError` when neither `.json` nor `.json.gz` exists.
  - now tries canonical `.json` first, then legacy `.json.gz`.
- `Manifest._extract_acquired_ns_from_metadata(...)`:
  - unchanged exception classes caught; changed read targets (`metadata.json` -> fallback `.json.gz`).
- `ZarrDataset.refresh_from_folder(...)`:
  - raises `ValueError` for unsupported mode values.

No new broad `except Exception` blocks were introduced in these ticket changes.

## 8) Read/write semantics changes

1. JSON artifacts:
- Write path changed from `analysis/<name>.json.gz` to `analysis/<name>.json`.
- Write encoding changed from gzip-compressed JSON bytes to plain UTF-8 JSON bytes.
- Read semantics now dual-path (`.json` preferred, `.json.gz` legacy fallback).

2. Metadata lookup:
- Manifest acquisition timestamp extraction now checks `analysis/metadata.json` before legacy gzip.

3. Ingest bookkeeping:
- `ingest_legacy_folder` now writes/updates dataset-level sources index and updates manifest.

4. Refresh ingest:
- New explicit refresh API with mode-controlled behavior:
  - `skip`: ingest only unseen `source_primary_path`
  - `reingest_if_changed`: ingest if mtime/size changed relative to latest sources row

## 9) Data layout changes

### New dataset-level table
- `tables/sources.parquet` introduced.

### Sources table schema (v0.1)
Columns:
- `source_primary_path` (str)
- `image_id` (str)
- `source_mtime_ns` (int)
- `source_size_bytes` (int)
- `ingested_epoch_ns` (int)

### JSON artifact canonicalization
- New canonical per-record JSON path:
  - `images/<image_id>/analysis/<name>.json`
- Legacy compatible path still readable:
  - `images/<image_id>/analysis/<name>.json.gz`

### Provenance JSON field update
- Ingest provenance now uses `source_primary_path` key (previous tests referenced `source_path`).

## 10) Known limitations / TODOs

1. `refresh_from_folder(mode="reingest_if_changed")` currently re-ingests changed sources as **new records**; it does not replace prior record content or de-duplicate by path.
2. `save_sources_index` requires exact required columns and does not coerce types; malformed caller DataFrames raise `ValueError`.
3. Export still emits analysis tables as CSV (by design) and does not emit raw parquet during export.
4. JSON legacy fallback is read-only compatibility; no migration utility is implemented to rewrite legacy `.json.gz` artifacts in place.
5. `source_key` rename was applied in zarr layer/tests/examples only; external non-zarr consumers must use updated constructor argument when instantiating `AcqImageV01` directly.
