# tests/core/test_user_config.py
from __future__ import annotations

import json
from pathlib import Path

from kymflow.core.user_config import (
    DEFAULT_FOLDER_DEPTH,
    DEFAULT_WINDOW_RECT,
    DEFAULT_HOME_FILE_PLOT_SPLITTER,
    DEFAULT_HOME_PLOT_EVENT_SPLITTER,
    HOME_FILE_PLOT_SPLITTER_RANGE,
    HOME_PLOT_EVENT_SPLITTER_RANGE,
    SCHEMA_VERSION,
    UserConfig,
)


def test_load_defaults_when_missing(tmp_path: Path) -> None:
    cfg_path = tmp_path / "user_config.json"
    cfg = UserConfig.load(config_path=cfg_path)
    assert cfg.path == cfg_path
    assert cfg.data.schema_version == SCHEMA_VERSION
    assert cfg.get_recent_folders() == []
    assert cfg.get_last_path() == ("", DEFAULT_FOLDER_DEPTH)
    assert cfg.get_window_rect() == tuple(DEFAULT_WINDOW_RECT)
    assert cfg.get_home_splitter_positions() == (
        DEFAULT_HOME_FILE_PLOT_SPLITTER,
        DEFAULT_HOME_PLOT_EVENT_SPLITTER,
    )
    assert not cfg_path.exists()


def test_create_if_missing_writes_defaults(tmp_path: Path) -> None:
    cfg_path = tmp_path / "user_config.json"
    assert not cfg_path.exists()

    cfg = UserConfig.load(config_path=cfg_path, create_if_missing=True)
    assert cfg_path.exists()

    # File should be valid JSON with schema_version
    loaded = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    assert loaded["schema_version"] == SCHEMA_VERSION


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    cfg_path = tmp_path / "user_config.json"
    cfg = UserConfig.load(config_path=cfg_path)

    # Create actual folders that exist
    folder_a = tmp_path / "a"
    folder_b = tmp_path / "b"
    folder_a.mkdir()
    folder_b.mkdir()

    cfg.push_recent_path(folder_a, depth=2)
    cfg.push_recent_path(folder_b, depth=3)
    cfg.set_window_rect(1, 2, 3, 4)
    cfg.set_home_splitter_positions(12.5, 61.0)
    cfg.save()

    cfg2 = UserConfig.load(config_path=cfg_path)
    assert cfg2.get_last_path() == (str(folder_b.resolve(strict=False)), 3)
    recents = cfg2.get_recent_folders()
    assert len(recents) == 2
    assert recents[0][1] == 3
    assert recents[1][1] == 2
    assert cfg2.get_window_rect() == (1, 2, 3, 4)
    assert cfg2.get_home_splitter_positions() == (12.5, 61.0)


def test_push_recent_moves_to_front_and_updates_depth(tmp_path: Path) -> None:
    cfg_path = tmp_path / "user_config.json"
    cfg = UserConfig.load(config_path=cfg_path)

    cfg.push_recent_path("/tmp/a", depth=2)
    cfg.push_recent_path("/tmp/b", depth=3)
    cfg.push_recent_path("/tmp/a", depth=5)  # move to front + update depth

    recents = cfg.get_recent_folders()
    assert recents[0][0] == str(Path("/tmp/a").resolve(strict=False))
    assert recents[0][1] == 5
    assert recents[1][0] == str(Path("/tmp/b").resolve(strict=False))
    assert recents[1][1] == 3

    assert cfg.get_last_path() == (str(Path("/tmp/a").resolve(strict=False)), 5)


def test_set_last_path_does_not_reorder_recents(tmp_path: Path) -> None:
    cfg_path = tmp_path / "user_config.json"
    cfg = UserConfig.load(config_path=cfg_path)

    cfg.push_recent_path("/tmp/a", depth=2)
    cfg.push_recent_path("/tmp/b", depth=3)
    cfg.set_last_path("/tmp/a", depth=9)

    recents = cfg.get_recent_folders()
    assert recents[0][0] == str(Path("/tmp/b").resolve(strict=False))
    assert recents[1][0] == str(Path("/tmp/a").resolve(strict=False))
    assert cfg.get_last_path() == (str(Path("/tmp/a").resolve(strict=False)), 9)


def test_get_depth_for_folder_falls_back_to_default(tmp_path: Path) -> None:
    cfg_path = tmp_path / "user_config.json"
    cfg = UserConfig.load(config_path=cfg_path)

    assert cfg.get_depth_for_folder("/tmp/never_seen") == DEFAULT_FOLDER_DEPTH
    cfg.set_default_folder_depth(7)
    assert cfg.get_depth_for_folder("/tmp/never_seen") == 7

    cfg.push_recent_path("/tmp/a", depth=2)
    assert cfg.get_depth_for_folder("/tmp/a") == 2


def test_get_depth_for_folder_with_file_path(tmp_path: Path) -> None:
    """Test that get_depth_for_folder returns 0 for file paths."""
    cfg_path = tmp_path / "user_config.json"
    cfg = UserConfig.load(config_path=cfg_path)
    
    # Create a test file
    test_file = tmp_path / "test.tif"
    test_file.touch()
    
    # File paths should return 0 (depth is ignored for files)
    assert cfg.get_depth_for_folder(test_file) == 0
    assert cfg.get_depth_for_folder(str(test_file)) == 0
    
    # Even if the file is in recent folders, it should return 0
    cfg.push_recent_path(str(test_file.parent), depth=3)
    assert cfg.get_depth_for_folder(test_file) == 0


def test_schema_mismatch_resets(tmp_path: Path) -> None:
    cfg_path = tmp_path / "user_config.json"

    payload = {
        "schema_version": 999,
        "recent_folders": [{"path": "/tmp/a", "depth": 2}],
        "last_folder": {"path": "/tmp/a", "depth": 2},
        "window_rect": [9, 9, 9, 9],
        "default_folder_depth": 4,
    }
    cfg_path.write_text(json.dumps(payload), encoding="utf-8")

    cfg = UserConfig.load(config_path=cfg_path, schema_version=SCHEMA_VERSION, reset_on_version_mismatch=True)
    assert cfg.get_recent_folders() == []
    assert cfg.get_last_path() == ("", DEFAULT_FOLDER_DEPTH)
    assert cfg.get_window_rect() == tuple(DEFAULT_WINDOW_RECT)


def test_schema_mismatch_without_reset_keeps_data_but_updates_version(tmp_path: Path) -> None:
    cfg_path = tmp_path / "user_config.json"

    # Create actual folder that exists
    folder_a = tmp_path / "a"
    folder_a.mkdir()
    folder_a_path = str(folder_a.resolve(strict=False))

    payload = {
        "schema_version": 999,
        "recent_folders": [{"path": folder_a_path, "depth": 2}],
        "last_path": {"path": folder_a_path, "depth": 2},  # Use last_path (new API)
        "window_rect": [9, 9, 9, 9],
        "default_folder_depth": 4,
    }
    cfg_path.write_text(json.dumps(payload), encoding="utf-8")

    cfg = UserConfig.load(config_path=cfg_path, schema_version=SCHEMA_VERSION, reset_on_version_mismatch=False)
    assert cfg.data.schema_version == SCHEMA_VERSION
    recents = cfg.get_recent_folders()
    assert len(recents) > 0
    assert recents[0][1] == 2
    assert cfg.get_window_rect() == (9, 9, 9, 9)


def test_splitter_positions_are_clamped(tmp_path: Path) -> None:
    cfg_path = tmp_path / "user_config.json"
    cfg = UserConfig.load(config_path=cfg_path)

    cfg.set_home_splitter_positions(-10.0, 200.0)
    file_plot, plot_event = cfg.get_home_splitter_positions()

    assert file_plot == HOME_FILE_PLOT_SPLITTER_RANGE[0]
    assert plot_event == HOME_PLOT_EVENT_SPLITTER_RANGE[1]


def test_ensure_exists(tmp_path: Path) -> None:
    """Test UserConfig.ensure_exists() method."""
    cfg_path = tmp_path / "user_config.json"
    assert not cfg_path.exists()
    
    cfg = UserConfig.load(config_path=cfg_path)
    cfg.set_window_rect(10, 20, 30, 40)
    cfg.ensure_exists()
    
    assert cfg_path.exists()
    # Verify file was written with current data
    cfg2 = UserConfig.load(config_path=cfg_path)
    assert cfg2.get_window_rect() == (10, 20, 30, 40)


def test_prune_missing_folders(tmp_path: Path) -> None:
    """Test UserConfig.prune_missing_folders() method."""
    cfg_path = tmp_path / "user_config.json"
    cfg = UserConfig.load(config_path=cfg_path)
    
    # Add existing folder
    existing_folder = tmp_path / "existing"
    existing_folder.mkdir()
    cfg.push_recent_path(existing_folder, depth=1)
    
    # Add non-existent folder
    cfg.push_recent_path("/tmp/nonexistent_folder_12345", depth=2)
    cfg.set_last_path("/tmp/another_nonexistent_67890", depth=3)
    
    assert len(cfg.get_recent_folders()) == 2
    
    # Prune missing folders
    removed = cfg.prune_missing_folders()
    assert removed >= 1  # At least one folder should be removed
    
    recents = cfg.get_recent_folders()
    # Existing folder should remain
    assert len(recents) == 1
    assert str(existing_folder.resolve(strict=False)) in recents[0][0]
    
    # Last path should be cleared if it was missing
    last_path, _ = cfg.get_last_path()
    if last_path:
        # If last path was missing, it should be empty now
        assert Path(last_path).exists() or last_path == ""


def test_default_config_path() -> None:
    """Test UserConfig.default_config_path() static method."""
    path = UserConfig.default_config_path(app_name="test_app", filename="test.json")
    
    assert path.name == "test.json"
    assert path.parent.exists()  # Directory should exist
    assert path.parent.is_dir()


def test_default_config_path_with_app_author() -> None:
    """Test UserConfig.default_config_path() with app_author parameter."""
    path = UserConfig.default_config_path(
        app_name="test_app", 
        filename="test.json",
        app_author="test_author"
    )
    
    assert path.name == "test.json"
    assert path.parent.exists()
    assert path.parent.is_dir()


def test_load_with_app_author() -> None:
    """Test UserConfig.load() with app_author parameter."""
    cfg = UserConfig.load(
        app_name="test_app",
        filename="test_config.json",
        app_author="test_author"
    )
    
    assert cfg.path.name == "test_config.json"
    # Path should be in author-specific directory
    assert "test_author" in str(cfg.path) or "test_app" in str(cfg.path)


def test_set_default_folder_depth(tmp_path: Path) -> None:
    """Test UserConfig.set_default_folder_depth() method."""
    cfg_path = tmp_path / "user_config.json"
    cfg = UserConfig.load(config_path=cfg_path)
    
    # Default should be DEFAULT_FOLDER_DEPTH
    assert cfg.get_depth_for_folder("/tmp/unknown") == DEFAULT_FOLDER_DEPTH
    
    # Set new default
    cfg.set_default_folder_depth(5)
    assert cfg.get_depth_for_folder("/tmp/unknown") == 5
    
    # Verify it persists after save/load
    cfg.save()
    cfg2 = UserConfig.load(config_path=cfg_path)
    assert cfg2.get_depth_for_folder("/tmp/unknown") == 5


def test_window_rect_edge_cases(tmp_path: Path) -> None:
    """Test UserConfig window_rect getter with edge cases."""
    cfg_path = tmp_path / "user_config.json"
    
    # Test with invalid window_rect in file
    payload = {
        "schema_version": SCHEMA_VERSION,
        "window_rect": [1, 2],  # Invalid: not 4 elements
    }
    cfg_path.write_text(json.dumps(payload), encoding="utf-8")
    
    cfg = UserConfig.load(config_path=cfg_path)
    rect = cfg.get_window_rect()
    assert rect == tuple(DEFAULT_WINDOW_RECT)  # Should fall back to defaults
    
    # Test with non-integer values
    payload2 = {
        "schema_version": SCHEMA_VERSION,
        "window_rect": ["a", "b", "c", "d"],  # Invalid: not integers
    }
    cfg_path.write_text(json.dumps(payload2), encoding="utf-8")
    
    cfg2 = UserConfig.load(config_path=cfg_path)
    rect2 = cfg2.get_window_rect()
    assert rect2 == tuple(DEFAULT_WINDOW_RECT)  # Should fall back to defaults


def test_home_splitter_getter_setter(tmp_path: Path) -> None:
    """Test get_home_splitter_positions() and set_home_splitter_positions() comprehensively."""
    cfg_path = tmp_path / "user_config.json"
    cfg = UserConfig.load(config_path=cfg_path)
    
    # Test default values
    file_plot, plot_event = cfg.get_home_splitter_positions()
    assert file_plot == DEFAULT_HOME_FILE_PLOT_SPLITTER
    assert plot_event == DEFAULT_HOME_PLOT_EVENT_SPLITTER
    
    # Test setting valid values
    cfg.set_home_splitter_positions(20.0, 60.0)
    file_plot2, plot_event2 = cfg.get_home_splitter_positions()
    assert file_plot2 == 20.0
    assert plot_event2 == 60.0
    
    # Test persistence
    cfg.save()
    cfg2 = UserConfig.load(config_path=cfg_path)
    file_plot3, plot_event3 = cfg2.get_home_splitter_positions()
    assert file_plot3 == 20.0
    assert plot_event3 == 60.0


def test_push_recent_path_with_file(tmp_path: Path) -> None:
    """Test push_recent_path() with file paths."""
    cfg_path = tmp_path / "user_config.json"
    cfg = UserConfig.load(config_path=cfg_path)
    
    # Create a test file
    test_file = tmp_path / "test.tif"
    test_file.touch()
    
    # Push file path (depth should be ignored, stored as 0)
    cfg.push_recent_path(test_file, depth=5)
    
    # File should be in recent_files, not recent_folders
    files = cfg.get_recent_files()
    assert len(files) == 1
    assert str(test_file.resolve(strict=False)) in files[0]
    
    folders = cfg.get_recent_folders()
    assert len(folders) == 0
    
    # last_path should have depth=0 for files
    last_path, last_depth = cfg.get_last_path()
    assert last_path == str(test_file.resolve(strict=False))
    assert last_depth == 0


def test_push_recent_path_with_folder(tmp_path: Path) -> None:
    """Test push_recent_path() with folder paths."""
    cfg_path = tmp_path / "user_config.json"
    cfg = UserConfig.load(config_path=cfg_path)
    
    # Create a test folder
    test_folder = tmp_path / "test_folder"
    test_folder.mkdir()
    
    # Push folder path with depth
    cfg.push_recent_path(test_folder, depth=3)
    
    # Folder should be in recent_folders, not recent_files
    folders = cfg.get_recent_folders()
    assert len(folders) == 1
    assert str(test_folder.resolve(strict=False)) in folders[0][0]
    assert folders[0][1] == 3
    
    files = cfg.get_recent_files()
    assert len(files) == 0
    
    # last_path should have the depth
    last_path, last_depth = cfg.get_last_path()
    assert last_path == str(test_folder.resolve(strict=False))
    assert last_depth == 3


def test_get_recent_files(tmp_path: Path) -> None:
    """Test get_recent_files() method."""
    cfg_path = tmp_path / "user_config.json"
    cfg = UserConfig.load(config_path=cfg_path)
    
    # Create test files
    file1 = tmp_path / "file1.tif"
    file2 = tmp_path / "file2.tif"
    file1.touch()
    file2.touch()
    
    cfg.push_recent_path(file1, depth=0)
    cfg.push_recent_path(file2, depth=0)
    
    files = cfg.get_recent_files()
    assert len(files) == 2
    # Most recent first - file2 was added last, so it should be first
    assert files[0] == str(file2.resolve(strict=False))
    assert files[1] == str(file1.resolve(strict=False))


def test_path_existence_validation_on_load(tmp_path: Path) -> None:
    """Test that missing paths are removed during load."""
    cfg_path = tmp_path / "user_config.json"
    
    # Create existing folder and file
    existing_folder = tmp_path / "existing_folder"
    existing_folder.mkdir()
    existing_file = tmp_path / "existing_file.tif"
    existing_file.touch()
    
    # Create config with both existing and missing paths
    payload = {
        "schema_version": SCHEMA_VERSION,
        "recent_folders": [
            {"path": str(existing_folder), "depth": 1},
            {"path": "/tmp/nonexistent_folder_12345", "depth": 2},
        ],
        "recent_files": [
            {"path": str(existing_file)},
            {"path": "/tmp/nonexistent_file_67890.tif"},
        ],
        "last_path": {"path": str(existing_folder), "depth": 1},
    }
    cfg_path.write_text(json.dumps(payload), encoding="utf-8")
    
    # Load config - missing paths should be removed
    cfg = UserConfig.load(config_path=cfg_path)
    
    folders = cfg.get_recent_folders()
    assert len(folders) == 1
    assert str(existing_folder.resolve(strict=False)) in folders[0][0]
    
    files = cfg.get_recent_files()
    assert len(files) == 1
    assert str(existing_file.resolve(strict=False)) in files[0]
    
    # last_path should still be valid
    last_path, _ = cfg.get_last_path()
    assert str(existing_folder.resolve(strict=False)) in last_path


def test_push_recent_path_removes_duplicates(tmp_path: Path) -> None:
    """Test that push_recent_path removes duplicates from both lists."""
    cfg_path = tmp_path / "user_config.json"
    cfg = UserConfig.load(config_path=cfg_path)
    
    test_folder = tmp_path / "test_folder"
    test_folder.mkdir()
    test_file = tmp_path / "test_file.tif"
    test_file.touch()
    
    # Add folder, then add file
    cfg.push_recent_path(test_folder, depth=2)
    cfg.push_recent_path(test_file, depth=0)
    
    assert len(cfg.get_recent_folders()) == 1
    assert len(cfg.get_recent_files()) == 1
    
    # Re-add folder - should move to front and remove from files if it was there
    cfg.push_recent_path(test_folder, depth=3)
    
    folders = cfg.get_recent_folders()
    assert len(folders) == 1
    assert folders[0][1] == 3
    
    files = cfg.get_recent_files()
    assert len(files) == 1  # File should still be there
    
    # Re-add file - should move to front
    cfg.push_recent_path(test_file, depth=0)
    
    files2 = cfg.get_recent_files()
    assert len(files2) == 1
    assert str(test_file.resolve(strict=False)) in files2[0]


def test_max_recents_limit_combined(tmp_path: Path) -> None:
    """Test that MAX_RECENTS limit applies to combined folders + files."""
    cfg_path = tmp_path / "user_config.json"
    cfg = UserConfig.load(config_path=cfg_path)
    
    # Create test folders and files
    for i in range(10):
        folder = tmp_path / f"folder_{i}"
        folder.mkdir()
        cfg.push_recent_path(folder, depth=1)
    
    for i in range(10):
        file = tmp_path / f"file_{i}.tif"
        file.touch()
        cfg.push_recent_path(file, depth=0)
    
    # Should be limited to MAX_RECENTS (15) total
    folders = cfg.get_recent_folders()
    files = cfg.get_recent_files()
    assert len(folders) + len(files) <= 15


def test_clear_recent_paths(tmp_path: Path) -> None:
    """Test clear_recent_paths() method clears all paths and resets last_path."""
    cfg_path = tmp_path / "user_config.json"
    cfg = UserConfig.load(config_path=cfg_path)
    
    # Create test folders and files
    test_folder = tmp_path / "test_folder"
    test_folder.mkdir()
    test_file = tmp_path / "test_file.tif"
    test_file.touch()
    
    # Add paths
    cfg.push_recent_path(test_folder, depth=2)
    cfg.push_recent_path(test_file, depth=0)
    cfg.set_last_path(test_folder, depth=2)
    
    # Verify paths exist
    assert len(cfg.get_recent_folders()) == 1
    assert len(cfg.get_recent_files()) == 1
    last_path, last_depth = cfg.get_last_path()
    assert last_path == str(test_folder.resolve(strict=False))
    assert last_depth == 2
    
    # Clear all paths
    cfg.clear_recent_paths()
    
    # Verify everything is cleared
    assert len(cfg.get_recent_folders()) == 0
    assert len(cfg.get_recent_files()) == 0
    last_path_after, last_depth_after = cfg.get_last_path()
    assert last_path_after == ""
    assert last_depth_after == DEFAULT_FOLDER_DEPTH
    
    # Verify persistence
    cfg.save()
    cfg2 = UserConfig.load(config_path=cfg_path)
    assert len(cfg2.get_recent_folders()) == 0
    assert len(cfg2.get_recent_files()) == 0
    last_path2, last_depth2 = cfg2.get_last_path()
    assert last_path2 == ""
    assert last_depth2 == DEFAULT_FOLDER_DEPTH


# ============================================================================
# CSV-related tests
# ============================================================================

def test_push_recent_csv(tmp_path: Path) -> None:
    """Test push_recent_csv() method adds CSV to recent_csvs and sets last_path."""
    cfg_path = tmp_path / "user_config.json"
    cfg = UserConfig.load(config_path=cfg_path)
    
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("path\n/file1.tif\n/file2.tif")
    
    # Verify initial state
    assert len(cfg.get_recent_csvs()) == 0, "Should start with empty CSV list"
    
    # Get normalized path (what push_recent_csv will use)
    from kymflow.core.user_config import _normalize_folder_path
    normalized_path = _normalize_folder_path(csv_file)
    
    cfg.push_recent_csv(csv_file)
    
    # Verify CSV is in recent_csvs (check in-memory, no save needed)
    csvs = cfg.get_recent_csvs()
    assert len(csvs) == 1, f"Expected 1 CSV, got {len(csvs)}: {csvs}. Data.recent_csvs: {cfg.data.recent_csvs}"
    # Use normalized path for comparison (push_recent_csv normalizes the path)
    assert csvs[0] == normalized_path, f"Expected {normalized_path}, got {csvs[0]}"
    
    # Verify last_path is set to CSV
    last_path, last_depth = cfg.get_last_path()
    assert last_path == normalized_path, f"Expected {normalized_path}, got {last_path}"
    assert last_depth == 0  # CSVs use depth=0 (like files)


def test_get_recent_csvs(tmp_path: Path) -> None:
    """Test get_recent_csvs() returns list of CSV paths."""
    cfg_path = tmp_path / "user_config.json"
    cfg = UserConfig.load(config_path=cfg_path)
    
    csv1 = tmp_path / "csv1.csv"
    csv2 = tmp_path / "csv2.csv"
    csv1.write_text("path\n/file1.tif")
    csv2.write_text("path\n/file2.tif")
    
    cfg.push_recent_csv(csv1)
    cfg.push_recent_csv(csv2)
    
    csvs = cfg.get_recent_csvs()
    assert len(csvs) == 2
    # Most recent first
    assert csvs[0] == str(csv2.resolve(strict=False))
    assert csvs[1] == str(csv1.resolve(strict=False))


def test_push_recent_path_detects_csv(tmp_path: Path) -> None:
    """Test push_recent_path() detects CSV and routes to recent_csvs."""
    cfg_path = tmp_path / "user_config.json"
    cfg = UserConfig.load(config_path=cfg_path)
    
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("path\n/file1.tif")
    tif_file = tmp_path / "test.tif"
    tif_file.touch()
    
    # Push CSV - should go to recent_csvs, not recent_files
    cfg.push_recent_path(csv_file, depth=0)
    csvs = cfg.get_recent_csvs()
    files = cfg.get_recent_files()
    assert len(csvs) == 1
    assert len(files) == 0
    assert csvs[0] == str(csv_file.resolve(strict=False))
    
    # Push TIF - should go to recent_files, not recent_csvs
    cfg.push_recent_path(tif_file, depth=0)
    csvs = cfg.get_recent_csvs()
    files = cfg.get_recent_files()
    assert len(csvs) == 1  # Still 1 CSV
    assert len(files) == 1
    assert files[0] == str(tif_file.resolve(strict=False))


def test_prune_missing_csvs(tmp_path: Path) -> None:
    """Test prune_missing_folders() removes non-existent CSVs."""
    cfg_path = tmp_path / "user_config.json"
    cfg = UserConfig.load(config_path=cfg_path)
    
    csv1 = tmp_path / "csv1.csv"
    csv2 = tmp_path / "csv2.csv"
    csv1.write_text("path\n/file1.tif")
    csv2.write_text("path\n/file2.tif")
    
    cfg.push_recent_csv(csv1)
    cfg.push_recent_csv(csv2)
    
    # Delete one CSV
    csv2.unlink()
    
    # Prune missing paths (method is still called prune_missing_folders but handles CSVs too)
    cfg.prune_missing_folders()
    
    csvs = cfg.get_recent_csvs()
    assert len(csvs) == 1
    assert csvs[0] == str(csv1.resolve(strict=False))


def test_user_config_loads_csvs_from_json(tmp_path: Path) -> None:
    """Test UserConfig loads recent_csvs from JSON (backward compatibility)."""
    cfg_path = tmp_path / "user_config.json"
    
    # Create JSON with recent_csvs
    csv1 = tmp_path / "csv1.csv"
    csv2 = tmp_path / "csv2.csv"
    csv1.write_text("path\n/file1.tif")
    csv2.write_text("path\n/file2.tif")
    
    csv1_path = str(csv1.resolve(strict=False))
    csv2_path = str(csv2.resolve(strict=False))
    
    # last_path must be a dict with path and depth keys (not a string)
    config_data = {
        "schema_version": SCHEMA_VERSION,
        "recent_folders": [],
        "recent_files": [],
        "recent_csvs": [
            {"path": csv1_path},
            {"path": csv2_path},
        ],
        "last_path": {"path": csv2_path, "depth": DEFAULT_FOLDER_DEPTH},
    }
    cfg_path.write_text(json.dumps(config_data), encoding="utf-8")
    
    cfg = UserConfig.load(config_path=cfg_path)
    csvs = cfg.get_recent_csvs()
    assert len(csvs) == 2
    # Order is preserved from JSON (csv1 first, csv2 second)
    # Note: last_path doesn't affect the order of recent_csvs when loading from JSON
    assert csvs[0] == csv1_path
    assert csvs[1] == csv2_path
    # But last_path should be set to csv2
    last_path, _ = cfg.get_last_path()
    assert last_path == csv2_path


def test_recent_csvs_max_limit(tmp_path: Path) -> None:
    """Test that recent_csvs respects MAX_RECENTS limit (combined with folders/files)."""
    cfg_path = tmp_path / "user_config.json"
    cfg = UserConfig.load(config_path=cfg_path)
    
    # Add many folders, files, and CSVs
    for i in range(10):
        folder = tmp_path / f"folder_{i}"
        folder.mkdir()
        cfg.push_recent_path(folder, depth=1)
    
    for i in range(5):
        file = tmp_path / f"file_{i}.tif"
        file.touch()
        cfg.push_recent_path(file, depth=0)
    
    for i in range(5):
        csv = tmp_path / f"csv_{i}.csv"
        csv.write_text("path\n/file.tif")
        cfg.push_recent_csv(csv)
    
    # Should be limited to MAX_RECENTS (15) total
    folders = cfg.get_recent_folders()
    files = cfg.get_recent_files()
    csvs = cfg.get_recent_csvs()
    assert len(folders) + len(files) + len(csvs) <= 15


def test_user_config_blinded_defaults_to_false(tmp_path: Path) -> None:
    """Test that blinded defaults to False when not set."""
    cfg_path = tmp_path / "user_config.json"
    cfg = UserConfig.load(config_path=cfg_path)
    
    assert cfg.get_blinded() is False
    assert cfg.data.blinded is False


def test_user_config_blinded_getter_setter(tmp_path: Path) -> None:
    """Test blinded getter and setter methods."""
    cfg_path = tmp_path / "user_config.json"
    cfg = UserConfig.load(config_path=cfg_path)
    
    # Default should be False
    assert cfg.get_blinded() is False
    
    # Set to True
    cfg.set_blinded(True)
    assert cfg.get_blinded() is True
    assert cfg.data.blinded is True
    
    # Set back to False
    cfg.set_blinded(False)
    assert cfg.get_blinded() is False
    assert cfg.data.blinded is False


def test_user_config_blinded_persists(tmp_path: Path) -> None:
    """Test that blinded setting persists across save/load."""
    cfg_path = tmp_path / "user_config.json"
    cfg = UserConfig.load(config_path=cfg_path)
    
    # Set blinded to True
    cfg.set_blinded(True)
    cfg.save()
    
    # Reload and verify
    cfg2 = UserConfig.load(config_path=cfg_path)
    assert cfg2.get_blinded() is True
    
    # Set to False and verify
    cfg2.set_blinded(False)
    cfg2.save()
    
    cfg3 = UserConfig.load(config_path=cfg_path)
    assert cfg3.get_blinded() is False


def test_user_config_blinded_backward_compatible(tmp_path: Path) -> None:
    """Test that old config files without blinded field default to False."""
    cfg_path = tmp_path / "user_config.json"
    
    # Create a config file with schema v2 (no blinded field)
    old_config = {
        "schema_version": 2,
        "recent_folders": [],
        "recent_files": [],
        "recent_csvs": [],
        "last_path": {"path": "", "depth": 1},
        "window_rect": [100, 100, 1200, 800],
        "default_folder_depth": 1,
        "home_file_plot_splitter": 15.0,
        "home_plot_event_splitter": 50.0,
    }
    cfg_path.write_text(json.dumps(old_config), encoding="utf-8")
    
    # Load should default blinded to False
    cfg = UserConfig.load(config_path=cfg_path, schema_version=3, reset_on_version_mismatch=False)
    assert cfg.get_blinded() is False
