# Plan: Add error_cb to AcqImageList Load Pipeline

**Implementation order:** Follow the "Files to Modify" section in order (1 → 5). Each file path is relative to the **kymflow** project root (the directory containing `src/kymflow` and `tests/`).

**Conventions:** Add `error_cb` as an optional parameter after `progress_cb` in every signature. Use keyword-only args where the rest of the API does (e.g. after `*`). Line numbers in the plan (~L...) are approximate; use method and call-site descriptions to locate the correct spots if the code has changed.

## Summary

Add an optional `error_cb` callback to signal when individual files fail to load (e.g., permission denied on macOS). The callback mirrors `cancel_event` and `progress_cb` and allows the GUI to surface non-fatal load errors to the user.

## Problem

When loading a path (folder, file list, or CSV), `AcqImageList._instantiate_image()` constructs `image_cls(**kwargs)` (e.g., `KymImage(path=file_path)`). KymImage can fail when it calls `_readOlympusHeader(path_obj)`, which reads the companion `.txt` file via `with open(olympusTxtPath) as f:` in `read_olympus_header.py` (line 350). On some systems (e.g., macOS Sequoia) the app may lack permission, raising:

```
[Errno 1] Operation not permitted: '/Users/.../20251114_A114_0008.txt'
```

The exception propagates:

1. `read_olympus_header.py:350` – `open(olympusTxtPath)` raises `OSError`
2. `_readOlympusHeader` – no try/except, propagates
3. `KymImage.__init__:53` – `_olympusDict = _readOlympusHeader(path_obj)` propagates
4. `AcqImageList._instantiate_image:303` – `return self.image_cls(**kwargs)` propagates
5. **Caught** by `except Exception as e:` in `_instantiate_image` (lines 304–307)

`_instantiate_image` logs the error and returns `None`. `_wrap_paths` receives `None` and skips the file. No upstream notification occurs; the user only sees logs and may not realize files were skipped.

## Design

### error_cb

- **Signature**: `Callable[[Path, Exception], None] | None`
- **Invocation**: Called when `_instantiate_image` catches an exception, before returning `None`
- **Threading**: Invoked on the worker thread (same as `progress_cb`); UI updates must happen elsewhere (e.g., in `on_done`)

### Does error_cb stop the load?

**No.** `error_cb` is a reporting hook. When a file fails:

1. `_instantiate_image` catches the exception
2. Calls `error_cb(file_path, e)` if provided
3. Returns `None`
4. `_wrap_paths` does not append the failed file but continues to the next one

The load proceeds for all other files. Only the failed file(s) are skipped. If you want “abort on first error,” that would be a separate design (e.g., `error_cb` sets `cancel_event`, or returns a boolean to abort).

## Where ui.notify() is Called

`ui.notify()` runs on the main thread. `error_cb` runs on the worker thread, so it should not call `ui.notify()` directly.

The correct place for `ui.notify()` is in **`FolderController._start_threaded_load`** inside the `on_done` callback (around lines 266–293):

```python
def on_done(result: tuple["KymImageList", Path]) -> None:
    dialog.close()
    files, selected_path = result
    self._app_state._apply_loaded_files(files, selected_path)
    # ... persist config, set title, emit event ...

    # Show success notification
    try:
        if is_csv:
            ui.notify(f"Loaded CSV: {path.name}", type="positive")
        else:
            ui.notify(f"Loaded: {path.name}", type="positive")

        # NEW: If any files failed to load, show warning
        if load_errors:
            ui.notify(
                f"{len(load_errors)} file(s) could not be loaded (e.g., permission denied)",
                type="warning",
            )
    except RuntimeError as e:
        # ... existing exception handling ...
```

Flow:

1. Worker runs, calls `error_cb(path, exc)` for each failed file; `error_cb` appends to `load_errors`.
2. Worker completes and puts `DoneMsg` into the queue.
3. Timer on the main thread drains the queue and calls `on_done`.
4. `on_done` runs on the main thread → safe to call `ui.notify()`.

`load_errors` is defined in the closure around `worker_fn` / `on_done` and is populated by the worker before `on_done` runs.

## Files to Modify

All paths below are relative to the **kymflow** project root (e.g. `kymflow/` when you are in the repo).

### 1. `src/kymflow/core/utils/progress.py`

| Location | Change |
|----------|--------|
| Imports | Ensure `Path` is in scope (already used by `ProgressMessage`). |
| After line `ProgressCallback = Callable[[ProgressMessage], None]` | Add: `ErrorCallback = Callable[[Path, Exception], None]` |

### 2. `src/kymflow/core/image_loaders/acq_image_list.py`

| Location | Change |
|----------|--------|
| Imports | Add `ErrorCallback` to the import from `kymflow.core.utils.progress`. |
| `__init__` (signature ~L79–81) | Add `error_cb: ErrorCallback \| None = None` after `progress_cb`. Pass `error_cb=error_cb` into both `_load_files(...)` calls (file_path_list branch ~L151–155, path branch ~L177–181). |
| `_load_files` (signature ~L312–315) | Add `error_cb: ErrorCallback \| None = None` after `progress_cb`. Pass `error_cb=error_cb` into every `_wrap_paths(...)` call (3 places: ~L322–326, ~L343–347, ~L367–374). |
| `_wrap_paths` (signature ~L690–696) | Add `error_cb: ErrorCallback \| None = None` after `progress_cb`. In the loop, change `_instantiate_image(file_path, blind_index=index)` to `_instantiate_image(file_path, blind_index=index, error_cb=error_cb)`. |
| `_instantiate_image` (signature ~L283) | Add parameter `error_cb: ErrorCallback \| None = None` (after `blind_index`). In the `except Exception as e:` block, before `return None`, add: `if error_cb is not None: error_cb(file_path, e)`. (Keep existing `logger.error` calls; call `error_cb` before `return None`.) |
| `load` (signature ~L378–384) | Add `error_cb: ErrorCallback \| None = None` after `progress_cb`. Pass `error_cb=error_cb` to `_load_files(...)` (~L399–403). |
| `reload` (signature ~L405–410) | Add `error_cb: ErrorCallback \| None = None` after `progress_cb`. Pass `error_cb=error_cb` to `load(...)` (~L413–417). |
| `load_from_path` (signature ~L428–439) | Add `error_cb: ErrorCallback \| None = None` after `progress_cb`. Pass `error_cb=error_cb` into each of the four `return cls(...)` calls only (do **not** add error_cb to `collect_paths_from_csv`). **Exact call sites:** (1) path=None branch: `return cls(path=None, ..., progress_cb=progress_cb, error_cb=error_cb)` (~L453–461). (2) CSV branch: `return cls(file_path_list=..., ..., progress_cb=progress_cb, error_cb=error_cb)` (~L471–479). (3) Single-file branch: `return cls(path=path_obj, ..., progress_cb=progress_cb, error_cb=error_cb)` (~L482–490). (4) Folder branch: `return cls(path=path_obj, ..., progress_cb=progress_cb, error_cb=error_cb)` (~L493–502). |

### 3. `src/kymflow/core/image_loaders/kym_image_list.py`

| Location | Change |
|----------|--------|
| Imports | Add `ErrorCallback` to the import from `kymflow.core.utils.progress` (same line as `CancelledError`, `ProgressCallback`, `ProgressMessage`). |
| `__init__` (signature ~L78–80) | Add `error_cb: ErrorCallback \| None = None` after `progress_cb`. Pass `error_cb=error_cb` in `super().__init__(..., progress_cb=progress_cb, error_cb=error_cb)` (~L104–115). |
| `load_from_path` (signature ~L136–139) | Add `error_cb: ErrorCallback \| None = None` after `progress_cb`. Pass `error_cb=error_cb` in every `return cls(...)`: (1) path=None branch (~L164–166), (2) CSV branch (~L174–181), (3) single-file branch (~L184–191), (4) folder branch (~L193–200). |

### 4. `src/kymflow/gui_v2/state.py`

| Location | Change |
|----------|--------|
| Imports | Add `ErrorCallback` to the import from `kymflow.core.utils.progress` (e.g. `from kymflow.core.utils.progress import ProgressCallback, ErrorCallback`). |
| `_build_files_for_path` (signature ~L153–161) | Add `error_cb: ErrorCallback \| None = None` after `progress_cb`. Pass `error_cb=error_cb` into `KymImageList.load_from_path(..., progress_cb=progress_cb, error_cb=error_cb)` (~L175–182). |

### 5. `src/kymflow/gui_v2/controllers/folder_controller.py`

| Location | Change |
|----------|--------|
| `_start_threaded_load` | Before defining `worker_fn`, define `load_errors: list[tuple[Path, Exception]] = []` and `def capture_error(path: Path, exc: Exception) -> None: load_errors.append((path, exc))`. At start of `worker_fn`, add `load_errors.clear()`. Pass `error_cb=capture_error` into `_build_files_for_path(...)`. Inside `on_done`, after the existing success `ui.notify` block (and inside the same `try`), add: `if load_errors: ui.notify(f"{len(load_errors)} file(s) could not be loaded (e.g., permission denied)", type="warning")`. |

Worker closure sketch:

```python
load_errors: list[tuple[Path, Exception]] = []

def capture_error(path: Path, exc: Exception) -> None:
    load_errors.append((path, exc))

def worker_fn(cancel_event, progress_cb):
    load_errors.clear()
    result = self._app_state._build_files_for_path(
        path,
        depth=depth,
        cancel_event=cancel_event,
        progress_cb=progress_cb,
        error_cb=capture_error,
    )
    # ...
```

## Tests

Add tests in **`tests/core/test_acq_image_list.py`**:

- `error_cb` is called when `_instantiate_image` fails (e.g. mock `image_cls` to raise).
- `error_cb` is not called when load succeeds.
- Load continues after a failure; other files are still loaded.

## Implementation checklist (run in order)

1. **progress.py** – Add `ErrorCallback` type alias.
2. **acq_image_list.py** – Import `ErrorCallback`; add `error_cb` param to `__init__`, `_load_files`, `_wrap_paths`, `_instantiate_image`, `load`, `reload`, `load_from_path`; thread through all call sites; in `_instantiate_image` except block call `error_cb(file_path, e)` when `error_cb` is not None.
3. **kym_image_list.py** – Import `ErrorCallback`; add `error_cb` to `__init__` and `load_from_path`; pass through to `super().__init__` and all `cls(...)` returns.
4. **state.py** – Import `ErrorCallback`; add `error_cb` to `_build_files_for_path` and pass to `KymImageList.load_from_path`.
5. **folder_controller.py** – In `_start_threaded_load`: add `load_errors` and `capture_error`; pass `error_cb=capture_error` to `_build_files_for_path`; in `on_done` add `ui.notify` when `load_errors` is non-empty.
6. **tests** – Add tests in `tests/core/test_acq_image_list.py` as above.

## Out of Scope

- Changing `read_olympus_header.py` to catch/handle permission errors locally (current design: let exceptions propagate to `_instantiate_image`)
- Aborting the load on first error (would require an additional design decision)
- ThreadJobRunner changes (worker still receives only `cancel_event` and `progress_cb`; `error_cb` is captured in the closure)
