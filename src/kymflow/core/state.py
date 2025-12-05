"""Generic task state container with callback registries.

This module provides TaskState for tracking long-running tasks with progress.
TaskState is generic and can be used in scripts, notebooks, or GUI applications.
"""

from __future__ import annotations

from typing import Callable, List

from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)


# Type aliases for callbacks
TaskProgressHandler = Callable[[float], None]
TaskFinishedHandler = Callable[[], None]


class TaskState:
    """Container for tracking long-running tasks with progress.
    
    Generic progress tracking utility that can be used in scripts, notebooks,
    or GUI applications. Uses callback registries for progress updates and
    cancellation support.
    """
    
    def __init__(self):
        self.running: bool = False
        self.progress: float = 0.0
        self.message: str = ""
        self.cancellable: bool = False
        
        # Callback registries
        self._progress_changed_handlers: List[TaskProgressHandler] = []
        self._cancelled_handlers: List[TaskFinishedHandler] = []
        self._finished_handlers: List[TaskFinishedHandler] = []
        self._running_changed_handlers: List[Callable[[bool], None]] = []
    
    # Registration methods
    def on_progress_changed(self, handler: TaskProgressHandler) -> None:
        """Register callback for progress updates."""
        self._progress_changed_handlers.append(handler)
    
    def on_cancelled(self, handler: TaskFinishedHandler) -> None:
        """Register callback for cancellation."""
        self._cancelled_handlers.append(handler)
    
    def on_finished(self, handler: TaskFinishedHandler) -> None:
        """Register callback for completion."""
        self._finished_handlers.append(handler)
    
    def on_running_changed(self, handler: Callable[[bool], None]) -> None:
        """Register callback for running state changes."""
        self._running_changed_handlers.append(handler)
    
    # State mutation methods that trigger callbacks
    def set_progress(self, value: float, message: str = "") -> None:
        """Update task progress and call registered handlers."""
        self.progress = value
        self.message = message
        for handler in list(self._progress_changed_handlers):
            try:
                handler(value)
            except Exception:
                logger.exception("Error in progress_changed handler")
    
    def request_cancel(self) -> None:
        """Request cancellation of the current task."""
        if not self.running:
            return
        for handler in list(self._cancelled_handlers):
            try:
                handler()
            except Exception:
                logger.exception("Error in cancelled handler")
    
    def set_running(self, running: bool) -> None:
        """Set running state and notify handlers."""
        if self.running != running:
            self.running = running
            for handler in list(self._running_changed_handlers):
                try:
                    handler(running)
                except Exception:
                    logger.exception("Error in running_changed handler")
    
    def mark_finished(self) -> None:
        """Mark task as finished and notify handlers."""
        self.running = False
        self.cancellable = False
        for handler in list(self._finished_handlers):
            try:
                handler()
            except Exception:
                logger.exception("Error in finished handler")


