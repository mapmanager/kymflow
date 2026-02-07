from __future__ import annotations

import time

from kymflow.core.utils.progress import ProgressMessage
from kymflow.gui_v2.thread_job_runner import ThreadJobRunner


class _DummyTimer:
    def __init__(self, cb) -> None:
        self._cb = cb
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def tick(self) -> None:
        if not self._cancelled:
            self._cb()


def _drain_runner(runner: ThreadJobRunner, timer: _DummyTimer, timeout_s: float = 2.0) -> None:
    start = time.time()
    while True:
        timer.tick()
        if not runner.is_running() and runner._q.empty():
            break
        if time.time() - start > timeout_s:
            break
        time.sleep(0.01)


def test_thread_job_runner_progress_and_done() -> None:
    runner: ThreadJobRunner[int] = ThreadJobRunner()
    progress_msgs: list[ProgressMessage] = []
    done_values: list[int] = []

    def worker_fn(cancel_event, progress_cb):
        progress_cb(ProgressMessage(phase="wrap", done=1, total=2))
        return 42

    timer = None

    def ui_timer_factory(_, cb):
        nonlocal timer
        timer = _DummyTimer(cb)
        return timer

    runner.start(
        ui_timer_factory=ui_timer_factory,
        poll_interval_s=0.01,
        worker_fn=worker_fn,
        on_progress=lambda msg: progress_msgs.append(msg),
        on_done=lambda result: done_values.append(result),
    )

    assert timer is not None
    _drain_runner(runner, timer)

    assert done_values == [42]
    assert len(progress_msgs) == 1
    assert progress_msgs[0].phase == "wrap"


def test_thread_job_runner_cancelled() -> None:
    runner: ThreadJobRunner[int] = ThreadJobRunner()
    cancelled = False

    def on_cancelled() -> None:
        nonlocal cancelled
        cancelled = True

    def worker_fn(cancel_event, progress_cb):
        while not cancel_event.is_set():
            progress_cb(ProgressMessage(phase="wrap", done=0, total=1))
            time.sleep(0.01)
        return 0

    timer = None

    def ui_timer_factory(_, cb):
        nonlocal timer
        timer = _DummyTimer(cb)
        return timer

    runner.start(
        ui_timer_factory=ui_timer_factory,
        poll_interval_s=0.01,
        worker_fn=worker_fn,
        on_cancelled=on_cancelled,
    )

    assert timer is not None
    runner.cancel()
    _drain_runner(runner, timer)

    assert cancelled is True


def test_thread_job_runner_error() -> None:
    runner: ThreadJobRunner[int] = ThreadJobRunner()
    errors: list[BaseException] = []

    def worker_fn(cancel_event, progress_cb):
        raise ValueError("boom")

    timer = None

    def ui_timer_factory(_, cb):
        nonlocal timer
        timer = _DummyTimer(cb)
        return timer

    runner.start(
        ui_timer_factory=ui_timer_factory,
        poll_interval_s=0.01,
        worker_fn=worker_fn,
        on_error=lambda exc, tb: errors.append(exc),
    )

    assert timer is not None
    _drain_runner(runner, timer)

    assert len(errors) == 1
    assert isinstance(errors[0], ValueError)
