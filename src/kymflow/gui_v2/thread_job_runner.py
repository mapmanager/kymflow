"""NiceGUI-friendly background thread runner with progress and cancellation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, Optional, TypeVar, Union
import queue
import threading
import traceback

from kymflow.core.utils.progress import CancelledError as CoreCancelledError
from kymflow.core.utils.progress import ProgressCallback, ProgressMessage

TResult = TypeVar("TResult")


class ThreadJobCancelled(Exception):
    """Raised by worker code to signal a UI-level cancellation."""


@dataclass(frozen=True)
class ProgressMsg:
    job_id: int
    msg: ProgressMessage


@dataclass(frozen=True)
class DoneMsg(Generic[TResult]):
    job_id: int
    result: TResult


@dataclass(frozen=True)
class CancelledMsg:
    job_id: int


@dataclass(frozen=True)
class ErrorMsg:
    job_id: int
    exc: BaseException
    tb: str


WorkerMsg = Union[ProgressMsg, DoneMsg[TResult], CancelledMsg, ErrorMsg]

WorkerFn = Callable[[threading.Event, ProgressCallback], TResult]
OnProgress = Callable[[ProgressMessage], None]
OnDone = Callable[[TResult], None]
OnError = Callable[[BaseException, str], None]
OnCancelled = Callable[[], None]


class ThreadJobRunner(Generic[TResult]):
    """Run a background job while keeping NiceGUI UI updates on the main thread."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._next_job_id: int = 0
        self._active_job_id: int = 0

        self._cancel_event: Optional[threading.Event] = None
        self._thread: Optional[threading.Thread] = None
        self._q: "queue.Queue[WorkerMsg[TResult]]" = queue.Queue()

        self._on_progress: Optional[OnProgress] = None
        self._on_done: Optional[OnDone[TResult]] = None
        self._on_error: Optional[OnError] = None
        self._on_cancelled: Optional[OnCancelled] = None

        self._timer = None

    @property
    def active_job_id(self) -> int:
        with self._lock:
            return self._active_job_id

    def is_running(self) -> bool:
        t = self._thread
        return bool(t and t.is_alive())

    def cancel(self) -> None:
        with self._lock:
            ev = self._cancel_event
        if ev is not None:
            ev.set()

    def start(
        self,
        *,
        ui_timer_factory: Callable[[float, Callable[[], None]], object],
        poll_interval_s: float,
        worker_fn: WorkerFn[TResult],
        on_progress: Optional[OnProgress] = None,
        on_done: Optional[OnDone[TResult]] = None,
        on_error: Optional[OnError] = None,
        on_cancelled: Optional[OnCancelled] = None,
        cancel_previous: bool = False,
    ) -> int:
        """Start a job.

        If cancel_previous=True, any existing job gets a cancel request.
        Prefer guarding with is_running() when you want one job at a time.
        """
        with self._lock:
            self._next_job_id += 1
            job_id = self._next_job_id

            if cancel_previous and self._cancel_event is not None:
                self._cancel_event.set()

            self._active_job_id = job_id
            self._cancel_event = threading.Event()

            self._on_progress = on_progress
            self._on_done = on_done
            self._on_error = on_error
            self._on_cancelled = on_cancelled

        self._ensure_timer(ui_timer_factory, poll_interval_s)

        t = threading.Thread(
            target=self._worker_entry,
            name=f"ThreadJobRunner-{job_id}",
            daemon=True,
            args=(job_id, self._cancel_event, worker_fn),
        )
        self._thread = t
        t.start()
        return job_id

    def _ensure_timer(
        self,
        ui_timer_factory: Callable[[float, Callable[[], None]], object],
        poll_interval_s: float,
    ) -> None:
        if self._timer is not None:
            try:
                self._timer.cancel()
            except Exception:
                pass
            self._timer = None
        self._timer = ui_timer_factory(poll_interval_s, self._poll_queue_once)

    def _worker_entry(
        self,
        job_id: int,
        cancel_event: threading.Event,
        worker_fn: WorkerFn[TResult],
    ) -> None:
        try:
            def emit(msg: ProgressMessage) -> None:
                self._q.put(ProgressMsg(job_id=job_id, msg=msg))

            result = worker_fn(cancel_event, emit)

            if cancel_event.is_set():
                self._q.put(CancelledMsg(job_id=job_id))
                return

            self._q.put(DoneMsg[TResult](job_id=job_id, result=result))

        except (ThreadJobCancelled, CoreCancelledError):
            self._q.put(CancelledMsg(job_id=job_id))
        except BaseException as exc:
            tb = traceback.format_exc()
            self._q.put(ErrorMsg(job_id=job_id, exc=exc, tb=tb))

    def _poll_queue_once(self) -> None:
        max_per_tick = 200
        n = 0
        while n < max_per_tick:
            try:
                msg = self._q.get_nowait()
            except queue.Empty:
                break
            n += 1
            self._handle_msg(msg)

        if not self.is_running() and self._q.empty():
            self._stop_timer()

    def _handle_msg(self, msg: WorkerMsg[TResult]) -> None:
        with self._lock:
            latest_id = self._active_job_id
            on_progress = self._on_progress
            on_done = self._on_done
            on_error = self._on_error
            on_cancelled = self._on_cancelled

        if getattr(msg, "job_id", None) != latest_id:
            return

        if isinstance(msg, ProgressMsg):
            if on_progress:
                on_progress(msg.msg)
            return

        if isinstance(msg, DoneMsg):
            if on_done:
                on_done(msg.result)
            return

        if isinstance(msg, CancelledMsg):
            if on_cancelled:
                on_cancelled()
            return

        if isinstance(msg, ErrorMsg):
            if on_error:
                on_error(msg.exc, msg.tb)
            return

    def _stop_timer(self) -> None:
        if self._timer is not None:
            try:
                self._timer.cancel()
            except Exception:
                pass
            self._timer = None
