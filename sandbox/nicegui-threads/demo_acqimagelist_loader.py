# sandbox/nicegui-threads/demo_acqimagelist_loader.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

from nicegui import ui

from kymflow.core.image_loaders.acq_image_list import AcqImageList
from kymflow.core.image_loaders.kym_image import KymImage

from thread_job_runner import ThreadJobRunner


# ---- Demo configuration (your concrete guidance) ----
DEFAULT_PATH = Path("/Users/cudmore/Dropbox/data/declan/2026/compare-condiitons/v1-analysis")
DEFAULT_DEPTH = 3
FILE_EXT = ".tif"


@dataclass
class DemoState:
    loaded: List[KymImage]
    last_path: Path
    last_depth: int


state = DemoState(loaded=[], last_path=DEFAULT_PATH, last_depth=DEFAULT_DEPTH)

runner: ThreadJobRunner[List[KymImage]] = ThreadJobRunner()


def _scan_tifs_depth_limited(root: Path, *, depth: int) -> List[Path]:
    """
    Depth definition:
    - depth=0 means only files directly under root.
    - depth=1 includes one subfolder level, etc.

    We implement this by counting relative path parts excluding the filename:
        rel = file.relative_to(root)
        dir_depth = len(rel.parts) - 1
    """
    if root.is_file():
        return [root] if root.suffix.lower() == FILE_EXT else []

    out: List[Path] = []
    root = root.resolve()

    for p in root.rglob(f"*{FILE_EXT}"):
        try:
            rel = p.relative_to(root)
        except Exception:
            continue
        dir_depth = max(0, len(rel.parts) - 1)
        if dir_depth <= depth:
            out.append(p)

    out.sort()
    return out


def _disable_during_run(load_blocking_btn, load_threaded_btn, cancel_btn) -> None:
    running = runner.is_running()
    load_blocking_btn.enabled = not running
    load_threaded_btn.enabled = not running
    cancel_btn.enabled = running


@ui.page("/")
def main_page() -> None:
    ui.page_title("NiceGUI Threads Demo - AcqImageList / KymImage")

    with ui.column().classes("w-full max-w-4xl mx-auto gap-3"):
        ui.label("NiceGUI Threads Demo (native=True)").classes("text-xl font-semibold")
        ui.label("Goal: show UI freeze vs. background thread with progress + cancel.").classes("text-sm")

        with ui.card().classes("w-full"):
            ui.label("Inputs").classes("font-semibold")

            path_input = ui.input("Path", value=str(DEFAULT_PATH)).props("dense").classes("w-full")
            depth_input = ui.number("Depth", value=DEFAULT_DEPTH, min=0, step=1, format="%d").props("dense").classes("w-40")

            # You asked about not wanting 2nd job to win by default:
            # - default is "guarded": we refuse to start a new job if one is running.
            # - you can toggle this on to test 'latest job wins' gating if you want.
            allow_restart = ui.checkbox("Allow restart while running (enables latest-job-wins behavior)", value=False)

        with ui.card().classes("w-full"):
            ui.label("Progress").classes("font-semibold")
            status = ui.label("Idle.").classes("text-sm")
            progress = ui.linear_progress(value=0).classes("w-full")
            progress.props("instant-feedback")

            with ui.row().classes("gap-2"):
                load_blocking_btn = ui.button("Load (blocking)", color="negative")
                load_threaded_btn = ui.button("Load (threaded)", color="primary")
                cancel_btn = ui.button("Cancel", color="warning")
                cancel_btn.enabled = False

        with ui.card().classes("w-full"):
            ui.label("Results").classes("font-semibold")
            result_summary = ui.label("No results yet.").classes("text-sm")
            first_five = ui.markdown("").classes("text-sm")

        def _read_inputs() -> tuple[Path, int]:
            p = Path(path_input.value).expanduser()
            d = int(depth_input.value) if depth_input.value is not None else DEFAULT_DEPTH
            return p, d

        def _render_results(files: List[KymImage], root: Path, depth: int) -> None:
            state.loaded = files
            state.last_path = root
            state.last_depth = depth

            result_summary.text = f"Loaded {len(files)} KymImage items (load_image=False)."
            paths = []
            for i, img in enumerate(files[:5], start=1):
                # KymImage likely stores its path; we try common attrs
                p = getattr(img, "path", None) or getattr(img, "file_path", None) or getattr(img, "filepath", None)
                paths.append(f"{i}. {p}")
            if paths:
                first_five.content = "First 5:\n" + "\n".join(f"- {x}" for x in paths)
            else:
                first_five.content = ""

        def _load_blocking() -> None:
            root, depth = _read_inputs()

            status.text = "Blocking load started (UI will freeze if large)."
            progress.value = 0

            # This is your current blocking line:
            # (We use your imports + args; depth ignored for file mode, used for folder mode.)
            files = AcqImageList(
                path=root,
                image_cls=KymImage,
                file_extension=FILE_EXT,
                depth=depth if root.is_dir() else 0,
            )

            # Convert to a list[KymImage] for consistent result display
            out = list(files)

            status.text = f"Blocking load finished: {len(out)} items."
            progress.value = 1
            _render_results(out, root, depth)

        def _load_threaded() -> None:
            root, depth = _read_inputs()

            if runner.is_running() and not bool(allow_restart.value):
                ui.notify("Already running. Cancel first, or enable 'Allow restart while running'.", type="warning")
                return

            status.text = f"Threaded load started: scanning {root} (depth={depth})"
            progress.value = 0
            first_five.content = ""

            # If allow_restart is enabled, we allow a new start, and runner will:
            # - cancel the previous job (best-effort)
            # - gate messages so only the latest job updates UI ("latest job wins")
            cancel_previous = bool(allow_restart.value)

            def worker(cancel_event, emit) -> List[KymImage]:
                tif_paths = _scan_tifs_depth_limited(root, depth=depth)
                total = len(tif_paths)

                # Emit initial info so UI can show total quickly
                emit(0, total, detail="scan complete")

                out: List[KymImage] = []
                for i, tif_path in enumerate(tif_paths, start=1):
                    if cancel_event.is_set():
                        break

                    # Your instruction: instantiate with load_image=False
                    out.append(KymImage(tif_path, load_image=False))

                    # Throttle progress: update every 10 files
                    if (i % 10) == 0 or i == total:
                        emit(i, total, detail=str(tif_path))

                return out

            def on_progress(done: int, total: int, detail: str) -> None:
                progress.value = (done / total) if total else 0
                status.text = f"Threaded: {done}/{total}  {detail}"

            def on_done(result: List[KymImage]) -> None:
                progress.value = 1
                status.text = f"Threaded load finished: {len(result)} items."
                _render_results(result, root, depth)
                _disable_during_run(load_blocking_btn, load_threaded_btn, cancel_btn)

            def on_cancelled() -> None:
                status.text = "Cancelled. (Kept previous results.)"
                progress.value = 0
                _disable_during_run(load_blocking_btn, load_threaded_btn, cancel_btn)

            def on_error(exc: BaseException, tb: str) -> None:
                status.text = f"Error: {exc}"
                progress.value = 0
                ui.notify(f"Worker error: {exc}", type="negative")
                # You can print tb to console for debugging
                print(tb)
                _disable_during_run(load_blocking_btn, load_threaded_btn, cancel_btn)

            runner.start(
                ui_timer_factory=lambda dt, cb: ui.timer(dt, cb),
                poll_interval_s=0.05,
                worker_fn=worker,
                on_progress=on_progress,
                on_done=on_done,
                on_cancelled=on_cancelled,
                on_error=on_error,
                cancel_previous=cancel_previous,
            )

            _disable_during_run(load_blocking_btn, load_threaded_btn, cancel_btn)

        def _cancel() -> None:
            runner.cancel()
            _disable_during_run(load_blocking_btn, load_threaded_btn, cancel_btn)

        load_blocking_btn.on_click(_load_blocking)
        load_threaded_btn.on_click(_load_threaded)
        cancel_btn.on_click(_cancel)

        # Keep buttons in sync even if a job ends naturally between clicks
        ui.timer(0.2, lambda: _disable_during_run(load_blocking_btn, load_threaded_btn, cancel_btn))


if __name__ in {"__main__", "__mp_main__"}:
    # NOTE: native=True assumes you are running locally with NiceGUI native mode.
    ui.run(native=True, title="NiceGUI Threads Demo", reload=False)
