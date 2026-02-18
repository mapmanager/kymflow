# How to Add (or Remove) Attributes to the Radon Report

This recipe is a checklist for developers, future maintainers, and LLMs when adding new attributes to (or removing old ones from) the radon report. The radon report is the per-ROI summary of velocity analysis and related metadata, persisted as `radon_report_db.csv` and used by the plot pool and exports.

---

## Quick Checklist

Use this as a running checklist; not every item applies to every change.

### Adding a new attribute

- [ ] **Core – RadonReport** (`core/image_loaders/radon_report.py`): Add field to dataclass; update docstring; update `from_dict()` type handling if not a string (see below).
- [ ] **Core – KymAnalysis** (`core/image_loaders/kym_analysis.py`): In `get_radon_report()`, compute or read the value (once per image where appropriate) and pass it into every `RadonReport(...)` call.
- [ ] **Core – Cache/CSV**: No change needed; cache and CSV use `fields(RadonReport)` and `to_dict()`/`from_dict()`, so new fields are picked up automatically. Loading an old CSV will trigger a rebuild when columns are missing (see Gotchas).
- [ ] **GUI – Radon consumers**: If the new attribute should refresh the plot pool when it changes at runtime, ensure the code path that updates it also updates the radon cache (and optionally emits `RadonReportUpdated`). See “When the radon cache is updated” below.
- [ ] **Tests**: Update `tests/core/test_radon_report.py` (and any `test_kym_image_list.py` tests that assert on report fields or CSV columns) to include or allow the new attribute.

### Removing an attribute

- [ ] **Core – RadonReport**: Remove the field from the dataclass and docstring; remove or relax its handling in `from_dict()` (e.g. drop from the explicit int/float/bool/string lists if it was there).
- [ ] **Core – KymAnalysis**: Remove the variable and the argument from every `RadonReport(...)` call in `get_radon_report()`.
- [ ] **GUI**: No structural change usually; old CSV columns will be ignored by `from_dict()` (unknown keys are already ignored). Consider whether any UI or scripts assume the column exists.
- [ ] **Tests**: Remove or adjust assertions that reference the removed field; ensure roundtrip and CSV tests still pass.

---

## Section 1: Edits in `core/`

### 1.1 RadonReport dataclass

**File:** `kymflow/src/kymflow/core/image_loaders/radon_report.py`

1. **Add the field** to the dataclass. Use `Optional[<type>] = None` for optional fields. Keep field order consistent (e.g. existing path/metadata fields before `accepted`, then experimental metadata like `treatment`, `condition`, `date`).
2. **Update the class docstring** in the `Attributes` section so the new field is documented and its source is clear (e.g. “From AcqImage experimental metadata”).
3. **Serialization:**
   - `to_dict()` uses `asdict(self)`, so new fields are included automatically.
   - `from_dict()`: New fields are only auto-handled if they are treated as **strings** in the final `else` branch. For **int**, **float**, or **bool** you must add an explicit branch or add the field name to the existing lists:
     - **int:** add to the list that includes `roi_id`, `img_min`, `img_max`, `vel_n_nan`, `vel_n_zero`, `vel_n_big`.
     - **float:** add to the list that includes `vel_min`, `vel_max`, `vel_mean`, ….
     - **bool:** add a dedicated `elif key == "your_key":` with the same logic as `accepted`.
     - **str:** no change; the `else` branch does `str(value) if value is not None else None` for all remaining known fields.
   - Optionally update the comment on the `else` branch to include the new field name for discoverability.

**Example – new string attribute:**

```python
# In class docstring Attributes:
#   my_attr: Description and source (e.g. from AcqImage experimental metadata).

my_attr: Optional[str] = None

# In from_dict(), the existing else branch already covers it; optionally:
# else:
#     # Strings (..., treatment, condition, date, my_attr)
#     filtered_data[key] = str(value) if value is not None else None
```

**Example – new int attribute:** Add to the int list in `from_dict()`:

```python
elif key in ["img_min", "img_max", "vel_n_nan", "vel_n_zero", "vel_n_big", "my_count"]:
    filtered_data[key] = int(value) if value is not None else None
```

### 1.2 Populating the attribute: KymAnalysis.get_radon_report()

**File:** `kymflow/src/kymflow/core/image_loaders/kym_analysis.py`

1. **Where to get the value:** Decide if it is per-ROI or per-image. Per-image values (e.g. path, file_name, parent_folder, grandparent_folder, accepted, treatment, condition, date) should be computed or read **once** before the `for roi_id in roi_ids:` loop.
2. **Per-image example (e.g. from AcqImage experimental metadata):**
   - Read from `self.acq_image.experiment_metadata` (and normalize empty string to None if desired):  
     `my_attr = getattr(self.acq_image.experiment_metadata, "my_attr", None) or None`
   - Pass into every `RadonReport(...)` call: `my_attr=my_attr`.
3. **Per-ROI example:** Compute inside the loop (e.g. from `roi`, `velocity`, or `self.get_analysis_value(roi_id, ...)`) and pass that value into `RadonReport(...)` for that ROI.
4. **Keep the dataclass frozen:** Do not mutate a `RadonReport` after creation; construct a new instance with all required arguments.

### 1.3 Cache and CSV (KymImageList)

- **`_radon_report_cache`:** Keyed by image path string; value is `List[RadonReport]`. Populated by `_load_radon_report_db()` (from CSV or rebuild) and by `update_radon_report_cache_only()` / `_build_reports_from_images()`.
- **Loading CSV:** `_load_radon_report_db()` uses `expected_cols = {f.name for f in fields(RadonReport)}`. If the CSV is missing any column (e.g. you added a new field), `missing = expected_cols - set(df.columns)` is non-empty → rebuild from images, then **save** (see Gotchas).
- **Saving CSV:** `save_radon_report_db()` builds `report_dicts = [r.to_dict() for r in reports]` and writes the DataFrame to CSV. New fields appear automatically.
- **rel_path:** Not set in `KymAnalysis.get_radon_report()`; it is set by `KymImageList` via `dataclass_replace(r, rel_path=rel_path)` when building cache entries. Do not add `rel_path` in `get_radon_report()`.

No code changes are required in `kym_image_list.py` when adding a new attribute, unless you introduce a new cache-invalidation or update rule.

---

## Section 2: Edits in `gui_v2/`

### 2.1 When the radon cache must be updated

The radon report cache in `KymImageList` should stay in sync with:

1. **Load / rebuild** – Handled in `_load_radon_report_db()` (core).
2. **User clicks “Analyze flow”** – Handled in `plot_pool_bindings.py`: on `AnalysisCompleted`, call `update_radon_report_cache_only(e.file)` and emit `RadonReportUpdated()`.
3. **User edits AcqImage experimental metadata** – Handled in `metadata_controller.py`: after applying experimental metadata, if the file list supports it, call `update_radon_report_cache_only(e.file)` and emit `RadonReportUpdated()`. CSV is **not** written until the user explicitly saves (Option A).
4. **User saves (selected or all)** – Handled in `save_controller.py`: after save, call `update_radon_report_for_image(kf)` (cache + persist to CSV).

If your new attribute is updated through a **different** code path (e.g. a new UI that edits something that feeds into the radon report), you must add a call to update the radon cache (and optionally emit `RadonReportUpdated`) in that path; otherwise the plot pool and saved CSV will be stale.

### 2.2 Files that reference radon report / cache

| File | Role |
|------|------|
| `gui_v2/controllers/metadata_controller.py` | On experimental metadata edit → `update_radon_report_cache_only(e.file)` + `RadonReportUpdated()` |
| `gui_v2/views/plot_pool_bindings.py` | Subscribes to `RadonReportUpdated` and `FileListChanged` to refresh plot pool; on `AnalysisCompleted` → `update_radon_report_cache_only(e.file)` + `RadonReportUpdated()` |
| `gui_v2/controllers/save_controller.py` | On save → `update_radon_report_for_image(kf)` |
| `gui_v2/pages/home_page.py` | Uses `app_state.files.get_radon_report_df()` for plot pool; checks `hasattr(app_state.files, "get_radon_report_df")` |
| `gui_v2/controllers/folder_controller.py` | Handles `phase == "rebuild_radon_db"` progress messages |
| `gui_v2/events_state.py` | Defines `RadonReportUpdated` event |

Adding a new attribute to `RadonReport` does **not** by itself require changes in these files. Only add GUI edits if:

- The new attribute is editable or derived from something that is updated in the GUI (e.g. another metadata form), and that update path does not already trigger a radon cache update and `RadonReportUpdated`.
- You want to show the new column in a specific UI (e.g. plot pool config or table); then add the column/config in the relevant view.

### 2.3 Emitting RadonReportUpdated

If you add a new place that updates the radon cache (e.g. a new controller or batch script that runs in the GUI context), emit `RadonReportUpdated()` after the update so the plot pool refreshes:

```python
from kymflow.gui_v2.events_state import RadonReportUpdated
# ... after update_radon_report_cache_only(...) or similar ...
self._bus.emit(RadonReportUpdated())
```

Do **not** call `save_radon_report_db()` unless the user has explicitly triggered a save; in-memory cache updates should only persist when the user saves.

---

## Section 3: Gotchas and Red Flags

### 3.1 Save after rebuild on load

**Behavior:** When the radon DB is missing or the CSV schema is stale (e.g. you added a new column), `_load_radon_report_db()` rebuilds from images and then calls `save_radon_report_db()`. So the **first load with new code can write CSV without an explicit user save.**

**Red flag:** If you assume “CSV is only written on explicit save,” this is an exception. The code comment in `kym_image_list.py` above `save_radon_report_db()` after rebuild documents this; preferred behavior would be not to save unless the user explicitly saves, but the current behavior is left as-is.

### 3.2 from_dict() type lists are hardcoded

**Red flag:** In `radon_report.py`, `from_dict()` uses **hardcoded** lists for int, float, and a single special case for `accepted` (bool). Adding a new **int**, **float**, or **bool** field without adding it to the right branch will leave it as a string or wrong type when loading from CSV/JSON, which can cause subtle bugs (e.g. sorting, filtering, or downstream logic). Always update the appropriate branch and add a test that roundtrips the new type.

### 3.3 Frozen dataclass: no in-place updates

**Red flag:** `RadonReport` is `frozen=True`. You cannot do `r.treatment = "x"`. To “update” a report you must create a new instance (e.g. `dataclasses.replace(r, treatment="x")`) or build a new list and replace the cache entry. `KymImageList` uses `dataclass_replace(r, rel_path=rel_path)` for this when attaching `rel_path`.

### 3.4 Cache key is path string; path can be None

**Red flag:** Cache is keyed by `str(kym_image.path)`. If `path` is None, `update_radon_report_cache_only()` and `update_radon_report_for_image()` return without updating. Ensure images that contribute to the radon report have a non-None path when used in folder or file-list mode.

### 3.5 New attribute and old CSV

When you add a new required or expected field:

- **Loading:** Old CSV has no column for it → `missing` is non-empty → full rebuild from images → new reports have the new field (from current in-memory state). Then the code **saves** the new CSV (see 3.1).
- **Backward compatibility:** `from_dict()` only sets keys that exist in `data`; missing keys get the dataclass default (usually `None`). So old rows still load; new fields are None. No migration script is required for “add optional field.”

### 3.6 Removing an attribute

If you remove a field from the dataclass:

- **from_dict:** Unknown keys are already ignored, so old CSV columns with that name are harmless.
- **to_dict:** The field no longer exists, so it will not be written. Existing CSVs will still have the column until overwritten. Downstream scripts that expect that column may break if they rely on it.

---

## Section 4: Code Review – Current Radon Report Implementation

### 4.1 RadonReport (`radon_report.py`)

**Strengths**

- Single source of truth: one frozen dataclass, clear docstring, and explicit serialization contract.
- `to_dict()` / `from_dict()` support CSV and JSON; `fields(cls)` keeps schema discovery automatic for new fields (for load/save and schema checks).
- NaN/None handling in `from_dict()` avoids bad values from CSV.
- `roi_id` required check prevents invalid reports.

**Weak points / improvements**

1. **Brittle type dispatch in `from_dict()`:** The int/float/bool branches use **hardcoded** field names. Adding a new int/float/bool field is error-prone (easy to forget). **Improvement:** Derive type from the dataclass field type (e.g. `get_type_hints(RadonReport)` or a small registry) and convert by type, with explicit overrides only for special cases like `accepted`.
2. **Comment drift:** The comment listing string fields can get out of date. **Improvement:** Either document that “all remaining known fields are strings” or stop listing them and rely on “else = string” semantics.
3. **No schema version:** Old CSV cannot be distinguished from “new schema with optional columns” except by missing columns. **Improvement:** Optional: add a `_schema_version` or `_radon_report_version` field (or a separate manifest) to support future migrations or stricter compatibility checks.

### 4.2 KymImageList radon cache

**Strengths**

- Cache is keyed by path; rebuild and per-image update are clear. `get_radon_report()` order follows `self.images`, which is stable and predictable.
- `update_radon_report_cache_only` vs `update_radon_report_for_image` cleanly separates in-memory refresh from persist.
- `_build_reports_from_images()` adds `rel_path` in one place, avoiding duplication in `KymAnalysis.get_radon_report()`.

**Weak points / improvements**

1. **Cache can be stale if images change without a cache update:** If something mutates analysis or metadata (e.g. a script or a code path we don’t hook) without calling `update_radon_report_cache_only` or `update_radon_report_for_image`, the cache and CSV will be stale. **Improvement:** Document all mutation points that must touch the radon cache (this doc and code comments); consider a “dirty” flag or validation that compares cache to current `get_radon_report()` from images for debugging.
2. **No staleness check on load:** Unlike velocity event DB, we do not compare loaded cache to current image state (e.g. by content hash or report count). We only check “missing columns” and then rebuild. So if the CSV has the right columns but outdated content (e.g. from an old run), we keep it. **Improvement:** Optionally, add a lightweight staleness check (e.g. set of (path, roi_count) or checksum) and rebuild when stale, if we want to guarantee freshness at load.
3. **Rebuild replaces entire cache:** Rebuild always rebuilds from all images and overwrites the whole cache. For large lists this can be slow. **Improvement:** For future scalability, consider incremental updates (e.g. only rebuild images whose path is missing or whose mtime/metadata changed); currently acceptable for typical folder sizes.

### 4.3 Persisting to and loading from CSV

**Strengths**

- Single file per folder/file-list; path rules are clear (`_get_radon_db_path()`). CSV is human-readable and easy to inspect.
- Schema check via `fields(RadonReport)` ensures we rebuild when the schema gains columns; no manual version constant in the loader.
- `rel_path` allows portable CSVs when base path is available; path resolution on load handles missing `path` using `rel_path` + base.

**Weak points / improvements**

1. **Save after rebuild (see Gotchas 3.1):** Rebuild-on-load triggers a save, which is not “explicit user save.” Documented in code and in this doc; behavior could be changed later to only rebuild in memory and not call `save_radon_report_db()` until the user saves.
2. **`print(df.head())` in save path:** `save_radon_report_db()` contains `print(df.head())`, which is noisy in production and in tests. **Improvement:** Remove or guard with a debug flag / logger at debug level.
3. **No quoting or escaping policy:** CSV is written with pandas default options. If a field contains commas, newlines, or quotes, behavior depends on pandas. **Improvement:** Document or fix encoding/quoting (e.g. `quoting=csv.QUOTE_NONNUMERIC`) if needed for downstream tools.
4. **Row order:** Rows are written in `get_radon_report()` order (by `self.images`, then by ROI id per image). This is stable but not explicitly documented. **Improvement:** Add a one-line comment or docstring note that CSV row order follows image list then ROI id.
5. **Large CSVs:** Entire CSV is read into memory and parsed row-by-row into `RadonReport` instances. For very large folders this could be heavy. **Improvement:** For future scale, consider chunked read or streaming if we ever need to support huge report DBs.

---

## Summary

- **Adding an attribute:** Add field and docstring in `radon_report.py`; add type handling in `from_dict()` if not string; populate in `kym_analysis.get_radon_report()` and pass into `RadonReport(...)`; update tests; ensure any new runtime update path that affects the report also updates the radon cache (and emits `RadonReportUpdated` if in GUI).
- **Removing an attribute:** Remove from dataclass and from `get_radon_report()`; relax `from_dict()` if needed; update tests; be aware that old CSV columns will be ignored and new CSVs will no longer contain that column.
- **Core** owns schema, serialization, and cache/CSV logic; **gui_v2** owns when to call cache update and when to emit `RadonReportUpdated`, and where the radon DataFrame is consumed (e.g. plot pool).
- Watch for: save-after-rebuild on load, hardcoded types in `from_dict()`, frozen dataclass, and any new mutation path that doesn’t update the radon cache.
