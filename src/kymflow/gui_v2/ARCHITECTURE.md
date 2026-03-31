## GUI v2 architecture (overview)

This document captures the current architecture of `kymflow.gui_v2`. It is the
authoritative description of how the GUI is wired and should be kept up-to-date
when the architecture evolves.

### Core building blocks

- **AppContext**
  - Singleton (`AppContext`) created in `app_context.py`.
  - Owns:
    - `app_state: AppState` – shared GUI state (files, selections, theme).
    - `home_task: TaskState` – long-running task state for the home page
      (analyze flow, save, load, etc.).
    - `batch_task`, `batch_overall_task: TaskState` – batch-analysis tasks.
    - `user_config`, `app_config`, `runtime_env`.

- **AppState**
  - Defined in `state.py`.
  - Holds:
    - `folder: Path | None` – selected folder/file/CSV path.
    - `files: KymImageList` – list of loaded `KymImage` objects.
    - `selected_file: KymImage | None`.
    - `selected_roi_id: int | None`.
    - Theme and plotting-related state.
  - Key methods:
    - `load_path(path, depth)` – synchronous load of folder/file/CSV.
    - `_build_files_for_path(...)` – worker-safe file scanning with a
      `ProgressCallback`.
    - `select_file(...)`, `select_roi(...)`, `select_velocity_event(...)`.

- **EventBus**
  - Implemented in `bus.py`.
  - One `EventBus` per NiceGUI client.
  - Typed, phase-aware API:
    - `subscribe_intent`, `subscribe_state`.
    - `emit(event)` with optional `event.phase ∈ {"intent", "state"}`.

- **Events**
  - **Intent / state events** in `events.py`:
    - Examples: `FileSelection`, `ROISelection`, `AnalysisStart`,
      `SaveSelected`, `SaveAll`.
  - **Path selection events** in `events_folder.py`:
    - `SelectPathEvent`, `CancelSelectPathEvent`.
  - **State notifications** in `events_state.py`:
    - `FileListChanged`, `ThemeChanged`, `TaskStateChanged`, `AnalysisCompleted`,
      `RadonReportUpdated`, `VelocityEventDbUpdated`.

- **Task system**
  - Core `TaskState` in `kymflow.core.state`.
  - `TaskStateBridgeController`:
    - Observes a `TaskState` and emits `TaskStateChanged` on the bus with
      `task_type` (`"home"`, `"batch"`, `"batch_overall"`).
  - Analysis and loading use two styles:
    - `tasks.run_flow_analysis` / `run_batch_flow_analysis`:
      - Background thread + `queue.Queue` → updates `TaskState`.
    - `ThreadJobRunner` for folder/CSV loads:
      - Background thread + `queue.Queue[WorkerMsg]` → view/controller callbacks.

- **TaskState instances**
  - `home_task` – long-running operations on the Home page (analysis, save).
  - `load_task` – folder/CSV loads (path changes).
  - `batch_task`, `batch_overall_task` – batch analysis.

### Controllers, views, bindings

- **Controllers** (in `controllers/`) consume *intent* events and update
  `AppState`/`TaskState` and/or backend:
  - `FolderController` – handles `SelectPathEvent(intent)` and loads folders,
    files, and CSVs into `AppState` using `ThreadJobRunner`.
  - `FileSelectionController`, `ROISelectionController`,
    `KymEventSelectionController` – selection controllers.
  - `AnalysisController` – handles `AnalysisStart(intent)` / `AnalysisCancel`
    and runs flow analysis (Radon) using `tasks.run_flow_analysis` with
    `home_task`.
  - `SaveController` – handles `SaveSelected(intent)` / `SaveAll(intent)`,
    saves analysis results, updates radon/velocity DBs, and uses `home_task`.
  - `TaskStateBridgeController` – bridges `TaskState` → `TaskStateChanged`.
  - Additional controllers for metadata, ROI, events, etc.

- **Views** (in `views/`) are thin UI wrappers around NiceGUI/nicewidgets:
  - `FolderSelectorView` – Open Folder/Open File/Open CSV, recent paths, save
    buttons.
  - `FileTableView`, `ImageLineViewerView`, `KymEventView`, drawer tabs, etc.
  - `TaskProgressView` – progress bar + message for `TaskStateChanged`.
  - `FooterView` – compact footer with selection, last event, and progress.

- **Bindings** (in `views/`) subscribe to *state* events and call view methods:
  - `FileTableBindings`, `FolderSelectorBindings`, `ImageLineViewerBindings`,
    `KymEventBindings`, etc.
  - `TaskProgressBindings`:
    - Subscribes to `TaskStateChanged(task_type="home")`.
    - Calls `TaskProgressView.set_task_state(...)`.

### Signal flow patterns

#### 1. Analyze Flow (home page)

1. **User action**
   - User clicks “Analyze Flow” in `AnalysisToolbarView`.
2. **Intent event**
   - `AnalysisToolbarView` emits `AnalysisStart(window_size, roi_id, phase="intent")`.
3. **Controller**
   - `AnalysisController` (subscribed with `subscribe_intent`) receives
     `AnalysisStart` and starts analysis:
     - Uses `AppContext.home_task: TaskState` to track progress and
       cancellation.
     - Calls `tasks.run_flow_analysis(kym_file, home_task, ...)`.
4. **Background work**
   - `run_flow_analysis`:
     - Spawns a worker thread that pushes progress messages into a
       `queue.Queue`.
     - A `ui.timer` drains the queue on the NiceGUI thread and:
       - Calls `home_task.set_progress(pct, "X/Y windows")`.
       - Calls `home_task.set_running(True)` / `mark_finished()`.
5. **Bridge → bus**
   - `TaskStateBridgeController(context.home_task, bus, task_type="home")`
     observes changes and emits `TaskStateChanged` (phase `"state"`) on the bus.
6. **Views**
   - `TaskProgressBindings` receives `TaskStateChanged(task_type="home")` and
     calls `TaskProgressView.set_task_state(...)`.
   - `FooterController` also receives the same `TaskStateChanged` and:
     - Calls `FooterView.set_progress(...)`.
     - Updates “last event” when the task starts or finishes.

This makes Analyze Flow progress fully bus-based and shared between the drawer
task widget and the global footer.

#### 2. Save Selected / Save All

1. **User action**
   - User clicks “Save Selected” or “Save All” in `FolderSelectorView`.
2. **Intent event**
   - `FolderSelectorView` emits `SaveSelected(phase="intent")` or
     `SaveAll(phase="intent")` via `on_save_selected` / `on_save_all` callbacks
     (wired to `bus.emit` in `HomePage`).
3. **Controller**
   - `SaveController` subscribes with `subscribe_intent` and:
     - For “selected”:
       - Uses `home_task` to gate the UI (`set_running(True)`, then
         `mark_finished()`).
       - Runs `kym_analysis.save_analysis()` via `run.io_bound`.
     - For “all”:
       - Iterates files and uses `run.io_bound` per file.
       - Updates radon and velocity DB caches and emits:
         - `VelocityEventDbUpdated()`.
         - `FileListChanged(files=list(app_state.files))`.
4. **Bridge → bus**
   - `TaskStateBridgeController` emits `TaskStateChanged(task_type="home")`
     reflecting save progress/state.
5. **Views**
   - `TaskProgressView` and `FooterView` both see the same
     `TaskStateChanged` updates. Footer’s “last event” is set from:
     - `SaveSelected` / `SaveAll` *intent* events at start.
     - `TaskStateChanged` messages on completion/error.

#### Velocity-event DB (in-memory vs CSV)

- **In-memory cache**: `KymImageList.update_velocity_event_cache_only` and GUI-driven
  refreshes keep the velocity-event DataFrame aligned with `KymAnalysis` on each
  `KymImage`. Batch kym-event analysis defers cache updates until the batch worker
  finishes, then updates the cache once for successful files and emits a single
  `VelocityEventDbUpdated` (no CSV write).
- **CSV persistence**: The on-disk `kym_event_db.csv` (and related save helpers such as
  `update_velocity_event_for_image`, `save_velocity_event_db`, `rebuild_velocity_event_db_and_save`)
  are used **only** on explicit user save flows (e.g. `SaveController` handling
  `SaveSelected` / `SaveAll`). Routine detection and batch analysis do **not** persist
  the velocity-event DB to CSV.
- **Batch suppression**: While a batch kym-event run is active, `AppContext.suppress_velocity_event_cache_sync_on_detect_events`
  is set so `KymEventCacheSyncController` ignores per-file `DetectEvents` (state) and
  avoids per-file `VelocityEventDbUpdated` emissions; see `tasks.run_batch_kym_event_analysis`.

#### 3. Open Folder / Open CSV (threaded loads)

1. **User action**
   - User:
     - Picks a recent path from `FolderSelectorView`, or
     - Clicks “Open folder”, “Open file”, or “Open CSV”.
2. **Intent event**
   - `FolderSelectorView` emits `SelectPathEvent(new_path, depth, phase="intent")`.
3. **Controller**
   - `FolderController` subscribes with `subscribe_intent` and:
     - Validates the path and detects type (file/folder/CSV).
     - Checks for unsaved analysis and, if necessary, shows an unsaved-changes
       dialog.
     - For threaded loads (folders and CSVs), calls `_start_threaded_load(...)`.
4. **Threaded load + dialog**
   - `_start_threaded_load`:
     - Creates a `ui.dialog` with:
       - Title “Loading files…”.
       - A label for textual progress.
       - A `ui.linear_progress` bar.
       - A “Cancel” button wired to `ThreadJobRunner.cancel()`.
     - Starts a `ThreadJobRunner` job which:
       - Calls `AppState._build_files_for_path(...)` in a worker thread.
       - Emits `ProgressMsg` / `DoneMsg` / `CancelledMsg` / `ErrorMsg` back to
         the main thread.
     - `on_progress`, `on_done`, `on_cancelled`, `on_error` update the dialog.
5. **TaskState integration for footer (dedicated load task)**
   - `FolderController` optionally receives `load_task_state` (wired from
     `AppContext.load_task` on the Home page).
   - When `load_task_state` is provided:
     - `_start_threaded_load` calls:
       - `load_task_state.cancellable = True`.
       - `load_task_state.set_running(True)`.
       - `load_task_state.set_progress(0.0, "Loading files...")`.
     - `on_progress` maps `ProgressMessage` into:
       - `load_task_state.set_progress(fraction, formatted_message)`.
     - `on_done` sets:
       - `load_task_state.message = "Load complete"`.
       - `load_task_state.mark_finished()`.
     - `on_cancelled` sets:
       - `load_task_state.message = "Load cancelled"`.
       - `load_task_state.mark_finished()`.
     - `on_error` sets:
       - `load_task_state.message = f"Load error: {exc}"`.
       - `load_task_state.mark_finished()`.
6. **Bridge → bus**
   - `TaskStateBridgeController` for `load_task` emits corresponding
     `TaskStateChanged(task_type="load")` events.
7. **Views**
   - Existing **dialog** remains unchanged and is still the primary detailed
     visualization for load progress.
   - In parallel:
     - `FooterView` shows load progress via `TaskStateChanged(task_type="load")`.
     - `FooterController` also listens to `SelectPathEvent(intent)` to set
       “Load: <path>” as the initial last-event text, and then updates it based
       on `TaskStateChanged(task_type="load")` when the load finishes or fails.

### Footer architecture

- **FooterView** (`views/footer_view.py`)
  - Renders a single `ui.footer` with three regions:
    - **Left**: selection summary label –
      `"<file> · <channel> · ROI #<id>"`, e.g. `name.tif · Ch1 · ROI #3`.
    - **Center**: “last event” label (high-level, user-visible status).
    - **Right**: compact `ui.linear_progress` + small text label.
  - Public methods:
    - `render()` – create the footer UI.
    - `set_selection_summary(file_name, channel_label, roi_id)`.
    - `set_last_event(text)`.
    - `set_progress(running, progress, message)`.

- **FooterController** (`controllers/footer_controller.py`)
  - Constructed on the Home page in `_ensure_setup()`:
    - `FooterController(context.app_state, bus, footer_view)`.
  - Subscribes to:
    - `FileSelection(phase="state")` → updates file name and ROI.
    - `ROISelection(phase="state")` → updates ROI.
    - `TaskStateChanged(phase="state", task_type="home")` → mirrors progress
      into `FooterView.set_progress(...)` and updates “last event” on major
      transitions.
    - High-level *intent* events:
      - `AnalysisStart(intent)` → “Analysis: starting flow analysis”.
      - `SaveSelected(intent)` → “Save: saving selected file”.
      - `SaveAll(intent)` → “Save: saving all files”.
      - `SelectPathEvent(intent)` → “Load: <path_name>”.
  - Behaviour:
    - Uses `FileSelection` state events as the primary source of selection
      context (file and ROI).
    - Uses `TaskStateChanged(task_type="home")` as the single, bus-based source
      of long-running task progress for:
      - Analyze Flow.
      - Save Selected / Save All.
      - Folder / CSV loads (via `FolderController` + `home_task`).
    - Only updates “last event” for:
      - Task start.
      - Completion.
      - Cancel/error.

#### Future footer enhancements (TODO)

- Consider extending the footer selection summary to also show parent and
  grandparent folders for the currently selected file, alongside the existing
  `file · channel · ROI` display.

### Home page layout and wiring

- **Layout**
  - `HomePage` in `pages/home_page.py`:
    - `render()`:
      - Sets `ui.page_title`.
      - Calls `navigation.build_header(context, dark_mode, ...)`.
      - Calls `self._footer_view.render()` to build the global footer.
      - Builds a full-height `ui.splitter` that contains:
        - Left: drawer with analysis, contrast, metadata, options, etc.
        - Right: main content (folder selector, file table, image/line view,
          events, plot pool).

- **Controller setup**
  - `_ensure_setup()` (called once per client) creates:
    - All controllers (folder, selection, analysis, save, ROI, events, etc.).
    - All bindings (file table, folder selector, image viewer, etc.).
    - `TaskStateBridgeController(context.home_task, bus, task_type="home")`.
    - `FooterController(context.app_state, bus, footer_view)`.
  - `FolderController` is constructed with:
    - `FolderController(context.app_state, bus, context.user_config, task_state=context.home_task)`.
  - `SaveController` and `AnalysisController` also receive `context.home_task`
    to drive the same `TaskState` that the footer and task-progress drawer rely
    on.

### Conventions for future changes

When extending `gui_v2`:

- Prefer the **intent → controller → AppState/TaskState → bridge → state events
  → bindings → views** pattern instead of directly mutating views from random
  locations.
- For long-running work on the Home page:
  - Use `AppContext.home_task` as the single `TaskState` input.
  - Ensure `TaskStateBridgeController` (already wired) emits
    `TaskStateChanged(task_type="home")`.
  - Let both `TaskProgressView` and `FooterView` observe progress from the bus.
- For new user-visible status messages:
  - Prefer routing them through the footer’s “last event” semantics rather than
    `ui.notify`, except for truly interruptive toasts.
- Keep this `ARCHITECTURE.md` updated when:
  - You add new cross-cutting controllers or flows.
  - You change how tasks, progress, or selection are modelled.

