# Ticket 035 — Persist diameter analysis for one kymimage: save + reload (JSON + CSV)

**Goal:** Provide a clean, fail-fast persistence layer for the diameter pipeline:
- Save analysis outputs for a **single kymimage** to **two files**: one JSON and one CSV.
- Reload those files and restore runtime objects without guessing.
- Supports multiple ROI/channel runs per kymimage in the file formats (even if GUI currently uses roi=1, ch=1).

## Scope
- Only `sandbox/diameter-analysis/` (no edits under `kymflow/`).
- Primary file: `diameter_analysis.py`
- Integrate into GUI/controller only if straightforward; otherwise keep as pure backend API.

## Design decisions to implement (no guessing)
1) **File naming & location**
- Save alongside the source kym path by default:
  - JSON: `<kym_stem>.diameter.json`
  - CSV:  `<kym_stem>.diameter.csv`
- Provide override for output directory if needed.

2) **Fail-fast required metadata**
- Saved bundle must include **roi_id** and **channel_id** for each run.
- Load must raise if any required field is missing (no defaults/back-compat).

3) **Format**
- JSON: structured bundle (schema_version, source_path optional, runs keyed by (roi_id, channel_id) or nested dict).
- CSV: “flat wide” columns using naming `{field}_roi{roi}_ch{ch}` (underscore separator), plus time columns.
  - Time columns must always be present and unambiguous.

## Tasks

### 1) Add explicit backend API
In `diameter_analysis.py` (or a new `persistence.py` inside the sandbox package), add:

- `save_diameter_analysis(kym_path: str | Path, bundle: DiameterAnalysisBundle, *, out_dir: Path | None = None) -> tuple[Path, Path]`
- `load_diameter_analysis(kym_path: str | Path, *, in_dir: Path | None = None) -> DiameterAnalysisBundle`

These functions should:
- Determine file paths from `kym_path` + optional directory override.
- Write JSON + CSV.
- Read JSON + CSV and validate consistency (same schema_version; runs match; required fields present).

### 2) Ensure bundle model supports multi-run keys
If current bundle/run models do not include `channel_id` or cannot represent multiple runs:
- Refactor minimally so that each run is identified by (roi_id, channel_id).
- Keep API stable where possible, but prefer correctness over compatibility.

### 3) Roundtrip tests
Add tests that:
- Create a small synthetic bundle with **two** runs (roi=1,ch=1) and (roi=2,ch=1) (or (roi=1,ch=2)).
- Save -> load -> compare essential arrays/scalars for equality.
- Assert missing required fields raises.

### 4) Optional: wire into controller
If controller currently runs `analyze(...)`, add a *single* call site to:
- Save immediately after detect (behind a config flag), or
- Add explicit “Save analysis” and “Load analysis” actions.

Keep GUI changes minimal; core requirement is backend persistence.

## Acceptance criteria
- Saving produces both files with the agreed naming.
- Loading restores the bundle without defaults/back-compat.
- Tests cover multi-run, required fields, and roundtrip integrity.
- `uv run pytest` passes.

## Clarifications / new requirements (manual save only)
- **No autosave**: do not write analysis sidecars automatically on detect/load. Only write when the user explicitly clicks **Save analysis**.
- GUI must add a **Save analysis** button (Home page) that calls a controller method (e.g. `controller.save_analysis()`).
- Save should write exactly two files per kym image:
  - JSON sidecar (multi-run bundle; supports multiple (roi_id, channel_id))
  - CSV wide export (registry-driven; same bundle)
- If there is no current results bundle (no analysis run yet), clicking Save should fail fast with a clear error message (and UI notify).
