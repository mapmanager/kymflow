# Plan: Load CSV — "N of M files" and failure reporting

**Status:** Implemented (core + GUI). See implementation order below.

**Goal:** Final load status for CSV should show **N of M files** (e.g. "Loaded CSV: name.csv (60 of 65 files)") and, when some rows fail, **· K skipped** (e.g. "60 of 65 files · 5 skipped"). Individual row failures (e.g. path does not exist) should be clearly logged and optionally reported to the GUI.

---

## Current behavior

- **`AcqImageList.collect_paths_from_csv`** (in `acq_image_list.py`): Reads CSV `rel_path` column, resolves paths, and **raises `ValueError`** if **any** path does not exist. So load is all-or-nothing; no partial load.
- **FolderController `on_done`**: Has `len(files)` only, so it shows e.g. "Loaded CSV: name.csv (60 files)" with no total row count or skip count.
- **Logging:** We already log once per failed row with an f-string:  
  `logger.warning(f"CSV row failed to load: path does not exist (row {idx+1}, rel_path=..., resolved=...)")`  
  before appending to `invalid_paths` and then raising.

---

## Desired behavior

1. **Success message:** "Loaded CSV: {path.name} (N of M files)" using **N = len(files)** and **M = total CSV rows** (rows with a non-empty `rel_path`). If any rows were skipped: append " · K skipped".
2. **No all-or-nothing:** If some CSV rows have missing paths, **skip those rows**, load the rest, and report N of M and K skipped. Only fail the whole load for hard errors (e.g. CSV unreadable, missing `rel_path` column).
3. **Clear logging:** Keep (or add) a single log line per failed row (path does not exist) so logs are greppable.
4. **Optional GUI reporting:** Optionally, the core can call a small callback for each failed row (e.g. for a future "Load report" panel); not required for the footer message.

---

## Does the core need callbacks to signal back to the GUI?

**For the footer message (N of M · K skipped):** **No.** The core only needs to **return** (or attach) **counts**:

- **Option A (recommended):** Core returns **structured result** instead of raising on invalid paths:
  - `collect_paths_from_csv` returns e.g. `(path_list, total_rows, skipped_count)` where `total_rows` = number of `rel_path` rows considered (non-empty), `skipped_count` = number of invalid/missing paths.
  - No callback required for the footer; the GUI gets `files` plus `files.csv_total_rows` and `files.csv_skipped_count` (or equivalent) and formats the message in `on_done`.

**For per-row failure visibility:**

- **Logging:** Already in place; no callback needed.
- **Optional callback:** If we want the GUI to show "which rows failed" (e.g. in a dialog or report), the core could accept an optional `row_failed_cb(row_index, rel_path, resolved_path)` and call it for each skipped row. This is **optional** and can be added later; the plan below does not depend on it.

---

## Recommended design (summary)

1. **Core: `collect_paths_from_csv`**
   - **Stop raising** when some paths are missing.
   - **Skip** invalid rows (path does not exist); **log** each with the existing f-string warning.
   - **Return** either:
     - a small dataclass/named tuple `CsvCollectResult(path_list, total_rows, skipped_count)`, or
     - keep return type `List[Path]` and add an optional **output** parameter, e.g. `csv_stats: dict | None` that the caller can pass to receive `{"total_rows": M, "skipped_count": K}`.
   - **total_rows** = number of CSV rows with non-empty `rel_path` (the "M").
   - **skipped_count** = number of rows where the resolved path did not exist (the "K").
   - **path_list** = only valid paths (length N).

2. **Core: `KymImageList.load_from_path` (CSV branch)**
   - Call `collect_paths_from_csv`; get back path list and counts.
   - Build `KymImageList` with `file_path_list=path_list`, `csv_source_path=path_obj`.
   - **Attach** M and K to the list so the GUI can read them: e.g. set `files.csv_total_rows = M` and `files.csv_skipped_count = K` (or pass via a small wrapper / attributes on the list).  
   - `AcqImageList` / `KymImageList` would need optional attributes or a single optional `csv_load_stats: dict` (e.g. `{"total_rows": M, "skipped_count": K}`) set only when loaded from CSV.

3. **GUI: `FolderController._start_threaded_load` `on_done`**
   - For CSV: if `files` has `csv_total_rows` (and optionally `csv_skipped_count`), format:
     - `"Loaded CSV: {path.name} ({n} of {m} files)"` and if `csv_skipped_count > 0` append `" · {k} skipped"`.
   - Fallback: if those attributes are missing (e.g. old code path), keep current message e.g. "Loaded CSV: {path.name} ({n} files)".

4. **Tests**
   - CSV with mix of valid and invalid paths: load succeeds with N of M and K skipped; no exception.
   - CSV with all invalid paths: either 0 of M · M skipped, or retain a single exception for "no files loaded" if that is desired.
   - Existing tests that expect `ValueError` when any path is missing must be updated to expect success with skipped count.

---

## Implementation order (when implementing)

1. **progress / types**  
   No new callback type needed for the basic "N of M · K skipped" message. Optional: define `CsvCollectResult` or use a simple dict for stats.

2. **acq_image_list.py**  
   - Change `collect_paths_from_csv` to skip invalid rows (keep logging each), and return path list + total_rows + skipped_count (e.g. return a named tuple or pass stats via an optional out-param).
   - Optionally add `csv_total_rows` / `csv_skipped_count` (or `csv_load_stats`) to `AcqImageList` when constructed from CSV.

3. **kym_image_list.py**  
   - CSV branch: call updated `collect_paths_from_csv`, get counts, construct list, set `csv_total_rows` and `csv_skipped_count` (or `csv_load_stats`) on the instance.

4. **folder_controller.py**  
   - In `on_done`, for CSV and when `files` has total/skipped info: set `load_task.message` and footer to "Loaded CSV: … (N of M files · K skipped)" as above.

5. **Tests**  
   - Update CSV load tests: expect partial load and new message shape; add case for "some rows invalid" and "all rows invalid" if applicable.

---

## Relation to `error-cb-plan.md`

- **error-cb-plan.md** is about **wrap-phase** failures: when we build `KymImage(path)` from a path and the constructor fails (e.g. permission denied reading a companion file). That uses `error_cb(path, exception)` so the GUI can show "X file(s) could not be loaded."
- **This plan** is about **CSV path validation**: rows whose `rel_path` does not exist. Those are handled inside `collect_paths_from_csv`; no `KymImage` is created for them. So we do **not** need `error_cb` for this; we need **counts** (and optional per-row callback) from `collect_paths_from_csv` and a way to attach them to the returned list for the footer.

Both can coexist: after implementation, a CSV load could show e.g. "Loaded CSV: name.csv (58 of 65 files · 5 skipped)" (5 path-missing rows) and, if `error_cb` is implemented, a separate warning like "2 file(s) could not be loaded" for wrap-phase failures.
