## Agent guidelines for kymflow/gui_v2

### Framework and environment

- The GUI is built on **NiceGUI (currently 3.7.1)**.
- Do not change NiceGUI APIs or assume a different version unless the user explicitly requests a framework or version bump.
- GUI tests for `gui_v2` should be runnable via:

  ```bash
  cd kymflow
  uv run pytest tests/gui_v2
  ```

  and must respect `KYMFLOW_DISABLE_FILE_LOG=1` to avoid writing real log files in test runs.

### Documentation and style

- All new or modified **classes** and **functions** must include **Google‑style docstrings**:
  - One‑line summary.
  - `Args:` section describing every parameter and its meaning.
  - `Returns:` section (or note that it returns `None`).
  - `Raises:` when relevant for nontrivial public APIs.
- Add inline comments only where the logic is nontrivial or surprising; do **not** narrate obvious code.

### Fail-fast vs. defensive code

For code under `kymflow/src/kymflow/gui_v2` and closely related NiceGUI/nicewidgets glue:

- Prefer **fail‑fast** behavior for our own domain objects (e.g. `KymImage`, `AppState`, ROI/Kym controllers).
- Avoid introducing these patterns unless interacting with truly external / dynamic data (and document why there):
  - `dict.get("key", <default>)` or `.get("key") or {}` used to dodge `KeyError` on structures that should always have that key.
  - `getattr(obj, "attr", <default>)` or `hasattr(obj, "attr")` on attributes that should always exist on our own types.
  - `try/except` that only logs and returns around ROI or Kym event operations (e.g. `create_roi`, `edit_roi`, `add_velocity_event`, `delete_velocity_event`).
- If you must use defensive handling for an external or untyped API (e.g. Plotly JSON, browser messages), add a short comment explaining *why* defensive behavior is required at that call site.

### Event-bus architecture

- Respect the **intent vs state** split:
  - `phase="intent"`: user actions / requests.
  - `phase="state"`: confirmed model changes.
- Reuse existing events unless the user asks for a new event type:
  - For "file's structure/metadata changed", prefer `FileChanged(state, change_type=...)`.
  - For selections, use `FileSelection`, `ROISelection`, `EventSelection`, `ChannelSelection`.
- Avoid introducing new state‑phase ROI or Kym events when `FileChanged(state)` + selection events are sufficient.

### ROI and Kym controllers

- **ROI CRUD and selection**:
  - All ROI add/edit/delete + ROISelection intents are handled by `RoiController`.
  - Do not add new micro‑controllers for ROI CRUD or selection; integrate with `RoiController`.
  - `ImageLineViewerV2View` / `ImageRoiWidget` are the only places for user‑driven ROI CRUD; do not reintroduce ROI add/edit/delete widgets in the analysis toolbar.

- **Kym events (velocity events)**:
  - `KymEventController` handles Add/Delete/velocity-update intents, mirrors `SetKymEventRangeState` intent to state, and emits `InteractionBlocked` (state) for global UI blocking during range mode.
  - `KymEventCacheSyncController` remains the focused cache-sync listener.
  - Do not create new `AddKymEvent*` / `DeleteKymEvent*` micro-controllers; extend `KymEventController` when adding related flows.

### UI changes

- Do not introduce new tabs, panels, or major sections in the GUI unless the user explicitly requests them.
- Keep existing UX patterns (e.g., left control bar, drawer structure) unless asked to redesign them.
