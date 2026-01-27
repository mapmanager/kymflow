# minimal_mp_flow_app.py
"""
Minimal NiceGUI app that runs mp_analyze_flow() using multiprocessing
and reports progress back to the UI via queue.Queue.

How to run:
  1) Put this file next to kym_flow_radon.py (same directory)
  2) pip install nicegui numpy
  3) python minimal_mp_flow_app.py
"""

from __future__ import annotations

import multiprocessing as mp
import queue
import threading
import traceback
from dataclasses import dataclass
from typing import Any, Optional, Tuple

import numpy as np
from nicegui import ui

# --- Import mp_analyze_flow from your provided module -------------------------
try:
    # expects kym_flow_radon.py to be in the same directory
    from kym_flow_radon import mp_analyze_flow, FlowCancelled  # type: ignore
except Exception as e:
    raise RuntimeError(
        "Failed to import mp_analyze_flow from kym_flow_radon.py.\n"
        "Make sure minimal_mp_flow_app.py and kym_flow_radon.py are in the same folder.\n"
        f"Import error: {e}"
    )


# --- Simple task state container (no NiceGUI objects here) -------------------
@dataclass
class TaskState:
    running: bool = False
    cancelled: bool = False
    completed: int = 0
    total: int = 1
    last_status: str = "Idle"


def make_synthetic_data(n_time: int = 10_000, n_space: int = 25) -> np.ndarray:
    """
    Create synthetic (time x space) kymograph-like data.
    - Add a moving sinusoid + noise so radon has something to latch onto.
    """
    t = np.linspace(0, 20 * np.pi, n_time, dtype=np.float32)
    x = np.linspace(0, 2 * np.pi, n_space, dtype=np.float32)
    tt, xx = np.meshgrid(t, x, indexing="ij")  # (n_time, n_space)

    # Moving wave + noise
    data = np.sin(tt + 2.0 * xx) + 0.25 * np.random.randn(n_time, n_space).astype(np.float32)

    # Make it non-negative-ish (some implementations prefer)
    data = data - data.min()
    return data.astype(np.float32)


def main() -> None:
    # ------------------ UI + shared objects ------------------
    state = TaskState()
    progress_q: "queue.Queue[Tuple[Any, ...]]" = queue.Queue()
    cancel_event = threading.Event()
    worker_thread: Optional[threading.Thread] = None

    # Synthetic data (fixed for this minimal repro)
    data = make_synthetic_data(10_000, 25)

    # Parameters (kept simple; adjust as needed)
    windowsize = 200
    dim0_start, dim0_stop = 0, data.shape[0]
    dim1_start, dim1_stop = 0, data.shape[1]

    # ------------------ UI elements ------------------
    ui.label("Minimal multiprocessing flow analysis (mp_analyze_flow)").classes("text-h6")
    ui.label("This app uses queue.Queue + ui.timer to update progress safely.").classes("text-body2")

    progress_bar = ui.linear_progress(value=0.0).props("instant-feedback").classes("w-full")
    progress_label = ui.label("Idle")
    status_label = ui.label("")

    with ui.row().classes("items-center gap-2"):
        run_btn = ui.button("Run mp flow", color="primary")
        cancel_btn = ui.button("Cancel", color="negative")
        cancel_btn.disable()

    with ui.card().classes("w-full"):
        ui.label("Debug").classes("text-subtitle2")
        debug = ui.textarea(value="", placeholder="Logs...").props("readonly").classes("w-full h-48")

    def log(msg: str) -> None:
        # UI-safe; called only from main loop (timer/click handlers)
        debug.value = (debug.value + msg + "\n")[-20_000:]

    # ------------------ Background worker ------------------
    def worker() -> None:
        """
        Background thread: calls mp_analyze_flow().
        IMPORTANT: does NOT touch NiceGUI UI objects directly.
        It only pushes messages onto progress_q.
        """
        try:
            # Reset cancel flag for this run
            cancel_event.clear()

            # Run multiprocessing analysis.
            # Your mp_analyze_flow emits ("progress", completed, total) to progress_queue.
            result = mp_analyze_flow(
                data=data,
                windowsize=windowsize,
                dim0_start=dim0_start,
                dim0_stop=dim0_stop,
                dim1_start=dim1_start,
                dim1_stop=dim1_stop,
                verbose=False,
                progress_queue=progress_q,          # <-- core sends ("progress", c, n)
                progress_every=1,                  # emit every completed step
                is_cancelled=cancel_event.is_set,  # <-- core will terminate() pool if True
                use_multiprocessing=True,
                processes=None,                    # let core choose default
            )
            progress_q.put(("done", result))
        except FlowCancelled:
            progress_q.put(("cancelled", None))
        except Exception as e:
            progress_q.put(("error", repr(e), traceback.format_exc()))

    # ------------------ UI actions ------------------
    def start_run() -> None:
        nonlocal worker_thread

        if state.running:
            ui.notify("Already running", type="warning")
            return

        # Reset state
        state.running = True
        state.cancelled = False
        state.completed = 0
        state.total = 1
        state.last_status = "Starting..."

        # Clear any stale messages
        while True:
            try:
                progress_q.get_nowait()
            except Exception:
                break

        # UI updates
        run_btn.disable()
        cancel_btn.enable()
        progress_bar.value = 0.0
        progress_label.text = "Starting..."
        status_label.text = f"data={data.shape}, windowsize={windowsize}"
        log("Starting worker thread...")

        # Start background thread (NON-daemon)
        worker_thread = threading.Thread(target=worker, daemon=False)
        worker_thread.start()

    def cancel_run() -> None:
        if not state.running:
            return
        log("Cancel requested (setting cancel_event)...")
        state.cancelled = True
        cancel_event.set()
        cancel_btn.disable()  # immediate UX feedback

    run_btn.on("click", lambda e: start_run())
    cancel_btn.on("click", lambda e: cancel_run())

    # ------------------ Main-loop polling ------------------
    def drain_queue() -> None:
        """
        Runs on NiceGUI main event loop via ui.timer.
        Drains progress_q and updates UI safely.
        """
        if not state.running:
            return

        any_msg = False
        while True:
            try:
                msg = progress_q.get_nowait()
            except Exception:
                break

            any_msg = True
            tag = msg[0]

            if tag == "progress":
                # From your mp_analyze_flow: ("progress", completed, total)
                _, completed, total = msg
                state.completed = int(completed)
                state.total = max(1, int(total))
                progress_bar.value = state.completed / state.total
                progress_label.text = f"{state.completed} / {state.total}"
            elif tag == "done":
                _, result = msg
                state.running = False
                run_btn.enable()
                cancel_btn.disable()
                progress_bar.value = 1.0
                progress_label.text = "Done"
                log("DONE. Result type: " + str(type(result)))
                ui.notify("Flow analysis complete", type="positive")
            elif tag == "cancelled":
                state.running = False
                run_btn.enable()
                cancel_btn.disable()
                progress_bar.value = 0.0
                progress_label.text = "Cancelled"
                log("CANCELLED (core terminated pool and raised FlowCancelled).")
                ui.notify("Cancelled", type="warning")
            elif tag == "error":
                state.running = False
                run_btn.enable()
                cancel_btn.disable()
                progress_label.text = "Error"
                _, err, tb = msg
                log("ERROR: " + str(err))
                log(tb)
                ui.notify("Flow analysis error (see debug log)", type="negative")
            else:
                log(f"Unknown message: {msg!r}")

        # Optional: if nothing is coming back for a while, you can add a heartbeat here
        if any_msg:
            state.last_status = "Running"

    ui.timer(0.1, drain_queue)

    ui.run(title="Minimal mp_analyze_flow NiceGUI repro", reload=False)


if __name__ == "__main__":
    # Required on Windows; also harmless elsewhere.
    mp.freeze_support()

    # IMPORTANT: Keep guard to avoid multiprocessing re-import issues.
    main()