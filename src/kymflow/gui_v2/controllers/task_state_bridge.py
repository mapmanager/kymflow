"""Bridge TaskState callbacks to event bus events.

This module provides a controller that bridges TaskState callback registries
to the v2 EventBus, converting TaskState changes into TaskStateChanged events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from kymflow.core.state import TaskState
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.events_state import TaskStateChanged

if TYPE_CHECKING:
    pass


class TaskStateBridgeController:
    """Bridge TaskState callbacks into the v2 EventBus.

    This controller subscribes to TaskState callback registries and emits
    corresponding TaskStateChanged events on the EventBus. It checks client
    validity before emitting to prevent errors from stale callbacks.

    Flow:
        TaskState.set_progress() → callback → emit TaskStateChanged
        TaskState.set_running() → callback → emit TaskStateChanged
        TaskState.mark_finished() → callback → emit TaskStateChanged

    Attributes:
        _task_state: TaskState instance to monitor.
        _bus: EventBus instance (per-client).
        _task_type: Type identifier for this task state.
    """

    def __init__(
        self, task_state: TaskState, bus: EventBus, task_type: Literal["home", "batch", "batch_overall"]
    ) -> None:
        """Initialize the task state bridge controller.

        Subscribes to TaskState callbacks. The callbacks remain registered
        for the lifetime of the TaskState instance, but they check client
        validity before emitting events.

        Args:
            task_state: TaskState instance to monitor.
            bus: Per-client EventBus instance.
            task_type: Type identifier for this task ("home", "batch", or "batch_overall").
        """
        self._task_state: TaskState = task_state
        self._bus: EventBus = bus
        self._task_type: Literal["home", "batch", "batch_overall"] = task_type

        # Register callbacks that will emit bus events
        self._task_state.on_progress_changed(self._on_progress_changed)
        self._task_state.on_running_changed(self._on_running_changed)
        self._task_state.on_finished(self._on_finished)

        # Emit initial state
        self._emit_task_state()

    def _on_progress_changed(self, _value: float) -> None:
        """Handle TaskState progress change callback.

        Emits TaskStateChanged event with current state. Checks client validity
        before emitting.

        Args:
            _value: New progress value (0.0 to 1.0). Unused, we read from task_state.
        """
        if not self._is_client_alive():
            return
        self._emit_task_state()

    def _on_running_changed(self, _running: bool) -> None:
        """Handle TaskState running state change callback.

        Emits TaskStateChanged event with current state. Checks client validity
        before emitting.

        Args:
            _running: New running state. Unused, we read from task_state.
        """
        if not self._is_client_alive():
            return
        self._emit_task_state()

    def _on_finished(self) -> None:
        """Handle TaskState finished callback.

        Emits TaskStateChanged event with current state (running=False).
        Checks client validity before emitting.
        """
        if not self._is_client_alive():
            return
        self._emit_task_state()

    def _emit_task_state(self) -> None:
        """Emit TaskStateChanged event with current TaskState values.

        Only emits if client is still alive to prevent errors from stale callbacks.
        """
        if not self._is_client_alive():
            return

        from kymflow.core.utils.logging import get_logger
        logger = get_logger(__name__)
        
        # logger.debug(
        #     f"Emitting TaskStateChanged: running={self._task_state.running}, "
        #     f"cancellable={self._task_state.cancellable}, progress={self._task_state.progress}, "
        #     f"message={self._task_state.message}, task_type={self._task_type}"
        # )

        self._bus.emit(
            TaskStateChanged(
                running=self._task_state.running,
                progress=self._task_state.progress,
                message=self._task_state.message,
                cancellable=self._task_state.cancellable,
                task_type=self._task_type,
                phase="state",
            )
        )

    def _is_client_alive(self) -> bool:
        """Check if the client is still alive.

        Uses EventBus client validity check to prevent errors from stale callbacks.

        Returns:
            True if client is alive, False otherwise.
        """
        from kymflow.gui_v2.client_utils import is_client_alive

        return is_client_alive()
