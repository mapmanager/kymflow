# Ticket 12 — Robust Dataclass JSON Serialization (Centralize, Remove Longhand Field Wiring)

**Ticket ID:** ticket_12  
**Scope folder (STRICT):** `kymflow/sandbox/heart_rate_analysis/heart_rate/`

## Allowed edits (ONLY these files, unless explicitly created below)
- ✅ Modify: `heart_rate_pipeline.py`
- ✅ Modify: `heart_rate_analysis.py` (ONLY if config/estimate dataclasses live there and need serialization refactor)
- ✅ Modify/Create tests under: `tests/` (e.g. `tests/test_heart_rate_persistence.py`)
- ✅ (Optional) Add doc: `docs/heart_rate_persistence.md`

## Out of scope (DO NOT TOUCH)
- ❌ `run_heart_rate_examples_fixed2.py`
- ❌ Any files outside the scope folder above
- ❌ Any algorithmic changes to HR estimation (no numeric/behavior changes intended)
- ❌ Any batch parallel runner changes (leave `heart_rate_batch.py` untouched)

---

## Problem Statement

Current JSON save/load logic is brittle because dataclass fields are frequently enumerated “longhand” across multiple to_dict/from_dict implementations.  
This creates a maintenance hazard: adding/removing/renaming a dataclass field requires updates in several places and is easy to miss.

---

## Goal

Implement a small, robust, centralized dataclass JSON serializer/deserializer that:

1) **Automatically** serializes dataclasses (including nested dataclasses).
2) **Deserializes** by using `dataclasses.fields(cls)` to:
   - accept known keys
   - ignore unknown keys (forward-compatible)
   - fill missing keys with dataclass defaults (backward-compatible)
3) Minimizes manual field listing in `to_dict()` / `from_dict()` methods.

Keep the persistence schema stable; no changes to output key names beyond what’s needed for robust behavior.

---

## Requirements

### R1) Central helpers
Add these helpers in `heart_rate_pipeline.py` (top-level, importable by other modules):

- `def dataclass_to_jsonable(obj: Any) -> Any:`
  - Converts dataclasses → dict
  - Recurses into:
    - dict
    - list/tuple
    - primitives
  - Must handle:
    - `Enum` → `value`
    - `Path` → `str(path)`
  - Must raise a clear `TypeError` if an unsupported type is encountered.

- `def dataclass_from_dict(cls: type[T], payload: Mapping[str, Any]) -> T:`
  - Uses `fields(cls)` to collect known field names.
  - Builds kwargs from payload for known keys only.
  - Missing keys must rely on dataclass defaults.
  - Unknown keys are ignored.
  - Must support nested dataclasses by checking the field type and calling `dataclass_from_dict(...)` recursively when appropriate.
  - Must support Enum fields by converting from string values to Enum member.
  - Must support Path fields by converting from string to Path.

**Note:** If some dataclasses use `Literal` or `Optional[...]` types, implement pragmatic handling:
- Optional nested dataclass: if value is None, keep None
- Optional Enum: if value is None, keep None

### R2) Refactor persistence dataclasses to use helpers
Update the relevant dataclasses’ `to_dict()` / `from_dict()` methods to delegate to the centralized helpers, eliminating longhand field lists.

At minimum, ensure these types are robustly serialized:
- `HRAnalysisConfig`
- `HeartRateEstimate` (if persisted)
- `HeartRatePerRoiResults`
- Any “results container” dataclass that is written into the `_heart_rate.json` file

### R3) Save/load uses helpers
Update `HeartRateAnalysis.save_results_json()` and `HeartRateAnalysis.load_results_json()` to:
- use `to_dict()` / `from_dict()` methods that are now backed by helpers
- eliminate any redundant dual-source config “repair” logic **if possible without schema change**
  - If schema currently includes both `per_roi[roi]['cfg']` and `per_roi[roi]['results']['analysis_cfg']`:
    - Keep schema unchanged for now, but ensure load resolves deterministically:
      - Prefer `per_roi[roi]['cfg']` as source of truth
      - Ensure `roi_result.analysis_cfg` matches it (replace if needed)
    - Add a short comment stating why both exist and what is authoritative.

### R4) Tests (small but meaningful)
Add tests (fast, deterministic) that verify:

1) **Forward compatibility**: JSON contains an unknown key for a dataclass → load ignores it and succeeds.
2) **Backward compatibility**: JSON is missing a field that has a default → load succeeds and the default is applied.

Where to test:
- Prefer testing `HeartRateAnalysis.save_results_json()` → edit JSON payload → `load_results_json()` round trip.

### R5) Documentation (optional but recommended)
Add `docs/heart_rate_persistence.md` describing:
- JSON file naming convention (`*_heart_rate.json`)
- Schema version field
- Forward/back compatibility behavior (unknown keys ignored, missing keys default)

---

## Non-goals (explicit)

- No changes to HR numerical results.
- No changes to the batch parallel API.
- No changes to runner scripts.

---

## Acceptance criteria

- `uv run pytest` passes.
- Saving/loading works and is resilient to added/removed fields.
- Reduced manual field enumeration in code for the affected dataclasses.
- Changes are confined to allowed files.

---

## Codex report requirements (per CODEX_RULES)
- List modified code files (exclude report file), plus artifacts created
- Provide unified diffs for changed code files
- State what searches were performed to avoid unintended edits
- Provide commands run and observed outputs
- Include self-critique (pros/cons/drift risk)
