# Todo: Improve File-Load Exception Handling

This document summarizes the analysis of exception handling in the AcqImageList load pipeline and provides a focused strategy with concrete code to improve it.

---

## 1. Problem Summary

- **Where:** `kymflow/src/kymflow/core/image_loaders/acq_image_list.py`, method `_instantiate_image` (approx. lines 314–352).
- **Current behavior:** A single broad `except Exception as e:` catches all failures when instantiating an image (e.g. `KymImage(path=...)`). It logs the error (including duplicate traceback via `logger.exception` and `traceback.format_exc()`), then returns `None`. The caller `_wrap_paths` skips the file; the user is not notified.
- **Observed failure:** During debugging, the real error was **not** in the image constructor itself but several frames below: **`ValueError: assignment destination is read-only`** in `kymflow/core/analysis/utils.py`, function `_removeOutliers_sd` (line 46). The call chain was:
  - `_instantiate_image` → `image_cls(**kwargs)` → `KymImage.__init__` → `KymAnalysis.__init__` → `load_analysis()` → `import_v0_analysis()` → `_make_velocity_df()` → `_removeOutliers_sd()`. The fix for that specific bug was to use a writable copy in `_removeOutliers_sd` (`_y = y.copy()`), but the **exception-handling strategy** in `_instantiate_image` remains broad and opaque.

**Issues with current approach:**

1. **Bare `except Exception`** – Catches everything, including programming errors, and makes it hard to distinguish “expected” load failures (e.g. permission, missing file, read-only array in frozen app) from bugs.
2. **Duplicate traceback** – Both `logger.exception(...)` and `logger.error(traceback.format_exc())` log the same traceback; redundant and noisy.
3. **No user-visible feedback** – Callers (e.g. folder load) have no way to report “N file(s) could not be loaded” unless we add an explicit callback or return structure.

---

## 2. Focused Strategy

1. **Catch specific “skip this file” exceptions first** (e.g. `OSError`, `ValueError` for known cases like read-only assignment), log a short message and optionally `exc_info` for the first few failures, then return `None`.
2. **Use a single traceback log in the fallback** – In the broad `except Exception` fallback, use **only** `logger.exception(...)` (or `logger.error(..., exc_info=True)`), not both plus `traceback.format_exc()`.
3. **Add an optional `error_cb`** – When a file fails to load, call `error_cb(file_path, exc)` if provided, so the GUI can collect failures and show a summary (e.g. “N file(s) could not be loaded”) in `on_done`. This is already designed in `docs/plans/error-cb-plan.md`.
4. **Keep the broad catch as a safety net** – So one bad file never crashes the whole load; unexpected exceptions still get one full traceback and return `None`.

---

## 3. Files and Functions Involved

| File | Function / location | Role |
|------|----------------------|------|
| `src/kymflow/core/utils/progress.py` | After `ProgressCallback` | Define `ErrorCallback = Callable[[Path, Exception], None]`. |
| `src/kymflow/core/image_loaders/acq_image_list.py` | `_instantiate_image` | Catch specific exceptions first; call `error_cb`; single traceback in fallback. |
| `src/kymflow/core/image_loaders/acq_image_list.py` | `__init__`, `_load_files`, `_wrap_paths`, `load`, `reload`, `load_from_path` | Thread `error_cb` through the load pipeline. |
| `src/kymflow/core/image_loaders/kym_image_list.py` | `__init__`, `load_from_path` | Pass `error_cb` to `super()` and `cls(...)`. |
| `src/kymflow/gui_v2/state.py` | `_build_files_for_path` | Accept `error_cb` and pass to `KymImageList.load_from_path`. |
| `src/kymflow/gui_v2/controllers/folder_controller.py` | `_start_threaded_load`, `on_done` | Collect errors via `error_cb`; show `ui.notify` when `load_errors` non-empty. |

The full step-by-step for threading `error_cb` is in **`docs/plans/error-cb-plan.md`**. Below we focus on the exception-clause changes in `acq_image_list.py`.

---

## 4. Code: Exception Handling in `_instantiate_image`

**Current (simplified):**

```python
        except Exception as e:
            logger.exception(f"AcqImageList: could not load file: {file_path}")
            logger.error(f"  -->> e:{e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
```

**Proposed:**

- Add parameter `error_cb: ErrorCallback | None = None` to `_instantiate_image` (and thread it from `_wrap_paths` and above).
- Replace the single broad `except Exception` with:
  - Optional: catch **specific** exceptions first (e.g. `OSError`, `ValueError`), log a short message, call `error_cb(file_path, e)` if provided, return `None`.
  - One **fallback** `except Exception`: log **once** with full traceback (e.g. `logger.exception`), call `error_cb(file_path, e)` if provided, return `None`.

Example structure (no change to control flow elsewhere):

```python
    def _instantiate_image(
        self,
        file_path: Path,
        *,
        blind_index: int | None = None,
        error_cb: ErrorCallback | None = None,
    ) -> Optional[T]:
        # ... existing docstring and try block (kwargs_full, retries) ...

        except (OSError, ValueError) as e:
            # Expected per-file failures: permission, read-only array, etc.
            logger.warning("AcqImageList: could not load file %s: %s", file_path, e)
            if error_cb is not None:
                error_cb(file_path, e)
            return None
        except Exception as e:
            # Unexpected; log full traceback once and report.
            logger.exception("AcqImageList: could not load file %s", file_path)
            if error_cb is not None:
                error_cb(file_path, e)
            return None
```

- **Remove** the duplicate `logger.error(f"  -->> e:{e}")` and `logger.error(traceback.format_exc())`; `logger.exception` is sufficient for the fallback.
- **ErrorCallback** type and threading of `error_cb` through `_wrap_paths`, `_load_files`, `__init__`, `load`, `reload`, and `load_from_path` (and then through KymImageList, state, folder_controller) as in `docs/plans/error-cb-plan.md`.

---

## 5. Code: Optional Narrowing of Exceptions

If you prefer to **only** reduce noise and keep one broad catch (no specific `OSError`/`ValueError` branch), use:

```python
        except Exception as e:
            logger.exception("AcqImageList: could not load file %s", file_path)
            if error_cb is not None:
                error_cb(file_path, e)
            return None
```

And remove the extra `logger.error` and `traceback.format_exc()` calls. This still improves clarity (single traceback, optional user feedback via `error_cb`).

---

## 6. Reference: Where the Read-Only Error Was

- **File:** `src/kymflow/core/analysis/utils.py`
- **Function:** `_removeOutliers_sd(y: np.ndarray)`
- **Line (approx.):** 46 (in-place assignment `_y[_greater] = np.nan`).
- **Fix already applied:** Use a writable copy, e.g. `_y = y.copy()` at the start of the function, so the destination is never read-only. This avoids the `ValueError` in frozen apps; the exception-handling improvements above ensure that if similar issues appear elsewhere, the load still doesn’t crash and the user can be notified via `error_cb`.

---

## 7. Checklist

- [ ] Add `ErrorCallback` in `progress.py` and thread `error_cb` through the load pipeline (see `error-cb-plan.md`).
- [ ] In `_instantiate_image`: add `error_cb` parameter; call `error_cb(file_path, e)` in both exception branches (if provided).
- [ ] In `_instantiate_image`: remove duplicate traceback logging; use a single `logger.exception` in the broad `except Exception`.
- [ ] (Optional) Add a specific `except (OSError, ValueError)` before the broad `Exception` for clearer logs and future differentiation (e.g. permission vs programming error).
- [ ] In folder_controller `on_done`: if `load_errors` is non-empty, show `ui.notify(..., type="warning")` (see `error-cb-plan.md`).
