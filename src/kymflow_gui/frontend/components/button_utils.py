"""
Reusable utilities for managing button states based on TaskState.

This module provides DRY functions for common button state management patterns
across the application, reducing code duplication.
"""

from __future__ import annotations

from typing import List, Optional

from nicegui import ui

from kymflow_core.state import TaskState


def sync_action_buttons(
    buttons: List[ui.button],
    task_state: TaskState,
    *,
    red_when_running: bool = True,
) -> None:
    """
    Disable/enable action buttons (start, analyze, etc.) based on task running state.
    
    Parameters
    ----------
    buttons:
        List of buttons to disable when task is running.
    task_state:
        TaskState instance to monitor.
    red_when_running:
        If True, set button color to red when running (disabled).
    """
    def _sync() -> None:
        running = task_state.running
        for button in buttons:
            button.disabled = running
            if red_when_running:
                if running:
                    button.props("color=red")
                else:
                    button.props(remove="color")
    
    # Set initial state
    _sync()
    
    # Connect to task state changes
    @task_state.events.running.connect  # type: ignore[attr-defined]
    def _on_running_changed() -> None:
        _sync()


def sync_cancel_button(
    cancel_button: ui.button,
    task_state: TaskState,
    *,
    red_when_running: bool = True,
) -> None:
    """
    Sync cancel button state and color based on task state.
    
    Cancel button is enabled only when task is running AND cancellable.
    Optionally sets button color to red when running.
    
    Parameters
    ----------
    cancel_button:
        The cancel button to manage.
    task_state:
        TaskState instance to monitor.
    red_when_running:
        If True, set button color to red when task is running.
    """
    def _sync() -> None:
        running = task_state.running
        cancellable = task_state.cancellable
        
        # Enable only when running and cancellable
        cancel_button.disabled = not (running and cancellable)
        
        # Set color to red when running
        if red_when_running:
            if running:
                cancel_button.props("color=red")
            else:
                cancel_button.props(remove="color")
    
    # Set initial state
    _sync()
    
    # Connect to task state changes
    @task_state.events.running.connect  # type: ignore[attr-defined]
    def _on_running_changed() -> None:
        _sync()
    
    # Also listen to cancellable changes (though it's usually set with running)
    # This ensures we catch any edge cases
    if hasattr(task_state, 'cancellable'):
        # Note: cancellable is not an evented field, so we rely on running changes
        # which typically happen together with cancellable changes
        pass


def connect_button_states(
    action_buttons: List[ui.button],
    cancel_button: Optional[ui.button],
    task_state: TaskState,
    *,
    red_cancel_when_running: bool = True,
) -> None:
    """
    Convenience function to connect both action and cancel buttons to task state.
    
    Parameters
    ----------
    action_buttons:
        List of action buttons (start, analyze, etc.) to disable when running.
    cancel_button:
        Optional cancel button to manage.
    task_state:
        TaskState instance to monitor.
    red_cancel_when_running:
        If True, set cancel button color to red when running.
    """
    sync_action_buttons(action_buttons, task_state)
    
    if cancel_button is not None:
        sync_cancel_button(cancel_button, task_state, red_when_running=red_cancel_when_running)
