"""Tests for FolderController - unsaved changes dialog."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import tifffile

from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.core.image_loaders.acq_image_list import AcqImageList
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.controllers.folder_controller import FolderController
from kymflow.gui_v2.events_folder import PathChosen
from kymflow.gui_v2.state import AppState


@pytest.fixture
def app_state_with_dirty_file() -> tuple[AppState, KymImage]:
    """Create an AppState with a dirty file loaded."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.tif"
        test_image = np.zeros((100, 200), dtype=np.uint16)
        tifffile.imwrite(test_file, test_image)

        kym_file = KymImage(test_file, load_image=True)
        # Make file dirty (metadata only)
        kym_file.update_experiment_metadata(species="mouse")

        app_state = AppState()
        image_list = AcqImageList(path=None, image_cls=KymImage, file_extension=".tif", depth=1)
        image_list.images = [kym_file]
        app_state.files = image_list

        return app_state, kym_file


def test_folder_controller_shows_dialog_when_dirty(
    bus: EventBus, app_state_with_dirty_file: tuple[AppState, KymImage]
) -> None:
    """Test that FolderController shows dialog when any_dirty_analysis() returns True."""
    app_state, kym_file = app_state_with_dirty_file

    # Verify file is dirty
    assert app_state.files.any_dirty_analysis() is True

    controller = FolderController(app_state, bus, user_config=None)

    # Mock path checks and _show_unsaved_dialog to verify it's called
    new_folder = Path("/new/folder")
    with patch.object(Path, "is_file", return_value=False):
        with patch.object(Path, "is_dir", return_value=True):
            with patch.object(controller, "_show_unsaved_dialog") as mock_dialog:
                with patch.object(app_state, "load_folder") as mock_load:
                    # Emit path chosen event
                    bus.emit(PathChosen(new_path=str(new_folder), previous_path=None, depth=None, phase="intent"))

                    # Verify dialog was called (not load_folder)
                    mock_dialog.assert_called_once_with(new_folder)
                    mock_load.assert_not_called()


def test_folder_controller_loads_when_not_dirty(
    bus: EventBus, app_state_with_dirty_file: tuple[AppState, KymImage]
) -> None:
    """Test that FolderController loads folder directly when not dirty."""
    app_state, kym_file = app_state_with_dirty_file

    # Clear dirty state
    kym_file.clear_metadata_dirty()
    assert app_state.files.any_dirty_analysis() is False

    controller = FolderController(app_state, bus, user_config=None)

    # Mock path checks and app_state.load_folder to verify it's called
    new_folder = Path("/new/folder")
    with patch.object(Path, "is_file", return_value=False):
        with patch.object(Path, "is_dir", return_value=True):
            with patch.object(app_state, "load_folder") as mock_load:
                with patch.object(controller, "_show_unsaved_dialog") as mock_dialog:
                    # Emit path chosen event
                    bus.emit(PathChosen(new_path=str(new_folder), previous_path=None, depth=None, phase="intent"))

                    # Should call app_state.load_folder directly (no dialog)
                    mock_load.assert_called_once_with(new_folder, depth=app_state.folder_depth)
                    mock_dialog.assert_not_called()


def test_folder_controller_cancel_blocks_folder_switch(
    bus: EventBus, app_state_with_dirty_file: tuple[AppState, KymImage]
) -> None:
    """Test that canceling dialog prevents folder switch."""
    app_state, kym_file = app_state_with_dirty_file

    controller = FolderController(app_state, bus, user_config=None)

    # Mock path checks and _show_unsaved_dialog to simulate cancel
    new_folder = Path("/new/folder")
    with patch.object(Path, "is_file", return_value=False):
        with patch.object(Path, "is_dir", return_value=True):
            with patch.object(controller, "_show_unsaved_dialog") as mock_dialog:
                with patch.object(app_state, "load_folder") as mock_load:
                    # Emit path chosen event
                    bus.emit(PathChosen(new_path=str(new_folder), previous_path=None, depth=None, phase="intent"))

                    # Verify dialog was shown
                    mock_dialog.assert_called_once_with(new_folder)

                    # Simulate cancel: _confirm_switch_path is NOT called
                    # (In real UI, user clicks Cancel button which just closes dialog)
                    # So load_folder should NOT be called
                    mock_load.assert_not_called()


def test_folder_controller_confirm_proceeds_with_switch(
    bus: EventBus, app_state_with_dirty_file: tuple[AppState, KymImage]
) -> None:
    """Test that confirming dialog proceeds with folder switch."""
    app_state, kym_file = app_state_with_dirty_file

    controller = FolderController(app_state, bus, user_config=None)

    # Mock path checks and app_state.load_folder to verify it's called on confirm
    new_folder = Path("/new/folder")
    with patch.object(Path, "is_file", return_value=False):
        with patch.object(Path, "is_dir", return_value=True):
            with patch.object(app_state, "load_folder") as mock_load:
                # Mock _show_unsaved_dialog to simulate confirm
                def simulate_confirm(folder: Path) -> None:
                    # Simulate user clicking "Switch to folder" button
                    # This calls _confirm_switch_path which calls app_state.load_folder
                    controller._confirm_switch_path(MagicMock(), folder)

                with patch.object(controller, "_show_unsaved_dialog", side_effect=simulate_confirm):
                    # Emit path chosen event
                    bus.emit(PathChosen(new_path=str(new_folder), previous_path=None, depth=None, phase="intent"))

                    # Verify app_state.load_folder was called (folder switch proceeded)
                    mock_load.assert_called_once_with(new_folder, depth=app_state.folder_depth)


def test_folder_controller_does_not_persist_missing_folder(
    bus: EventBus,
) -> None:
    """Ensure missing paths do not update user config."""
    app_state = AppState()
    user_config = MagicMock()
    controller = FolderController(app_state, bus, user_config=user_config)

    with patch("pathlib.Path.exists", return_value=False):
        with patch("kymflow.gui_v2.controllers.folder_controller.ui.notify"):
            bus.emit(PathChosen(new_path="/missing/folder", previous_path=None, depth=None, phase="intent"))

    user_config.push_recent_folder.assert_not_called()


def test_folder_controller_persists_valid_folder_after_guard(
    bus: EventBus,
) -> None:
    """Ensure valid paths update user config after guard."""
    app_state = AppState()
    user_config = MagicMock()
    controller = FolderController(app_state, bus, user_config=user_config)

    folder_path = "/valid/folder"
    folder_path_obj = Path(folder_path)
    with patch.object(Path, "is_file", return_value=False):
        with patch.object(Path, "is_dir", return_value=True):
            with patch.object(app_state, "load_folder") as mock_load:
                bus.emit(PathChosen(new_path=folder_path, previous_path=None, depth=7, phase="intent"))

                assert app_state.folder_depth == 7
                mock_load.assert_called_once_with(folder_path_obj, depth=7)
                user_config.push_recent_folder.assert_called_once_with(folder_path, depth=7)
