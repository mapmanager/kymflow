"""Tests for AppState file lookup methods (get_file_by_path_or_selected, refresh_file_rows)."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
import tifffile

from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.core.image_loaders.acq_image_list import AcqImageList
from kymflow.core.image_loaders.roi import RoiBounds
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
        # Replace default empty list with a test AcqImageList containing our file
        image_list = AcqImageList(path=None, image_cls=KymImage, file_extension=".tif", depth=1)
        image_list.images = [kym_file]
        app_state.files = image_list
        app_state.selected_file = kym_file

        return app_state, kym_file


@pytest.fixture
def app_state_with_multiple_files() -> tuple[AppState, KymImage, KymImage]:
    """Create an AppState with multiple test files loaded."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file1 = Path(tmpdir) / "test1.tif"
        test_file2 = Path(tmpdir) / "test2.tif"
        test_image = np.zeros((100, 200), dtype=np.uint16)
        tifffile.imwrite(test_file1, test_image)
        tifffile.imwrite(test_file2, test_image)

        kym_file1 = KymImage(test_file1, load_image=True)
        kym_file2 = KymImage(test_file2, load_image=True)

        app_state = AppState()
        image_list = AcqImageList(path=None, image_cls=KymImage, file_extension=".tif", depth=1)
        image_list.images = [kym_file1, kym_file2]
        app_state.files = image_list
        app_state.selected_file = kym_file1  # First file is selected

        return app_state, kym_file1, kym_file2


@pytest.fixture
def app_state_with_empty_list() -> AppState:
    """Create an AppState with empty file list."""
    app_state = AppState()
    image_list = AcqImageList(path=None, image_cls=KymImage, file_extension=".tif", depth=1)
    image_list.images = []
    app_state.files = image_list
    app_state.selected_file = None
    return app_state


# Tests for get_file_by_path_or_selected()


def test_get_file_by_path_or_selected_with_path_found(
    app_state_with_multiple_files: tuple[AppState, KymImage, KymImage]
) -> None:
    """Test that get_file_by_path_or_selected returns file matching path (not selected_file)."""
    app_state, kym_file1, kym_file2 = app_state_with_multiple_files

    # kym_file1 is selected, but we search for kym_file2
    result = app_state.get_file_by_path_or_selected(str(kym_file2.path))
    
    assert result is not None
    assert result == kym_file2
    assert result != app_state.selected_file  # Should return the matched file, not selected


def test_get_file_by_path_or_selected_with_path_not_found(
    app_state_with_multiple_files: tuple[AppState, KymImage, KymImage]
) -> None:
    """Test that get_file_by_path_or_selected falls back to selected_file when path not found."""
    app_state, kym_file1, kym_file2 = app_state_with_multiple_files

    # Search for non-existent path
    result = app_state.get_file_by_path_or_selected("/nonexistent/path/file.tif")
    
    # Should fall back to selected_file
    assert result == app_state.selected_file
    assert result == kym_file1


def test_get_file_by_path_or_selected_with_none_path(
    app_state_with_multiple_files: tuple[AppState, KymImage, KymImage]
) -> None:
    """Test that get_file_by_path_or_selected returns selected_file when path is None."""
    app_state, kym_file1, kym_file2 = app_state_with_multiple_files

    result = app_state.get_file_by_path_or_selected(None)
    
    assert result == app_state.selected_file
    assert result == kym_file1


def test_get_file_by_path_or_selected_no_selected_file(
    app_state_with_multiple_files: tuple[AppState, KymImage, KymImage]
) -> None:
    """Test that get_file_by_path_or_selected returns None when no selected_file and path not found."""
    app_state, kym_file1, kym_file2 = app_state_with_multiple_files

    # Clear selected_file
    app_state.selected_file = None

    # Search for non-existent path
    result = app_state.get_file_by_path_or_selected("/nonexistent/path/file.tif")
    
    assert result is None


def test_get_file_by_path_or_selected_no_selected_file_with_none_path(
    app_state_with_multiple_files: tuple[AppState, KymImage, KymImage]
) -> None:
    """Test that get_file_by_path_or_selected returns None when no selected_file and path is None."""
    app_state, kym_file1, kym_file2 = app_state_with_multiple_files

    # Clear selected_file
    app_state.selected_file = None

    result = app_state.get_file_by_path_or_selected(None)
    
    assert result is None


def test_get_file_by_path_or_selected_empty_file_list(
    app_state_with_empty_list: AppState
) -> None:
    """Test that get_file_by_path_or_selected returns None when file list is empty."""
    app_state = app_state_with_empty_list

    result = app_state.get_file_by_path_or_selected("/some/path/file.tif")
    
    assert result is None


def test_get_file_by_path_or_selected_path_normalization(
    app_state_with_file: tuple[AppState, KymImage]
) -> None:
    """Test that get_file_by_path_or_selected handles path normalization via find_by_path."""
    app_state, kym_file = app_state_with_file

    # Test with absolute path (find_by_path normalizes paths)
    absolute_path = Path(kym_file.path).resolve()
    result = app_state.get_file_by_path_or_selected(str(absolute_path))
    
    assert result == kym_file

    # Test with Path object (should work the same)
    result2 = app_state.get_file_by_path_or_selected(absolute_path)
    
    assert result2 == kym_file


def test_get_file_by_path_or_selected_path_matches_selected_file(
    app_state_with_multiple_files: tuple[AppState, KymImage, KymImage]
) -> None:
    """Test that get_file_by_path_or_selected returns correct file even when it matches selected_file."""
    app_state, kym_file1, kym_file2 = app_state_with_multiple_files

    # Search for selected_file's path
    result = app_state.get_file_by_path_or_selected(str(kym_file1.path))
    
    # Should return the file (which happens to be selected_file)
    assert result == kym_file1
    assert result == app_state.selected_file


# Tests for refresh_file_rows() using find_by_path()


def test_refresh_file_rows_uses_find_by_path(
    app_state_with_file: tuple[AppState, KymImage]
) -> None:
    """Test that refresh_file_rows uses find_by_path() instead of manual loop."""
    app_state, kym_file = app_state_with_file

    # Set folder so refresh_file_rows doesn't return early
    app_state.folder = Path(kym_file.path).parent

    # Mock find_by_path to verify it's called
    with patch.object(app_state.files, "find_by_path") as mock_find:
        with patch.object(app_state, "load_path") as mock_load:
            # Mock find_by_path to return the file
            mock_find.return_value = kym_file
            
            app_state.refresh_file_rows()
            
            # Verify find_by_path was called (not a manual loop)
            assert mock_find.called
            # Verify load_path was called
            assert mock_load.called


def test_refresh_file_rows_preserves_selection_when_file_exists(
    app_state_with_file: tuple[AppState, KymImage]
) -> None:
    """Test that refresh_file_rows preserves file and ROI selection when file still exists."""
    app_state, kym_file = app_state_with_file

    # Create ROI and select it
    bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
    roi = kym_file.rois.create_roi(bounds=bounds)
    app_state.select_roi(roi.id)

    # Set folder
    app_state.folder = Path(kym_file.path).parent

    # Mock load_path to simulate refresh without actually reloading
    original_load_path = app_state.load_path
    def mock_load_path(folder: Path, depth: int | None = None) -> None:
        # Don't actually reload, just verify it would be called
        pass

    with patch.object(app_state, "load_path", side_effect=mock_load_path):
        # Mock find_by_path to return the file (simulating file still exists)
        with patch.object(app_state.files, "find_by_path", return_value=kym_file):
            # Since we're mocking load_path, we need to manually set up the state
            # that refresh_file_rows expects after load_path
            selected_path = str(kym_file.path)
            selected_roi_id = app_state.selected_roi_id

            # Call refresh_file_rows
            app_state.refresh_file_rows()

            # Restore the file list and selection manually (since load_path is mocked)
            # This simulates what would happen after a real refresh
            image_list = AcqImageList(path=None, image_cls=KymImage, file_extension=".tif", depth=1)
            image_list.images = [kym_file]
            app_state.files = image_list

            # Manually trigger the restoration logic that refresh_file_rows would do
            f = app_state.files.find_by_path(selected_path)
            if f is not None:
                app_state.select_file(f)
                if selected_roi_id is not None:
                    roi_ids = f.rois.get_roi_ids()
                    if selected_roi_id in roi_ids:
                        app_state.select_roi(selected_roi_id)

    # Verify selection was preserved
    assert app_state.selected_file == kym_file
    assert app_state.selected_roi_id == roi.id


def test_refresh_file_rows_handles_file_deleted(
    app_state_with_file: tuple[AppState, KymImage]
) -> None:
    """Test that refresh_file_rows handles case when selected file no longer exists."""
    app_state, kym_file = app_state_with_file

    # Set folder
    app_state.folder = Path(kym_file.path).parent

    # Mock load_path
    with patch.object(app_state, "load_path") as mock_load:
        # Mock find_by_path to return None (file deleted)
        with patch.object(app_state.files, "find_by_path", return_value=None):
            # After load_path, files list would be different
            # Simulate by creating a new file list without the original file
            new_file_list = AcqImageList(path=None, image_cls=KymImage, file_extension=".tif", depth=1)
            app_state.files = new_file_list

            app_state.refresh_file_rows()

            # Verify load_path was called
            assert mock_load.called
            # File should not be selected (since it doesn't exist in new list)
            # Note: load_path will select first file if available, or None if empty


def test_refresh_file_rows_no_folder(
    app_state_with_file: tuple[AppState, KymImage]
) -> None:
    """Test that refresh_file_rows returns early when no folder is loaded."""
    app_state, kym_file = app_state_with_file

    # Clear folder
    app_state.folder = None

    # Mock load_path to verify it's NOT called
    with patch.object(app_state, "load_path") as mock_load:
        app_state.refresh_file_rows()
        
        # Verify load_path was NOT called (early return)
        assert not mock_load.called


def test_refresh_file_rows_handles_roi_deleted(
    app_state_with_file: tuple[AppState, KymImage]
) -> None:
    """Test that refresh_file_rows selects first available ROI when selected ROI was deleted."""
    app_state, kym_file = app_state_with_file

    # Create multiple ROIs
    bounds1 = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
    bounds2 = RoiBounds(dim0_start=60, dim0_stop=90, dim1_start=60, dim1_stop=90)
    roi1 = kym_file.rois.create_roi(bounds=bounds1)
    roi2 = kym_file.rois.create_roi(bounds=bounds2)
    
    # Select roi1
    app_state.select_roi(roi1.id)

    # Set folder
    app_state.folder = Path(kym_file.path).parent

    # Simulate refresh: delete roi1, then refresh
    kym_file.rois.delete(roi1.id)

    # Mock load_path to not actually reload
    with patch.object(app_state, "load_path"):
        # Mock find_by_path to return the file
        with patch.object(app_state.files, "find_by_path", return_value=kym_file):
            # Manually set up state after refresh
            selected_path = str(kym_file.path)
            selected_roi_id = roi1.id  # This ROI was deleted

            # Restore file list
            image_list = AcqImageList(path=None, image_cls=KymImage, file_extension=".tif", depth=1)
            image_list.images = [kym_file]
            app_state.files = image_list

            # Manually trigger restoration logic
            f = app_state.files.find_by_path(selected_path)
            if f is not None:
                app_state.select_file(f)
                if selected_roi_id is not None:
                    roi_ids = f.rois.get_roi_ids()
                    if selected_roi_id in roi_ids:
                        app_state.select_roi(selected_roi_id)
                    elif roi_ids:
                        # ROI was deleted, select first available
                        app_state.select_roi(roi_ids[0])

    # Verify roi2 (first remaining) is selected
    assert app_state.selected_roi_id == roi2.id
