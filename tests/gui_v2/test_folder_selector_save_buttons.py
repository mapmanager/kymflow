"""Tests for FolderSelectorView save buttons functionality."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import tifffile

from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.events import FileSelection, SaveAll, SaveSelected, SelectionOrigin
from kymflow.gui_v2.events_state import TaskStateChanged
from kymflow.gui_v2.state import AppState
from kymflow.gui_v2.views.folder_selector_view import FolderSelectorView


@pytest.fixture
def sample_kym_file() -> KymImage:
    """Create a sample KymImage for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.tif"
        test_image = np.zeros((100, 200), dtype=np.uint16)
        tifffile.imwrite(test_file, test_image)

        kym_file = KymImage(test_file, load_image=True)
        return kym_file


def test_folder_selector_save_buttons_emit_save_selected(bus: EventBus) -> None:
    """Test that FolderSelectorView save buttons emit SaveSelected event when clicked."""
    app_state = AppState()
    emitted_events = []

    def capture_save_selected(event: SaveSelected) -> None:
        emitted_events.append(event)

    view = FolderSelectorView(
        bus=bus,
        app_state=app_state,
        user_config=None,
        on_save_selected=capture_save_selected,
        on_save_all=lambda e: None,
    )

    # Call the save selected click handler
    view._on_save_selected_click()

    # Verify SaveSelected event was emitted with correct phase
    assert len(emitted_events) == 1
    assert isinstance(emitted_events[0], SaveSelected)
    assert emitted_events[0].phase == "intent"


def test_folder_selector_save_buttons_emit_save_all(bus: EventBus) -> None:
    """Test that FolderSelectorView save buttons emit SaveAll event when clicked."""
    app_state = AppState()
    emitted_events = []

    def capture_save_all(event: SaveAll) -> None:
        emitted_events.append(event)

    view = FolderSelectorView(
        bus=bus,
        app_state=app_state,
        user_config=None,
        on_save_selected=lambda e: None,
        on_save_all=capture_save_all,
    )

    # Call the save all click handler
    view._on_save_all_click()

    # Verify SaveAll event was emitted with correct phase
    assert len(emitted_events) == 1
    assert isinstance(emitted_events[0], SaveAll)
    assert emitted_events[0].phase == "intent"


def test_folder_selector_save_buttons_no_callbacks(bus: EventBus) -> None:
    """Test that FolderSelectorView save buttons handle None callbacks gracefully."""
    app_state = AppState()

    view = FolderSelectorView(
        bus=bus,
        app_state=app_state,
        user_config=None,
        on_save_selected=None,
        on_save_all=None,
    )

    # Should not raise when callbacks are None
    view._on_save_selected_click()
    view._on_save_all_click()


def test_folder_selector_save_buttons_update_on_file_selection(
    bus: EventBus, sample_kym_file: KymImage
) -> None:
    """Test that FolderSelectorView save buttons update state on FileSelection events."""
    app_state = AppState()
    view = FolderSelectorView(
        bus=bus,
        app_state=app_state,
        user_config=None,
        on_save_selected=lambda e: None,
        on_save_all=lambda e: None,
    )

    # Render to create buttons
    view.render()

    # Mock the update method to verify it's called
    with patch.object(view, "_update_save_button_states") as mock_update:
        # Emit FileSelection event
        file_selection = FileSelection(
            path=None,  # Can be None for state phase (derived from file.path)
            file=sample_kym_file,
            origin=SelectionOrigin.EXTERNAL,
            phase="state",
        )
        view._on_file_selection_changed(file_selection)

        # Verify file was stored and update was called
        assert view._current_file == sample_kym_file
        mock_update.assert_called_once()


def test_folder_selector_save_buttons_update_on_task_state(bus: EventBus) -> None:
    """Test that FolderSelectorView save buttons update state on TaskStateChanged events."""
    app_state = AppState()
    view = FolderSelectorView(
        bus=bus,
        app_state=app_state,
        user_config=None,
        on_save_selected=lambda e: None,
        on_save_all=lambda e: None,
    )

    # Render to create buttons
    view.render()

    # Mock the update method to verify it's called
    with patch.object(view, "_update_save_button_states") as mock_update:
        # Emit TaskStateChanged event with "home" task type
        task_state = TaskStateChanged(
            task_type="home",
            running=True,
            cancellable=True,
            progress=0.5,
            message="Running",
        )
        view._on_task_state_changed(task_state)

        # Verify task state was stored and update was called
        assert view._task_state == task_state
        mock_update.assert_called_once()


def test_folder_selector_save_buttons_filter_task_type(bus: EventBus) -> None:
    """Test that FolderSelectorView save buttons only respond to "home" task type."""
    app_state = AppState()
    view = FolderSelectorView(
        bus=bus,
        app_state=app_state,
        user_config=None,
        on_save_selected=lambda e: None,
        on_save_all=lambda e: None,
    )

    # Render to create buttons
    view.render()

    # Mock the update method
    with patch.object(view, "_update_save_button_states") as mock_update:
        # Emit TaskStateChanged event with different task type
        task_state_other = TaskStateChanged(
            task_type="other",
            running=True,
            cancellable=True,
            progress=0.5,
            message="Running",
        )
        view._on_task_state_changed(task_state_other)

        # Verify update was NOT called (filtered out)
        mock_update.assert_not_called()

        # Emit TaskStateChanged event with "home" task type
        task_state_home = TaskStateChanged(
            task_type="home",
            running=True,
            cancellable=True,
            progress=0.5,
            message="Running",
        )
        view._on_task_state_changed(task_state_home)

        # Verify update WAS called for "home" task
        mock_update.assert_called_once()


def test_folder_selector_save_buttons_state_logic(
    bus: EventBus, sample_kym_file: KymImage
) -> None:
    """Test that FolderSelectorView save buttons have correct enable/disable logic."""
    app_state = AppState()
    view = FolderSelectorView(
        bus=bus,
        app_state=app_state,
        user_config=None,
        on_save_selected=lambda e: None,
        on_save_all=lambda e: None,
    )

    # Render to create buttons
    view.render()

    # Mock button methods
    view._save_selected_button = MagicMock()
    view._save_all_button = MagicMock()

    # Test: No file selected, task not running
    view._current_file = None
    view._task_state = TaskStateChanged(
        task_type="home", running=False, cancellable=False, progress=1.0, message="Done"
    )
    view._update_save_button_states()

    # Save Selected should be disabled (no file)
    view._save_selected_button.disable.assert_called()
    # Save All should be enabled
    view._save_all_button.enable.assert_called()

    # Reset mocks
    view._save_selected_button.reset_mock()
    view._save_all_button.reset_mock()

    # Test: File selected, task not running
    view._current_file = sample_kym_file
    view._task_state = TaskStateChanged(
        task_type="home", running=False, cancellable=False, progress=1.0, message="Done"
    )
    view._update_save_button_states()

    # Save Selected should be enabled (file selected)
    view._save_selected_button.enable.assert_called()
    # Save All should be enabled
    view._save_all_button.enable.assert_called()

    # Reset mocks
    view._save_selected_button.reset_mock()
    view._save_all_button.reset_mock()

    # Test: Task running (regardless of file selection)
    view._current_file = sample_kym_file
    view._task_state = TaskStateChanged(
        task_type="home", running=True, cancellable=True, progress=0.5, message="Running"
    )
    view._update_save_button_states()

    # Both buttons should be disabled when task is running
    view._save_selected_button.disable.assert_called()
    view._save_all_button.disable.assert_called()


def test_folder_selector_save_buttons_subscribe_to_events(bus: EventBus) -> None:
    """Test that FolderSelectorView subscribes to FileSelection and TaskStateChanged for save buttons."""
    app_state = AppState()
    view = FolderSelectorView(
        bus=bus,
        app_state=app_state,
        user_config=None,
        on_save_selected=lambda e: None,
        on_save_all=lambda e: None,
    )

    # Verify subscriptions were made (check that handlers exist)
    # The view subscribes in __init__ if callbacks are provided
    assert hasattr(view, "_on_file_selection_changed")
    assert hasattr(view, "_on_task_state_changed")

    # Test that handlers are callable
    assert callable(view._on_file_selection_changed)
    assert callable(view._on_task_state_changed)
