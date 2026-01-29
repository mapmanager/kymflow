"""Tests for views disabling controls during tasks (Tier 2)."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import tifffile

from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.events_state import TaskStateChanged
from kymflow.gui_v2.views.analysis_toolbar_view import AnalysisToolbarView
from kymflow.gui_v2.views.file_table_view import FileTableView
from kymflow.gui_v2.views.folder_selector_view import FolderSelectorView
from kymflow.gui_v2.views.metadata_experimental_view import MetadataExperimentalView
from kymflow.gui_v2.views.metadata_header_view import MetadataHeaderView
from kymflow.gui_v2.views.save_buttons_view import SaveButtonsView


@pytest.fixture
def sample_kym_file() -> KymImage:
    """Create a sample KymImage for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.tif"
        test_image = np.zeros((100, 200), dtype=np.uint16)
        tifffile.imwrite(test_file, test_image)

        kym_file = KymImage(test_file, load_image=True)
        return kym_file


def test_analysis_toolbar_stores_task_state(
    sample_kym_file: KymImage,
) -> None:
    """Test that AnalysisToolbarView stores task state and calls update method."""
    view = AnalysisToolbarView(
        on_analysis_start=lambda e: None,
        on_analysis_cancel=lambda e: None,
        on_add_roi=lambda e: None,
        on_delete_roi=lambda e: None,
        on_set_roi_edit_state=lambda e: None,
        on_roi_selected=lambda e: None,
    )

    # Mock the update method
    with patch.object(view, "_update_button_states") as mock_update:
        # Set task state to running
        task_state = TaskStateChanged(
            task_type="home", running=True, cancellable=True, progress=0.5, message="Running"
        )
        view.set_task_state(task_state)

        # Verify task state is stored
        assert view._task_state == task_state
        assert view._task_state.running is True

        # Verify update method was called
        mock_update.assert_called()

        # Set task state to not running
        task_state_not_running = TaskStateChanged(
            task_type="home", running=False, cancellable=False, progress=1.0, message="Done"
        )
        view.set_task_state(task_state_not_running)

        # Verify task state is updated
        assert view._task_state == task_state_not_running
        assert view._task_state.running is False


def test_save_buttons_stores_task_state(sample_kym_file: KymImage) -> None:
    """Test that SaveButtonsView stores task state and calls update method."""
    view = SaveButtonsView(
        on_save_selected=lambda e: None,
        on_save_all=lambda e: None,
    )

    # Mock the update method
    with patch.object(view, "_update_button_states") as mock_update:
        # Set task state to running
        task_state = TaskStateChanged(
            task_type="home", running=True, cancellable=True, progress=0.5, message="Running"
        )
        view.set_task_state(task_state)

        # Verify task state is stored
        assert view._task_state == task_state
        assert view._task_state.running is True

        # Verify update method was called
        mock_update.assert_called()

        # Set task state to not running
        task_state_not_running = TaskStateChanged(
            task_type="home", running=False, cancellable=False, progress=1.0, message="Done"
        )
        view.set_task_state(task_state_not_running)

        # Verify task state is updated
        assert view._task_state == task_state_not_running
        assert view._task_state.running is False


def test_file_table_stores_task_state(sample_kym_file: KymImage) -> None:
    """Test that FileTableView stores task state and calls update method."""
    view = FileTableView(on_selected=lambda e: None)

    # Mock the update method
    with patch.object(view, "_update_interaction_state") as mock_update:
        # Set task state to running
        task_state = TaskStateChanged(
            task_type="home", running=True, cancellable=True, progress=0.5, message="Running"
        )
        view.set_task_state(task_state)

        # Verify task state is stored
        assert view._task_state == task_state
        assert view._task_state.running is True

        # Verify update method was called
        mock_update.assert_called()

        # Set task state to not running
        task_state_not_running = TaskStateChanged(
            task_type="home", running=False, cancellable=False, progress=1.0, message="Done"
        )
        view.set_task_state(task_state_not_running)

        # Verify task state is updated
        assert view._task_state == task_state_not_running
        assert view._task_state.running is False


def test_metadata_header_stores_task_state(sample_kym_file: KymImage) -> None:
    """Test that MetadataHeaderView stores task state and calls update method."""
    view = MetadataHeaderView(on_metadata_update=lambda e: None)

    # Mock the update method
    with patch.object(view, "_update_widget_states") as mock_update:
        # Set task state to running
        task_state = TaskStateChanged(
            task_type="home", running=True, cancellable=True, progress=0.5, message="Running"
        )
        view.set_task_state(task_state)

        # Verify task state is stored
        assert view._task_state == task_state
        assert view._task_state.running is True

        # Verify update method was called
        mock_update.assert_called()

        # Set task state to not running
        task_state_not_running = TaskStateChanged(
            task_type="home", running=False, cancellable=False, progress=1.0, message="Done"
        )
        view.set_task_state(task_state_not_running)

        # Verify task state is updated
        assert view._task_state == task_state_not_running
        assert view._task_state.running is False


def test_metadata_experimental_stores_task_state(sample_kym_file: KymImage) -> None:
    """Test that MetadataExperimentalView stores task state and calls update method."""
    view = MetadataExperimentalView(on_metadata_update=lambda e: None)

    # Mock the update method
    with patch.object(view, "_update_widget_states") as mock_update:
        # Set task state to running
        task_state = TaskStateChanged(
            task_type="home", running=True, cancellable=True, progress=0.5, message="Running"
        )
        view.set_task_state(task_state)

        # Verify task state is stored
        assert view._task_state == task_state
        assert view._task_state.running is True

        # Verify update method was called
        mock_update.assert_called()

        # Set task state to not running
        task_state_not_running = TaskStateChanged(
            task_type="home", running=False, cancellable=False, progress=1.0, message="Done"
        )
        view.set_task_state(task_state_not_running)

        # Verify task state is updated
        assert view._task_state == task_state_not_running
        assert view._task_state.running is False


def test_folder_selector_stores_task_state(bus: EventBus) -> None:
    """Test that FolderSelectorView stores task state and calls update method."""
    from kymflow.gui_v2.state import AppState

    app_state = AppState()
    view = FolderSelectorView(bus=bus, app_state=app_state, user_config=None)

    # Mock the update method
    with patch.object(view, "_update_controls_state") as mock_update:
        # Set task state to running
        task_state = TaskStateChanged(
            task_type="home", running=True, cancellable=True, progress=0.5, message="Running"
        )
        view.set_task_state(task_state)

        # Verify task state is stored
        assert view._task_state == task_state
        assert view._task_state.running is True

        # Verify update method was called
        mock_update.assert_called()

        # Set task state to not running
        task_state_not_running = TaskStateChanged(
            task_type="home", running=False, cancellable=False, progress=1.0, message="Done"
        )
        view.set_task_state(task_state_not_running)

        # Verify task state is updated
        assert view._task_state == task_state_not_running
        assert view._task_state.running is False
