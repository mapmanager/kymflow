"""Tests for FolderController helper functions."""

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
from kymflow.gui_v2.events_folder import CancelSelectPathEvent
from kymflow.gui_v2.state import AppState


@pytest.fixture
def bus() -> EventBus:
    """Create an EventBus instance."""
    from kymflow.gui_v2.bus import EventBus, BusConfig
    return EventBus(client_id="test-client", config=BusConfig(trace=False))


@pytest.fixture
def app_state() -> AppState:
    """Create a fresh AppState instance."""
    return AppState()


# ============================================================================
# Path Type Detection Helper Tests
# ============================================================================

def test_detect_path_type_file(bus: EventBus, app_state: AppState) -> None:
    """Test _detect_path_type for file."""
    controller = FolderController(app_state, bus, user_config=None)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.tif"
        test_image = np.zeros((100, 200), dtype=np.uint16)
        tifffile.imwrite(test_file, test_image)
        
        is_file, is_folder, is_csv = controller._detect_path_type(test_file)
        assert is_file is True
        assert is_folder is False
        assert is_csv is False


def test_detect_path_type_folder(bus: EventBus, app_state: AppState) -> None:
    """Test _detect_path_type for folder."""
    controller = FolderController(app_state, bus, user_config=None)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        test_folder = Path(tmpdir)
        
        is_file, is_folder, is_csv = controller._detect_path_type(test_folder)
        assert is_file is False
        assert is_folder is True
        assert is_csv is False


def test_detect_path_type_csv(bus: EventBus, app_state: AppState) -> None:
    """Test _detect_path_type for CSV file."""
    controller = FolderController(app_state, bus, user_config=None)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_file = Path(tmpdir) / "test.csv"
        csv_file.write_text("path\n/file1.tif")
        
        is_file, is_folder, is_csv = controller._detect_path_type(csv_file)
        assert is_file is True
        assert is_folder is False
        assert is_csv is True


def test_detect_path_type_nonexistent(bus: EventBus, app_state: AppState) -> None:
    """Test _detect_path_type for nonexistent path."""
    controller = FolderController(app_state, bus, user_config=None)
    
    nonexistent = Path("/nonexistent/path")
    
    is_file, is_folder, is_csv = controller._detect_path_type(nonexistent)
    assert is_file is False
    assert is_folder is False
    assert is_csv is False


# ============================================================================
# Thread Runner Check Helper Tests
# ============================================================================

def test_check_thread_runner_available_when_available(bus: EventBus, app_state: AppState) -> None:
    """Test _check_thread_runner_available when thread runner is available."""
    controller = FolderController(app_state, bus, user_config=None)
    
    # Thread runner should not be running initially
    assert controller._thread_runner.is_running() is False
    
    result = controller._check_thread_runner_available("/current/path")
    assert result is True


def test_check_thread_runner_available_when_busy(bus: EventBus, app_state: AppState) -> None:
    """Test _check_thread_runner_available when thread runner is busy."""
    controller = FolderController(app_state, bus, user_config=None)
    
    # Mock thread runner as running
    with patch.object(controller._thread_runner, "is_running", return_value=True):
        with patch("kymflow.gui_v2.controllers.folder_controller.ui.notify") as mock_notify:
            emitted_events = []
            def capture_event(e):
                emitted_events.append(e)
            bus.subscribe(CancelSelectPathEvent, capture_event)
            
            result = controller._check_thread_runner_available("/current/path")
            
            assert result is False
            mock_notify.assert_called_once()
            assert len(emitted_events) == 1
            assert isinstance(emitted_events[0], CancelSelectPathEvent)
            assert emitted_events[0].previous_path == "/current/path"


def test_check_thread_runner_available_no_current_path(bus: EventBus, app_state: AppState) -> None:
    """Test _check_thread_runner_available when no current path."""
    controller = FolderController(app_state, bus, user_config=None)
    
    # Mock thread runner as running
    with patch.object(controller._thread_runner, "is_running", return_value=True):
        with patch("kymflow.gui_v2.controllers.folder_controller.ui.notify") as mock_notify:
            emitted_events = []
            def capture_event(e):
                emitted_events.append(e)
            bus.subscribe(CancelSelectPathEvent, capture_event)
            
            result = controller._check_thread_runner_available(None)
            
            assert result is False
            mock_notify.assert_called_once()
            # Should not emit CancelSelectPathEvent when no current path
            assert len(emitted_events) == 0


# ============================================================================
# Config Persistence Helper Tests
# ============================================================================

def test_persist_path_to_config_file(bus: EventBus, app_state: AppState) -> None:
    """Test _persist_path_to_config for file."""
    user_config = MagicMock()
    controller = FolderController(app_state, bus, user_config=user_config)
    
    test_file = Path("/test/file.tif")
    controller._persist_path_to_config(test_file, depth=0, is_file=True, is_csv=False)
    
    user_config.push_recent_path.assert_called_once_with(str(test_file), depth=0)
    user_config.push_recent_csv.assert_not_called()


def test_persist_path_to_config_folder(bus: EventBus, app_state: AppState) -> None:
    """Test _persist_path_to_config for folder."""
    user_config = MagicMock()
    controller = FolderController(app_state, bus, user_config=user_config)
    
    test_folder = Path("/test/folder")
    controller._persist_path_to_config(test_folder, depth=5, is_file=False, is_csv=False)
    
    user_config.push_recent_path.assert_called_once_with(str(test_folder), depth=5)
    user_config.push_recent_csv.assert_not_called()


def test_persist_path_to_config_csv(bus: EventBus, app_state: AppState) -> None:
    """Test _persist_path_to_config for CSV."""
    user_config = MagicMock()
    controller = FolderController(app_state, bus, user_config=user_config)
    
    csv_file = Path("/test/file.csv")
    controller._persist_path_to_config(csv_file, depth=0, is_file=True, is_csv=True)
    
    user_config.push_recent_csv.assert_called_once_with(str(csv_file))
    user_config.push_recent_path.assert_not_called()


def test_persist_path_to_config_no_user_config(bus: EventBus, app_state: AppState) -> None:
    """Test _persist_path_to_config when user_config is None."""
    controller = FolderController(app_state, bus, user_config=None)
    
    # Should not raise an error
    test_file = Path("/test/file.tif")
    controller._persist_path_to_config(test_file, depth=0, is_file=True, is_csv=False)
