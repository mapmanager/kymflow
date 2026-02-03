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
from kymflow.gui_v2.events_folder import SelectPathEvent, CancelSelectPathEvent
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
                    bus.emit(SelectPathEvent(new_path=str(new_folder), depth=None, phase="intent"))

                    # Verify dialog was called (not load_folder)
                    # _show_unsaved_dialog takes: new_path, previous_path_str, original_depth
                    mock_dialog.assert_called_once()
                    assert mock_dialog.call_args[0][0] == new_folder
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
                    bus.emit(SelectPathEvent(new_path=str(new_folder), depth=None, phase="intent"))

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
                    bus.emit(SelectPathEvent(new_path=str(new_folder), depth=None, phase="intent"))

                    # Verify dialog was shown
                    # _show_unsaved_dialog takes: new_path, previous_path_str, original_depth
                    mock_dialog.assert_called_once()
                    assert mock_dialog.call_args[0][0] == new_folder

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
                def simulate_confirm(new_path: Path, previous_path_str: str | None, original_depth: int | None) -> None:
                    # Simulate user clicking "Switch to folder" button
                    # This calls _confirm_switch_path which calls app_state.load_folder
                    controller._confirm_switch_path(MagicMock(), new_path, previous_path_str, original_depth)

                with patch.object(controller, "_show_unsaved_dialog", side_effect=simulate_confirm):
                    # Emit path chosen event
                    bus.emit(SelectPathEvent(new_path=str(new_folder), depth=None, phase="intent"))

                    # Verify app_state.load_folder was called (folder switch proceeded)
                    mock_load.assert_called_once_with(new_folder, depth=app_state.folder_depth)


def test_folder_controller_does_not_persist_missing_folder(
    bus: EventBus,
) -> None:
    """Ensure missing paths do not update user config and emit CancelSelectPathEvent."""
    app_state = AppState()
    app_state.folder = Path("/current/folder")  # Set current path
    user_config = MagicMock()
    controller = FolderController(app_state, bus, user_config=user_config)

    emitted_events = []
    def capture_event(e):
        emitted_events.append(e)
    bus.subscribe(CancelSelectPathEvent, capture_event)

    with patch("pathlib.Path.exists", return_value=False):
        with patch("kymflow.gui_v2.controllers.folder_controller.ui.notify"):
            bus.emit(SelectPathEvent(new_path="/missing/folder", depth=None, phase="intent"))

    user_config.push_recent_folder.assert_not_called()
    # Should emit CancelSelectPathEvent with previous_path
    assert len(emitted_events) == 1
    assert isinstance(emitted_events[0], CancelSelectPathEvent)
    assert emitted_events[0].previous_path == "/current/folder"


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
                bus.emit(SelectPathEvent(new_path=folder_path, depth=7, phase="intent"))

                assert app_state.folder_depth == 7
                mock_load.assert_called_once_with(folder_path_obj, depth=7)
                user_config.push_recent_folder.assert_called_once_with(folder_path, depth=7)


def test_folder_controller_handles_file_path(
    bus: EventBus,
) -> None:
    """Test that FolderController handles file paths correctly (depth=0)."""
    app_state = AppState()
    user_config = MagicMock()
    controller = FolderController(app_state, bus, user_config=user_config)

    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.tif"
        test_image = np.zeros((100, 200), dtype=np.uint16)
        tifffile.imwrite(test_file, test_image)
        
        # Ensure file exists
        assert test_file.exists() and test_file.is_file()

        with patch.object(app_state, "load_folder") as mock_load:
            bus.emit(SelectPathEvent(new_path=str(test_file), depth=None, phase="intent"))

            # Should call load_folder with depth=0 for files
            mock_load.assert_called_once_with(test_file, depth=0)
            # Should persist with depth=0
            user_config.push_recent_folder.assert_called_once_with(str(test_file), depth=0)


def test_folder_controller_uses_depth_from_event(
    bus: EventBus,
) -> None:
    """Test that FolderController uses depth from SelectPathEvent for folders."""
    app_state = AppState()
    app_state.folder_depth = 1  # Default depth
    user_config = MagicMock()
    controller = FolderController(app_state, bus, user_config=user_config)

    folder_path = "/valid/folder"
    folder_path_obj = Path(folder_path)
    with patch.object(Path, "is_file", return_value=False):
        with patch.object(Path, "is_dir", return_value=True):
            with patch.object(app_state, "load_folder") as mock_load:
                bus.emit(SelectPathEvent(new_path=folder_path, depth=5, phase="intent"))

                # Should update folder_depth and use it
                assert app_state.folder_depth == 5
                mock_load.assert_called_once_with(folder_path_obj, depth=5)
                user_config.push_recent_folder.assert_called_once_with(folder_path, depth=5)
