# Handoff Packet — Tickets 3–6 (Codex-ready)

Repo: `kymflow`  
Branch: `kymflow-zarr`  
Area: `src/kymflow/core/zarr/` + minimal touches in `src/kymflow/core/`

These tickets follow on from Tickets 1–2 and assume:
- tests currently pass
- demos `demo_gui_flow_v01.py` and `demo_export_import_v01.py` run

---

## Ticket 3 — Remove `kymflow` logging imports from `kymflow_zarr` (stdlib logging only)

### Goal
Decouple `kymflow_zarr` from `kymflow.core.utils.logging.get_logger` by using standard library logging:
```python
import logging
logger = logging.getLogger(__name__)
```

### Why
- Avoid hard dependency on `kymflow` internals from the storage subpackage.
- Makes it possible to import/execute `kymflow_zarr` in isolation later.

### Scope
Only files under:
- `src/kymflow/core/zarr/src/kymflow_zarr/**`

### Requirements
- Replace all `from kymflow.core.utils.logging import get_logger` imports in `kymflow_zarr`.
- Replace `logger = get_logger(__name__)` with `logger = logging.getLogger(__name__)`.
- Do not change logging semantics beyond this (no new handlers, no formatting).

### Acceptance
- `uv run pytest src/kymflow/core/zarr/tests -q` passes
- `uv run python src/kymflow/core/zarr/examples/demo_export_import_v01.py` passes

---

## Ticket 4 — Clarify/rename `AcqImageV01.key` → `source_key` and document meaning

### Goal
Make the source identity explicit and readable.

### Desired meaning
`source_key` is a **PixelStore identity**:
- TIFF mode: absolute path to the channel-1 TIFF (primary pixel file)
- Zarr mode: record `image_id` string (uuid) inside the dataset

### Scope
- `src/kymflow/core/zarr/src/kymflow_zarr/experimental_stores/acq_image.py`
- Any references in:
  - `src/kymflow/core/zarr/src/kymflow_zarr/experimental_stores/acq_image_list.py`
  - tests + demos under `src/kymflow/core/zarr/`

### Requirements
- Rename dataclass field `key: str` → `source_key: str`
- Update all call sites.
- Update docstring for `AcqImageV01`:
  - Explain what `source_key` is and where it comes from.
- Ensure any JSON payloads that include `key` now use `source_key` (if applicable).
- Add a small helper property (optional but useful):
  - `def display_name(self) -> str: ...` (default: basename for TIFF, or image_id for Zarr)

### Acceptance
- tests pass
- demos pass

---

## Ticket 5 — JSON artifacts: write raw `.json` (no gzip); read both `.json` and legacy `.json.gz`

### Goal
- New writes are human-browsable: `*.json`
- Backward compatible reads: if `.json` missing, fall back to `.json.gz`

### Scope
- `src/kymflow/core/zarr/src/kymflow_zarr/experimental_stores/stores/zarr_store.py`
- Any record helper methods writing JSON (e.g., `ZarrImageRecord.save_json`, `save_metadata_payload`)
- Import/export modules:
  - `src/kymflow/core/zarr/src/kymflow_zarr/io_export.py`
  - `src/kymflow/core/zarr/src/kymflow_zarr/io_import.py`
- Any tests asserting `.json.gz` paths

### Requirements
- Implement canonical JSON path:
  - `analysis/<name>.json`
- Implement backward-compatible read:
  - first try `.json`
  - then try `.json.gz`
- Do **not** compress JSON on write.
- Keep Parquet as canonical for tables (no change).
- Update export:
  - export JSON artifacts from `.json` (or `.json.gz` if legacy)
- Update import:
  - ingest `.json` sidecars as JSON artifacts (store as `.json` inside zarr)

### Tests to add/update
- Ensure writing uses `.json` (not `.json.gz`)
- Ensure reading old `.json.gz` still works

### Acceptance
- tests + demos pass

---

## Ticket 6 — Dataset “sources” index + explicit refresh ingest for new files

### Goal
Support explicit GUI/script refresh:
- scan a legacy folder
- ingest only new TIFFs not already in the dataset
- optionally flag “maybe already ingested / maybe changed” via mtime/size

### Add dataset table
Canonical dataset table:
- `tables/sources.parquet`

Columns (v0.1):
- `source_primary_path` (str) — normalized absolute path
- `image_id` (str uuid)
- `source_mtime_ns` (int) — file mtime converted to ns
- `source_size_bytes` (int)
- `ingested_epoch_ns` (int)

### Public API
Add to `ZarrDataset`:
- `load_sources_index() -> pd.DataFrame`
- `save_sources_index(df: pd.DataFrame) -> None`
- `refresh_from_folder(folder: str|Path, pattern: str="*.tif", *, mode: str="skip") -> list[str]`
  - returns list of newly ingested `image_id`s
  - `mode="skip"`: if `source_primary_path` already present → skip
  - `mode="reingest_if_changed"` may be stubbed (optional): compare size/mtime and reingest if changed

### Integrate with existing ingest
- `ingest_legacy_folder(...)` should populate `sources` table as it ingests.
- `refresh_from_folder(...)` should call a shared internal ingest function to avoid duplicating logic.

### Tests
- Create temp folder with N TIFFs
- Ingest once → sources length N
- Add one new TIFF → refresh → ingests 1 new image, sources length N+1
- Re-run refresh without changes → ingests 0

### Acceptance
- tests pass
- update `demo_export_import_v01.py` to demonstrate refresh (optional but recommended)

---

## Add prompts templates (housekeeping)
Create under `src/kymflow/core/zarr/prompts/`:

1) `codex_ticket_template.md`  
2) `codex_change_report_prompt.md` (the report prompt you used)

(If the folder already exists, just add these files.)

---

# Notes for Codex
- Keep typed signatures and Google-style docstrings on public methods.
- Avoid broad `except Exception` unless immediately re-raised; use targeted exceptions.
