# Codex Ticket 14–17

## Title
KymDataset v0.1 – Indexer Framework, Table Discipline, and Provenance Linking

---

## High-Level Goals

Implement the first concrete version of `KymDataset` in `kymflow.core` as a domain layer on top of the general-purpose `kymflow_zarr` acquisition container.

This ticket batch must:

1. Introduce a clean Extractor / Indexer interface
2. Implement a concrete KymDataset class
3. Harden replace-row semantics for dataset tables
4. Enforce table namespace discipline
5. Link analysis parameters (JSON) to table rows via provenance fields

This is the first real instantiation of the extensible analysis model.

---

## Architectural Rules

- `kymflow_zarr` remains storage-only (no kym-specific logic).
- `KymDataset` lives in `kymflow/core/`.
- Indexers must not mutate pixel data.
- All public APIs must include:
  - Type hints
  - Google-style docstrings
- No broad `except Exception` unless re-raised immediately.

---

# Ticket 14 – Extractor / Indexer Interface

## Create

src/kymflow/core/kym_dataset/indexer_base.py

Define:

class BaseIndexer(Protocol):
    name: str

    def extract_rows(self, rec: ZarrImageRecord) -> pd.DataFrame:
        ...
    
    def params_hash(self, rec: ZarrImageRecord) -> str:
        ...
    
    def analysis_version(self) -> str:
        ...

Rules:

- extract_rows returns rows for ONE image only.
- Returned DataFrame must include:
  - image_id
  - analysis_version
  - params_hash

No dataset mutation here.

---

# Ticket 15 – Implement KymDataset

## Create

src/kymflow/core/kym_dataset/kym_dataset.py

Class:

class KymDataset:
    def __init__(self, ds: ZarrDataset):
        self.ds = ds

### Required Methods

def update_index(self, indexer: BaseIndexer, *, mode: str = "replace") -> None

Behavior:

- Iterate over all image_ids in dataset
- For each record:
  - call extract_rows
  - replace rows for that image_id in dataset table
- Table name = f"kym_{indexer.name}"

Use existing replace_rows_for_image_id primitive.

---

# Ticket 16 – Table Namespace Discipline

Enforce rule:

All kym tables must be stored under:

tables/kym_<indexer_name>.parquet

Add validation inside KymDataset.update_index:

- Prevent overwriting non-kym tables.
- Reject indexer names that start with reserved prefixes.

---

# Ticket 17 – Provenance Linking

Every row inserted into a kym table must include:

- image_id
- analysis_version
- params_hash

Additionally:

When updating index:

- If table exists and rows for image_id already exist:
  - If params_hash unchanged → skip recompute (future optimization hook)
  - For now: still replace (log TODO for incremental mode)

Add minimal logging (use stdlib logging).

---

# Tests Required

Create tests under:

src/kymflow/core/kym_dataset/tests/

Minimum:

1. test_indexer_row_insertion
2. test_table_name_enforcement
3. test_params_hash_written
4. test_replace_rows_semantics

Use a small in-memory ZarrDataset fixture.

---

# Acceptance Criteria

- All new tests pass.
- Existing zarr tests still pass.
- No coupling introduced into kymflow_zarr.
- Public API clean and minimal.
- No silent exception swallowing.

---

# Known Future Work (Do NOT implement yet)

- Incremental update mode
- Staleness detection
- Cross-index dependency
- Dataset-level provenance logs
