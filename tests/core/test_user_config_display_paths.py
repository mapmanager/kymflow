"""Tests for UserConfig display path functionality (~ notation)."""

from __future__ import annotations

from pathlib import Path

import pytest

from kymflow.core.user_config import UserConfig, _path_to_display


# ============================================================================
# _path_to_display() Utility Tests
# ============================================================================

def test_path_to_display_under_home() -> None:
    """Test _path_to_display() converts paths under home directory to ~ notation."""
    home = Path.home()
    test_path = home / "Dropbox" / "file.tif"
    
    result = _path_to_display(str(test_path))
    
    # Should start with ~
    assert result.startswith("~")
    # Should contain the relative path
    assert "Dropbox" in result
    assert "file.tif" in result


def test_path_to_display_outside_home() -> None:
    """Test _path_to_display() leaves paths outside home directory unchanged."""
    # Use a path that's definitely outside home (on Unix systems)
    test_path = "/usr/local/bin"
    
    result = _path_to_display(test_path)
    
    # Should remain unchanged
    assert result == "/usr/local/bin"


def test_path_to_display_home_directory() -> None:
    """Test _path_to_display() converts home directory itself to ~."""
    home = Path.home()
    
    result = _path_to_display(str(home))
    
    # Should be just ~
    assert result == "~"


def test_path_to_display_already_tilde() -> None:
    """Test _path_to_display() handles paths that already use ~ notation."""
    test_path = "~/Dropbox/file.tif"
    
    result = _path_to_display(test_path)
    
    # Should still convert properly (expanduser then convert back)
    assert result.startswith("~")
    assert "Dropbox" in result


def test_path_to_display_relative_path() -> None:
    """Test _path_to_display() handles relative paths."""
    test_path = "relative/path/file.tif"
    
    result = _path_to_display(test_path)
    
    # Should handle gracefully (may expand to current dir or keep relative)
    assert isinstance(result, str)


def test_path_to_display_nested_under_home() -> None:
    """Test _path_to_display() handles deeply nested paths under home."""
    home = Path.home()
    test_path = home / "Documents" / "Projects" / "kymflow" / "data" / "file.tif"
    
    result = _path_to_display(str(test_path))
    
    # Should start with ~
    assert result.startswith("~")
    # Should contain the nested path
    assert "Documents" in result or "Projects" in result or "file.tif" in result


# ============================================================================
# Display API Methods Tests
# ============================================================================

@pytest.fixture
def user_config_with_paths(tmp_path: Path) -> UserConfig:
    """Create a UserConfig with some test paths."""
    cfg_path = tmp_path / "user_config.json"
    config = UserConfig.load(config_path=cfg_path, create_if_missing=True)
    
    # Add some test paths
    home = Path.home()
    test_folder = home / "TestFolder"
    test_file = home / "TestFile.tif"
    test_csv = home / "TestCSV.csv"
    
    # Create the paths if they don't exist (for testing)
    test_folder.mkdir(parents=True, exist_ok=True)
    test_file.touch(exist_ok=True)
    test_csv.touch(exist_ok=True)
    
    config.push_recent_path(test_folder, depth=2)
    config.push_recent_path(test_file, depth=0)
    config.push_recent_csv(test_csv)
    config.save()
    
    return config


def test_get_recent_folders_display(user_config_with_paths: UserConfig) -> None:
    """Test get_recent_folders_display() returns paths with ~ notation."""
    display_paths = user_config_with_paths.get_recent_folders_display()
    full_paths = user_config_with_paths.get_recent_folders()
    
    # Should have same number of items
    assert len(display_paths) == len(full_paths)
    
    # Display paths should use ~ notation for paths under home
    for (display_path, depth), (full_path, full_depth) in zip(display_paths, full_paths):
        assert depth == full_depth
        # If full path is under home, display should start with ~
        if str(full_path).startswith(str(Path.home())):
            assert display_path.startswith("~")
        # Display path should be different from full path (unless outside home)
        if str(full_path).startswith(str(Path.home())):
            assert display_path != full_path


def test_get_recent_files_display(user_config_with_paths: UserConfig) -> None:
    """Test get_recent_files_display() returns paths with ~ notation."""
    display_paths = user_config_with_paths.get_recent_files_display()
    full_paths = user_config_with_paths.get_recent_files()
    
    # Should have same number of items
    assert len(display_paths) == len(full_paths)
    
    # Display paths should use ~ notation for paths under home
    for display_path, full_path in zip(display_paths, full_paths):
        # If full path is under home, display should start with ~
        if str(full_path).startswith(str(Path.home())):
            assert display_path.startswith("~")
        # Display path should be different from full path (unless outside home)
        if str(full_path).startswith(str(Path.home())):
            assert display_path != full_path


def test_get_recent_csvs_display(user_config_with_paths: UserConfig) -> None:
    """Test get_recent_csvs_display() returns paths with ~ notation."""
    display_paths = user_config_with_paths.get_recent_csvs_display()
    full_paths = user_config_with_paths.get_recent_csvs()
    
    # Should have same number of items
    assert len(display_paths) == len(full_paths)
    
    # Display paths should use ~ notation for paths under home
    for display_path, full_path in zip(display_paths, full_paths):
        # If full path is under home, display should start with ~
        if str(full_path).startswith(str(Path.home())):
            assert display_path.startswith("~")
        # Display path should be different from full path (unless outside home)
        if str(full_path).startswith(str(Path.home())):
            assert display_path != full_path


def test_display_api_preserves_structure(user_config_with_paths: UserConfig) -> None:
    """Test that display API methods preserve the same structure as original methods."""
    # Folders: should return tuples of (path, depth)
    display_folders = user_config_with_paths.get_recent_folders_display()
    full_folders = user_config_with_paths.get_recent_folders()
    
    assert len(display_folders) == len(full_folders)
    for (display_path, display_depth), (full_path, full_depth) in zip(display_folders, full_folders):
        assert isinstance(display_path, str)
        assert isinstance(display_depth, int)
        assert display_depth == full_depth
    
    # Files: should return list of strings
    display_files = user_config_with_paths.get_recent_files_display()
    full_files = user_config_with_paths.get_recent_files()
    
    assert len(display_files) == len(full_files)
    for display_path in display_files:
        assert isinstance(display_path, str)
    
    # CSVs: should return list of strings
    display_csvs = user_config_with_paths.get_recent_csvs_display()
    full_csvs = user_config_with_paths.get_recent_csvs()
    
    assert len(display_csvs) == len(full_csvs)
    for display_path in display_csvs:
        assert isinstance(display_path, str)
