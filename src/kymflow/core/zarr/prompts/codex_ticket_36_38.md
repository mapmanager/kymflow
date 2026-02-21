# codex_ticket_36_38.md

## Title
Add `docs/` suite for zarr core API contract + bake “docs must stay updated” rule into workflow

Repo: `kymflow`
Branch: `kymflow-zarr`
Scope: **zarr core only** (`src/kymflow/core/zarr/...`)

---

## Why
We need a living, human-readable API contract for the zarr core so a developer (or an LLM) can reliably answer:
- “How do I ingest a TIFF?”
- “How do I attach/read metadata and analysis artifacts?”
- “What’s the on-disk layout and which parts are authoritative?”

**Hard rule:** `docs/` is a living contract. Any change to public API semantics requires docs updates in the same PR/ticket.

---

## Ticket 36 — Create initial `docs/` suite (v0)

### Add directory
Create:

- `src/kymflow/core/zarr/docs/`

### Add markdown files
1) `src/kymflow/core/zarr/docs/README.md`
   - Purpose and scope of “zarr core”
   - Definitions: Dataset, Record, Manifest, Artifacts, Tables, Run marker
   - Explicit rule: docs must be updated when API changes

2) `src/kymflow/core/zarr/docs/api.md`  **(the contract)**
   - Enumerate the *public* surfaces (only what we intend callers to use)
   - For each: short description, signatures (copy/paste), read/write semantics, exceptions
   - Must include at least:
     - `ZarrDataset`: constructor/open modes, `add_image`, `record`, `image_ids`, `update_manifest`,
       tables API (`load_table/save_table/replace_rows_for_image_id/...`), legacy import/export if present
     - `ZarrImageRecord`: `open_array/load_array` (if exists), `get_axes`, `get_image_bounds`,
       `list_analysis_keys`, JSON + table artifact methods, metadata object payload methods
     - `run_marker.py` public helpers (if part of intended API)
   - Clearly label “internal / not stable” sections if needed

3) `src/kymflow/core/zarr/docs/layout.md`
   - Store layout paths, e.g.
     - `images/<image_id>/data`
     - `images/<image_id>/analysis/*`
     - `index/manifest...`
     - `tables/<name>.parquet`
   - “Authoritative vs derived”: manifest is derived; pixels + artifacts are authoritative

4) `src/kymflow/core/zarr/docs/workflows.md`
   - Copy/paste examples (minimal):
     - Create/open dataset
     - Ingest TIFF (document current best practice; if no `ingest_tiff`, show `tifffile.imread + add_image`)
     - Attach provenance JSON
     - Save/load header + experiment metadata + rois (canonical metadata payload)
     - Add/read a per-record table artifact and a dataset table
     - Export back to TIFF/CSV/JSON if those APIs exist

5) `src/kymflow/core/zarr/docs/incremental.md`
   - `params_hash` definition and what it means
   - Run marker schema: how “0 rows computed” is represented
   - Staleness reasons (high-level), link to `kym_dataset` if staleness types live there

### Content rules
- Use exact class/method names from code (do not invent APIs).
- Keep examples runnable in your environment (imports must be correct).
- Avoid excessive prose—this is developer reference.

---

## Ticket 37 — Add a tiny “docs drift” guard (optional but recommended)

Add:

- `src/kymflow/core/zarr/tests/test_docs_contract_smoke.py`

Test intent:
- Ensure docs exist and include a few key strings so we don’t “forget” to update them.
- Minimal checks only (do not overfit):
  - `docs/api.md` contains `ZarrDataset` and `ZarrImageRecord`
  - `docs/workflows.md` contains “Ingest TIFF” (or similar heading)

---

## Ticket 38 — Update Codex workflow prompts to enforce docs updates

Update:

- `src/kymflow/core/zarr/prompts/codex_run_ticket.md`
  - Add a requirement: if ticket changes public API or read/write semantics, update docs (`docs/api.md` + relevant docs files).
  - Add a checklist line in the final response: “Docs updated? yes/no (files)”

Also update (if present/used):
- `src/kymflow/core/zarr/prompts/codex_implement_ticket_and_gen_report_prompt.md`
  - Add the same docs-update rule (short form)

---

## Required commands
- `uv run pytest src/kymflow/core/zarr/tests -q`

No demo scripts required for this ticket.

---

## Definition of Done
- `docs/` directory exists with the 5 files listed.
- `docs/api.md` reflects actual current APIs.
- `codex_run_ticket.md` (and implement+report prompt, if used) explicitly requires docs updates with API changes.
- Tests pass.
