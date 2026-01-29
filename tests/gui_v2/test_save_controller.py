"""Tests for SaveController - metadata-only saves and dirty state checks."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
import tifffile

from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.core.image_loaders.acq_image_list import AcqImageList
from kymflow.core.state import TaskState
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.controllers.save_controller import SaveController
from kymflow.gui_v2.events import SaveAll, SaveSelected
from kymflow.gui_v2.state import AppState


@pytest.fixture
def app_state_with_file() -> tuple[AppState, KymImage]:
    """Create an AppState with a test file loaded."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.tif"
        test_image = np.zeros((100, 200), dtype=np.uint16)
        tifffile.imwrite(test_file, test_image)

        kym_file = KymImage(test_file, load_image=True)

        app_state = AppState()
        image_list = AcqImageList(path=None, image_cls=KymImage, file_extension=".tif", depth=1)
        image_list.images = [kym_file]
        app_state.files = image_list
        app_state.selected_file = kym_file

        return app_state, kym_file


def test_save_selected_metadata_only_dirty(
    bus: EventBus, app_state_with_file: tuple[AppState, KymImage]
) -> None:
    """Test that SaveController saves files with metadata-only dirty state."""
    app_state, kym_file = app_state_with_file
    task_state = TaskState()
    SaveController(app_state, task_state, bus)  # Subscribes to events

    # Update metadata only (no analysis)
    kym_file.update_experiment_metadata(species="mouse", region="cortex")
    assert kym_file.is_metadata_dirty is True
    assert kym_file.get_kym_analysis().is_dirty is True

    # Mock save_analysis to verify it's called
    with patch.object(kym_file.get_kym_analysis(), "save_analysis") as mock_save:
        mock_save.return_value = True

        # Emit save selected intent
        bus.emit(SaveSelected(phase="intent"))

        # Verify save_analysis was called (even without analysis data)
        mock_save.assert_called_once()


def test_save_selected_uses_is_dirty_not_has_analysis(
    bus: EventBus, app_state_with_file: tuple[AppState, KymImage]
) -> None:
    """Test that SaveController uses is_dirty property (not has_analysis gate)."""
    app_state, kym_file = app_state_with_file
    task_state = TaskState()
    SaveController(app_state, task_state, bus)  # Subscribes to events

    # Update metadata only (no analysis data)
    kym_file.update_experiment_metadata(note="test note")
    assert kym_file.get_kym_analysis().is_dirty is True
    assert not kym_file.get_kym_analysis().has_analysis()

    # Mock save_analysis
    with patch.object(kym_file.get_kym_analysis(), "save_analysis") as mock_save:
        mock_save.return_value = True

        # Emit save selected intent
        bus.emit(SaveSelected(phase="intent"))

        # Should call save_analysis even though has_analysis() is False
        mock_save.assert_called_once()


def test_save_all_metadata_only_dirty(
    bus: EventBus, app_state_with_file: tuple[AppState, KymImage]
) -> None:
    """Test that SaveController saves all files with metadata-only dirty state."""
    app_state, kym_file = app_state_with_file

    # Create second file with metadata dirty
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file2 = Path(tmpdir) / "test2.tif"
        test_image2 = np.zeros((80, 150), dtype=np.uint16)
        tifffile.imwrite(test_file2, test_image2)
        kym_file2 = KymImage(test_file2, load_image=True)

        # Add both files to app_state
        image_list = AcqImageList(path=None, image_cls=KymImage, file_extension=".tif", depth=1)
        image_list.images = [kym_file, kym_file2]
        app_state.files = image_list

        # Update metadata for both files (no analysis)
        kym_file.update_experiment_metadata(species="mouse")
        kym_file2.update_experiment_metadata(region="cortex")

        task_state = TaskState()
        SaveController(app_state, task_state, bus)  # Subscribes to events

        # Mock save_analysis for both files
        with patch.object(kym_file.get_kym_analysis(), "save_analysis") as mock_save1:
            with patch.object(kym_file2.get_kym_analysis(), "save_analysis") as mock_save2:
                mock_save1.return_value = True
                mock_save2.return_value = True

                # Emit save all intent
                bus.emit(SaveAll(phase="intent"))

                # Both should be saved (even without analysis data)
                mock_save1.assert_called_once()
                mock_save2.assert_called_once()


def test_save_selected_skips_when_not_dirty(
    bus: EventBus, app_state_with_file: tuple[AppState, KymImage]
) -> None:
    """Test that SaveController skips save when file is not dirty."""
    app_state, kym_file = app_state_with_file
    task_state = TaskState()
    SaveController(app_state, task_state, bus)  # Subscribes to events

    # File is not dirty
    assert not kym_file.get_kym_analysis().is_dirty

    # Mock save_analysis
    with patch.object(kym_file.get_kym_analysis(), "save_analysis") as mock_save:
        # Emit save selected intent
        bus.emit(SaveSelected(phase="intent"))

        # Should not call save_analysis when not dirty
        mock_save.assert_not_called()
