# sandbox/nicegui-threads/README.md

This sandbox demo reproduces your UI-freeze issue (blocking `AcqImageList(...)`) and demonstrates
a threaded alternative that stays responsive and shows progress, using your real classes:

- `from kymflow.core.image_loaders.kym_image import KymImage`
- `from kymflow.core.image_loaders.acq_image_list import AcqImageList`

## Files

- `thread_job_runner.py`
  - Background-thread helper: worker emits progress into a queue; UI polls via `ui.timer`.
  - Includes optional **latest-job-wins** gating (job_id).

- `demo_acqimagelist_loader.py`
  - NiceGUI app with buttons:
    - **Load (blocking)**: calls `AcqImageList(...)` on UI thread (freezes UI on large folders).
    - **Load (threaded)**: scans for `.tif` (depth-limited) and instantiates `KymImage(..., load_image=False)` in a worker thread.
    - **Cancel**: requests cancellation.

## Why "latest job wins" exists

Sometimes users click "Load" twice quickly. If you allow starting a second job, you have two problems:

1) You don't want the older job's results to overwrite the new selection.
2) You don't want the older job's progress messages to confuse the UI.

The runner solves this by giving each job a `job_id` and ignoring messages from stale jobs.

### But your preference: do NOT start a second job

The demo defaults to guarding starts:
- If a job is running, clicking "Load (threaded)" is refused with a warning.
- You can enable the checkbox "Allow restart while running" to test latest-job-wins behavior.

## Run

From the repo root (with your venv / uv env active):

```bash
uv run python sandbox/nicegui-threads/demo_acqimagelist_loader.py
```

The default path is:

`/Users/cudmore/Dropbox/data/declan/2026/compare-condiitons/v1-analysis`

Depth default is `3`.

## Expected behavior

- Blocking: UI freezes during load.
- Threaded: UI stays responsive; progress updates; cancel works.
