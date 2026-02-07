# Developer Roadmap: Threaded Path Loading in NiceGUI for kymflow

## Overview

This document describes the end-to-end strategy and concrete implementation plan for adding **threaded path loading** to the kymflow NiceGUI application, with **real progress reporting** and **true cancellation**.

The design explicitly separates:
- **Core (pure Python, no UI)** responsibilities
- **GUI v2 (NiceGUI)** responsibilities
- **Threading and progress plumbing** between them

This roadmap reflects the *validated sandbox prototype* and maps it directly onto the existing kymflow codebase.

---

## Goals

- Keep NiceGUI UI responsive while loading large datasets (hundreds+ files).
- Provide continuous, meaningful progress feedback.
- Support cancellation that stops work quickly and does **not** apply partial results.
- Avoid UI corruption by enforcing strict UI-thread ownership.
- Preserve backward compatibility for non-GUI / blocking usage.

---

## High-Level Strategy

1. **Thread boundary**
   - Only *pure work* runs in a background thread:
     - filesystem traversal
     - CSV parsing
     - AcqImageList / KymImage construction
   - No NiceGUI imports or UI mutation in worker threads.

2. **UI thread owns state mutation**
   - Assign `AppState.files`
   - Assign `AppState.folder`
   - Fire file-list change handlers
   - Select the active file

3. **Communication via ThreadJobRunner**
   - Worker sends progress + completion messages via queue
   - UI polls queue using `ui.timer(...)`
   - UI callbacks handle progress, completion, cancellation, errors

4. **UX policy**
   - One load job at a time (guard with `is_running()`)
   - Optional job-id gating retained as a safety invariant

---

## Repository Context

### Core
- `src/kymflow/core/image_loaders/acq_image_list.py`
- `src/kymflow/core/image_loaders/acq_image.py`
- `src/kymflow/core/image_loaders/kym_image.py`
- `src/kymflow/core/utils/`

### GUI v2
- `src/kymflow/gui_v2/state.py`
- `src/kymflow/gui_v2/controllers/folder_controller.py`
- `src/kymflow/gui_v2/thread_job_runner.py`

### Proven Sandbox
- `sandbox/nicegui-threads/`
- Native NiceGUI (`native=True`)
- Path: `/Users/cudmore/Dropbox/data/declan/2026/compare-condiitons/v1-analysis`
- Depth: `3`
- Uses `KymImage(..., load_image=False)`

---

## Step 0 — Core Progress Contract

### New file
**`src/kymflow/core/utils/progress.py`**

Defines a tiny, UI-agnostic progress message:

```python
@dataclass(frozen=True)
class ProgressMessage:
    phase: str
    done: int = 0
    total: Optional[int] = None
    detail: str = ""
    path: Optional[Path] = None
```

Also define:
```python
ProgressCallback = Callable[[ProgressMessage], None]
```

### Standard phases
- `scan`
- `read_csv`
- `wrap`
- `metadata` (optional)
- `load_image` (optional)
- `done`

---

## Step 1 — AcqImageList: real progress + real cancel

### File
**`src/kymflow/core/image_loaders/acq_image_list.py`**

### Signature additions (backward compatible)
```python
cancel_event: threading.Event | None = None
progress_cb: ProgressCallback | None = None
```

### Static path collectors
Add:
- `collect_paths_from_folder(...)`
- `collect_paths_from_csv(...)`
- `collect_paths_from_file(...)`

These return `list[Path]` and emit scan/read progress.

### Progress + cancel behavior
- Folder scan:
  - emit `scan` start (indeterminate)
  - check cancel during traversal
  - emit `scan` completion with total
- CSV read:
  - emit `read_csv` start/end
- Wrap loop:
  - emit `wrap` progress every N items
  - check cancel per iteration
- On cancel:
  - raise a cancellation exception
  - do **not** apply partial results

---

## Step 2 — AcqImage / KymImage hooks

### Files
- `src/kymflow/core/image_loaders/acq_image.py`
- `src/kymflow/core/image_loaders/kym_image.py`

### Add optional args
```python
cancel_event: threading.Event | None = None
progress_cb: ProgressCallback | None = None
```

Initially these may be pass-through only, but enable future:
- metadata progress
- image loading cancellation

---

## Step 3 — AppState split (GUI v2)

### File
**`src/kymflow/gui_v2/state.py`**

### Worker-safe builder
```python
_build_files_for_path(path, depth) -> (AcqImageList, selected_path)
```

- Pure Python
- CSV/file/folder detection
- Calls AcqImageList with cancel/progress hooks
- No UI handlers

### UI-thread applier
```python
_apply_loaded_files(files, selected_path)
```

- Assigns state
- Fires handlers
- Selects first file

### Keep `load_path` as blocking wrapper (optional)
Used for tests or CLI.

---

## Step 4 — ThreadJobRunner (GUI v2)

### File
**`src/kymflow/gui_v2/thread_job_runner.py`**

Responsibilities:
- Start one background thread job
- Maintain cancel event
- Queue progress messages
- Poll queue via `ui.timer`
- Invoke UI callbacks:
  - `on_progress`
  - `on_done`
  - `on_cancelled`
  - `on_error`
- Provide `is_running()` guard

---

## Step 5 — FolderController wiring

### File
**`src/kymflow/gui_v2/controllers/folder_controller.py`**

### Flow
1. UI button / intent event fires
2. Controller validates path + depth
3. Guard: refuse start if job running
4. Show progress dialog
5. Start ThreadJobRunner

### Worker function
- Calls `AppState._build_files_for_path(...)`
- Receives cancel_event + progress_cb
- Returns `(files, selected_path)`

### UI callbacks
- `on_progress`: update label + progress bar
- `on_done`: call `_apply_loaded_files`, update title, persist config
- `on_cancelled`: close dialog, revert path if needed
- `on_error`: notify + revert

---

## Handling the 3 init modes

### Folder + depth
- Always threaded
- Real scan + wrap progress
- Cancelable mid-scan and mid-wrap

### Single tif
- Prefer synchronous path (no thread overhead)
- Optionally allow threaded path for uniformity

### CSV
- Threaded
- `read_csv` phase + `wrap` phase
- Cancel during wrap

---

## Cancellation semantics

- Default: **discard partial results**
- Cancel raises internally
- Runner triggers `on_cancelled`
- UI keeps previous table/state

---

## End-to-End Flow Summary

1. User selects path
2. FolderController receives intent
3. ThreadJobRunner starts
4. Worker builds AcqImageList (core)
5. Core emits ProgressMessage
6. UI updates progress via timer
7. On success, UI applies state atomically
8. Handlers fire, plots/tables update

---

## Testing Checklist

### Sandbox
- UI never freezes
- Progress updates smoothly
- Cancel prevents state changes

### Core tests
- Folder depth correctness
- CSV validation
- Cancel stops early
- Progress phase ordering

### GUI tests
- is_running guard
- Correct callbacks fired

---

## Key Invariants

- No NiceGUI imports in core
- Worker threads never touch UI
- UI thread owns all state mutation
- Atomic state swap on completion
- One job at a time UX policy

---

## Recommended Implementation Order

1. Add ProgressMessage + callback type
2. Extend AcqImageList (progress + cancel)
3. Extend AcqImage / KymImage
4. Split AppState build/apply
5. Integrate ThreadJobRunner
6. Enable real progress UI
