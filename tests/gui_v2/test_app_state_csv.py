"""Tests for AppState CSV loading functionality."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest
import tifffile

from kymflow.core.image_loaders.acq_image_list import AcqImageList
from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.gui_v2.state import AppState


@pytest.fixture
def app_state() -> AppState:
    """Create a fresh AppState instance."""
    return AppState()


def test_load_path_detects_csv(app_state: AppState) -> None:
    """Test that load_path() detects CSV files by extension."""
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_file = Path(tmpdir) / "test.csv"
        file1 = Path(tmpdir) / "file1.tif"
        file2 = Path(tmpdir) / "file2.tif"
        test_image = np.zeros((100, 200), dtype=np.uint16)
        tifffile.imwrite(file1, test_image)
        tifffile.imwrite(file2, test_image)
        
        csv_file.write_text(f"path\n{file1}\n{file2}")
        
        # Should detect CSV and load it
        app_state.load_path(csv_file, depth=0)
        
        # Verify files were loaded
        assert len(app_state.files.images) == 2
        assert app_state.folder == csv_file


def test_load_path_csv_valid(app_state: AppState) -> None:
    """Test load_path() with valid CSV containing 'path' column."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create CSV with path column
        csv_file = Path(tmpdir) / "test.csv"
        
        # Create actual TIF files referenced in CSV
        file1 = Path(tmpdir) / "file1.tif"
        file2 = Path(tmpdir) / "file2.tif"
        test_image = np.zeros((100, 200), dtype=np.uint16)
        tifffile.imwrite(file1, test_image)
        tifffile.imwrite(file2, test_image)
        
        # Update CSV to use actual paths
        csv_file.write_text(f"path\n{file1}\n{file2}")
        
        # Mock file_list_changed handlers
        handler_called = False
        def mock_handler() -> None:
            nonlocal handler_called
            handler_called = True
        
        app_state.on_file_list_changed(mock_handler)
        
        # Load CSV via load_path
        app_state.load_path(csv_file)
        
        # Verify AcqImageList was created
        assert app_state.files is not None
        assert isinstance(app_state.files, AcqImageList)
        assert len(app_state.files.images) == 2
        
        # Verify folder is set to CSV path
        assert app_state.folder == csv_file
        
        # Verify handler was called
        assert handler_called


def test_load_path_csv_missing_path_column(app_state: AppState) -> None:
    """Test load_path() raises ValueError when 'path' column is missing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_file = Path(tmpdir) / "test.csv"
        csv_file.write_text("name,value\nfile1,1\nfile2,2")
        
        with pytest.raises(ValueError, match="CSV must have a 'path' column"):
            app_state.load_path(csv_file)


def test_load_path_csv_invalid_format(app_state: AppState) -> None:
    """Test load_path() handles pandas read errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_file = Path(tmpdir) / "test.csv"
        csv_file.write_text("invalid,malformed,csv")
        
        # Mock pandas to raise EmptyDataError
        with patch("kymflow.gui_v2.state.pd") as mock_pd:
            import pandas.errors
            mock_pd.read_csv.side_effect = pandas.errors.EmptyDataError("Empty CSV")
            
            # Should raise ValueError (wrapped by load_path)
            with pytest.raises(ValueError, match="Failed to read CSV file"):
                app_state.load_path(csv_file)


def test_load_path_csv_empty_paths(app_state: AppState) -> None:
    """Test load_path() with CSV containing no paths (empty DataFrame)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_file = Path(tmpdir) / "test.csv"
        csv_file.write_text("path\n")
        
        # Empty path_list should raise ValueError (AcqImageList doesn't allow empty file_path_list)
        with pytest.raises(ValueError, match="file_path_list cannot be empty"):
            app_state.load_path(csv_file)


def test_load_path_csv_sets_folder(app_state: AppState) -> None:
    """Test load_path() sets app_state.folder to CSV path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_file = Path(tmpdir) / "test.csv"
        file1 = Path(tmpdir) / "file1.tif"
        test_image = np.zeros((100, 200), dtype=np.uint16)
        tifffile.imwrite(file1, test_image)
        
        csv_file.write_text(f"path\n{file1}")
        
        app_state.load_path(csv_file)
        
        assert app_state.folder == csv_file


def test_load_path_csv_triggers_callbacks(app_state: AppState) -> None:
    """Test load_path() triggers file_list_changed callbacks."""
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_file = Path(tmpdir) / "test.csv"
        file1 = Path(tmpdir) / "file1.tif"
        test_image = np.zeros((100, 200), dtype=np.uint16)
        tifffile.imwrite(file1, test_image)
        
        csv_file.write_text(f"path\n{file1}")
        
        handler_called = False
        def mock_handler() -> None:
            nonlocal handler_called
            handler_called = True
        
        app_state.on_file_list_changed(mock_handler)
        app_state.load_path(csv_file)
        
        assert handler_called


def test_refresh_file_rows_with_csv(app_state: AppState) -> None:
    """Test refresh_file_rows() works correctly when loaded from CSV."""
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_file = Path(tmpdir) / "test.csv"
        file1 = Path(tmpdir) / "file1.tif"
        file2 = Path(tmpdir) / "file2.tif"
        test_image = np.zeros((100, 200), dtype=np.uint16)
        tifffile.imwrite(file1, test_image)
        tifffile.imwrite(file2, test_image)
        
        csv_file.write_text(f"path\n{file1}\n{file2}")
        
        app_state.load_path(csv_file)
        
        # Verify files are loaded
        assert len(app_state.files.images) == 2
        
        # Refresh should work (reloads CSV, but shouldn't error)
        app_state.refresh_file_rows()
        
        # Files should still be there
        assert len(app_state.files.images) == 2
