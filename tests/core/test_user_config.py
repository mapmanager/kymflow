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
    assert cfg.get_last_folder() == ("", DEFAULT_FOLDER_DEPTH)
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

    cfg.push_recent_folder("/tmp/a", depth=2)
    cfg.push_recent_folder("/tmp/b", depth=3)
    cfg.set_window_rect(1, 2, 3, 4)
    cfg.set_home_splitter_positions(12.5, 61.0)
    cfg.save()

    cfg2 = UserConfig.load(config_path=cfg_path)
    assert cfg2.get_last_folder() == (str(Path("/tmp/b").resolve(strict=False)), 3)
    recents = cfg2.get_recent_folders()
    assert len(recents) == 2
    assert recents[0][1] == 3
    assert recents[1][1] == 2
    assert cfg2.get_window_rect() == (1, 2, 3, 4)
    assert cfg2.get_home_splitter_positions() == (12.5, 61.0)


def test_push_recent_moves_to_front_and_updates_depth(tmp_path: Path) -> None:
    cfg_path = tmp_path / "user_config.json"
    cfg = UserConfig.load(config_path=cfg_path)

    cfg.push_recent_folder("/tmp/a", depth=2)
    cfg.push_recent_folder("/tmp/b", depth=3)
    cfg.push_recent_folder("/tmp/a", depth=5)  # move to front + update depth

    recents = cfg.get_recent_folders()
    assert recents[0][0] == str(Path("/tmp/a").resolve(strict=False))
    assert recents[0][1] == 5
    assert recents[1][0] == str(Path("/tmp/b").resolve(strict=False))
    assert recents[1][1] == 3

    assert cfg.get_last_folder() == (str(Path("/tmp/a").resolve(strict=False)), 5)


def test_set_last_folder_does_not_reorder_recents(tmp_path: Path) -> None:
    cfg_path = tmp_path / "user_config.json"
    cfg = UserConfig.load(config_path=cfg_path)

    cfg.push_recent_folder("/tmp/a", depth=2)
    cfg.push_recent_folder("/tmp/b", depth=3)
    cfg.set_last_folder("/tmp/a", depth=9)

    recents = cfg.get_recent_folders()
    assert recents[0][0] == str(Path("/tmp/b").resolve(strict=False))
    assert recents[1][0] == str(Path("/tmp/a").resolve(strict=False))
    assert cfg.get_last_folder() == (str(Path("/tmp/a").resolve(strict=False)), 9)


def test_get_depth_for_folder_falls_back_to_default(tmp_path: Path) -> None:
    cfg_path = tmp_path / "user_config.json"
    cfg = UserConfig.load(config_path=cfg_path)

    assert cfg.get_depth_for_folder("/tmp/never_seen") == DEFAULT_FOLDER_DEPTH
    cfg.set_default_folder_depth(7)
    assert cfg.get_depth_for_folder("/tmp/never_seen") == 7

    cfg.push_recent_folder("/tmp/a", depth=2)
    assert cfg.get_depth_for_folder("/tmp/a") == 2


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
    assert cfg.get_last_folder() == ("", DEFAULT_FOLDER_DEPTH)
    assert cfg.get_window_rect() == tuple(DEFAULT_WINDOW_RECT)


def test_schema_mismatch_without_reset_keeps_data_but_updates_version(tmp_path: Path) -> None:
    cfg_path = tmp_path / "user_config.json"

    payload = {
        "schema_version": 999,
        "recent_folders": [{"path": "/tmp/a", "depth": 2}],
        "last_folder": {"path": "/tmp/a", "depth": 2},
        "window_rect": [9, 9, 9, 9],
        "default_folder_depth": 4,
    }
    cfg_path.write_text(json.dumps(payload), encoding="utf-8")

    cfg = UserConfig.load(config_path=cfg_path, schema_version=SCHEMA_VERSION, reset_on_version_mismatch=False)
    assert cfg.data.schema_version == SCHEMA_VERSION
    assert cfg.get_recent_folders()[0][1] == 2
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
    cfg.push_recent_folder(existing_folder, depth=1)
    
    # Add non-existent folder
    cfg.push_recent_folder("/tmp/nonexistent_folder_12345", depth=2)
    cfg.set_last_folder("/tmp/another_nonexistent_67890", depth=3)
    
    assert len(cfg.get_recent_folders()) == 2
    
    # Prune missing folders
    removed = cfg.prune_missing_folders()
    assert removed >= 1  # At least one folder should be removed
    
    recents = cfg.get_recent_folders()
    # Existing folder should remain
    assert len(recents) == 1
    assert str(existing_folder.resolve(strict=False)) in recents[0][0]
    
    # Last folder should be cleared if it was missing
    last_path, _ = cfg.get_last_folder()
    if last_path:
        # If last folder was missing, it should be empty now
        assert Path(last_path).exists() or last_path == ""


def test_default_config_path() -> None:
    """Test UserConfig.default_config_path() static method."""
    path = UserConfig.default_config_path(app_name="test_app", filename="test.json")
    
    assert path.name == "test.json"
    assert path.parent.exists()  # Directory should exist
    assert path.parent.is_dir()


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
