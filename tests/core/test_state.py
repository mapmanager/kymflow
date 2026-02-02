"""Tests for TaskState class."""

from __future__ import annotations

from kymflow.core.state import TaskState


def test_taskstate_initial_state() -> None:
    """Test TaskState initial state."""
    state = TaskState()
    assert state.running is False
    assert state.progress == 0.0
    assert state.message == ""
    assert state.cancellable is False


def test_taskstate_set_progress() -> None:
    """Test setting progress and message."""
    state = TaskState()
    progress_called = []
    
    def handler(value: float) -> None:
        progress_called.append(value)
    
    state.on_progress_changed(handler)
    state.set_progress(0.5, "Halfway done")
    
    assert state.progress == 0.5
    assert state.message == "Halfway done"
    assert progress_called == [0.5]


def test_taskstate_set_running() -> None:
    """Test setting running state."""
    state = TaskState()
    running_changes = []
    
    def handler(running: bool) -> None:
        running_changes.append(running)
    
    state.on_running_changed(handler)
    state.set_running(True)
    
    assert state.running is True
    assert running_changes == [True]
    
    state.set_running(False)
    assert state.running is False
    assert running_changes == [True, False]


def test_taskstate_request_cancel() -> None:
    """Test cancellation request."""
    state = TaskState()
    cancelled_called = []
    
    def handler() -> None:
        cancelled_called.append(True)
    
    state.on_cancelled(handler)
    
    # Should not call handler if not running
    state.request_cancel()
    assert len(cancelled_called) == 0
    
    # Should call handler if running
    state.set_running(True)
    state.request_cancel()
    assert len(cancelled_called) == 1


def test_taskstate_mark_finished() -> None:
    """Test marking task as finished."""
    state = TaskState()
    finished_called = []
    
    def handler() -> None:
        finished_called.append(True)
    
    state.on_finished(handler)
    state.set_running(True)
    state.cancellable = True
    state.mark_finished()
    
    assert state.running is False
    assert state.cancellable is False
    assert len(finished_called) == 1


def test_taskstate_multiple_handlers() -> None:
    """Test multiple handlers for same event."""
    state = TaskState()
    calls = []
    
    def handler1(value: float) -> None:
        calls.append(("handler1", value))
    
    def handler2(value: float) -> None:
        calls.append(("handler2", value))
    
    state.on_progress_changed(handler1)
    state.on_progress_changed(handler2)
    state.set_progress(0.75)
    
    assert len(calls) == 2
    assert ("handler1", 0.75) in calls
    assert ("handler2", 0.75) in calls


def test_taskstate_handler_exception_handling() -> None:
    """Test that handler exceptions don't break other handlers."""
    state = TaskState()
    good_calls = []
    
    def bad_handler(value: float) -> None:
        raise ValueError("Handler error")
    
    def good_handler(value: float) -> None:
        good_calls.append(value)
    
    state.on_progress_changed(bad_handler)
    state.on_progress_changed(good_handler)
    
    # Should not raise, and good handler should still be called
    state.set_progress(0.5)
    assert good_calls == [0.5]


def test_taskstate_running_changed_only_on_change() -> None:
    """Test that running_changed handler only called when value actually changes."""
    state = TaskState()
    changes = []
    
    def handler(running: bool) -> None:
        changes.append(running)
    
    state.on_running_changed(handler)
    
    # Set to True
    state.set_running(True)
    assert changes == [True]
    
    # Set to True again - should not trigger
    state.set_running(True)
    assert changes == [True]
    
    # Set to False
    state.set_running(False)
    assert changes == [True, False]
    
    # Set to False again - should not trigger
    state.set_running(False)
    assert changes == [True, False]
