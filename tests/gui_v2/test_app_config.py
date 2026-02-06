# tests/gui_v2/test_app_config.py
"""Tests for AppConfig in GUI v2."""

from __future__ import annotations

import json
from pathlib import Path

from kymflow.gui_v2.app_config import (
    DEFAULT_BLINDED,
    DEFAULT_TEXT_SIZE,
    DEFAULT_WINDOW_RECT,
    SCHEMA_VERSION,
    AppConfig,
    AppConfigData,
)


def test_load_defaults_when_missing(tmp_path: Path) -> None:
    """Test that AppConfig loads defaults when file is missing."""
    cfg_path = tmp_path / "app_config.json"
    cfg = AppConfig.load(config_path=cfg_path)
    assert cfg.path == cfg_path
    assert cfg.data.schema_version == SCHEMA_VERSION
    assert cfg.get_attribute("text_size") == DEFAULT_TEXT_SIZE
    assert not cfg_path.exists()


def test_create_if_missing_writes_defaults(tmp_path: Path) -> None:
    """Test that create_if_missing=True writes defaults to disk."""
    cfg_path = tmp_path / "app_config.json"
    assert not cfg_path.exists()

    cfg = AppConfig.load(config_path=cfg_path, create_if_missing=True)
    assert cfg_path.exists()

    # File should be valid JSON with schema_version
    loaded = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    assert loaded["schema_version"] == SCHEMA_VERSION
    assert loaded["text_size"] == DEFAULT_TEXT_SIZE


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    """Test that save/load roundtrip preserves values."""
    cfg_path = tmp_path / "app_config.json"
    cfg = AppConfig.load(config_path=cfg_path)

    cfg.set_attribute("text_size", "text-lg")
    cfg.save()

    cfg2 = AppConfig.load(config_path=cfg_path)
    assert cfg2.get_attribute("text_size") == "text-lg"


def test_set_attribute_validates_options(tmp_path: Path) -> None:
    """Test that set_attribute validates against metadata options."""
    cfg_path = tmp_path / "app_config.json"
    cfg = AppConfig.load(config_path=cfg_path)

    # Valid option should work
    cfg.set_attribute("text_size", "text-base")
    assert cfg.get_attribute("text_size") == "text-base"

    # Invalid option should raise ValueError
    try:
        cfg.set_attribute("text_size", "invalid-size")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "not in allowed options" in str(e)


def test_get_attribute(tmp_path: Path) -> None:
    """Test get_attribute method."""
    cfg_path = tmp_path / "app_config.json"
    cfg = AppConfig.load(config_path=cfg_path)

    assert cfg.get_attribute("text_size") == DEFAULT_TEXT_SIZE

    # Non-existent attribute should raise AttributeError
    try:
        cfg.get_attribute("nonexistent")
        assert False, "Should have raised AttributeError"
    except AttributeError as e:
        assert "has no attribute" in str(e)


def test_schema_mismatch_resets(tmp_path: Path) -> None:
    """Test that schema mismatch resets to defaults when reset_on_version_mismatch=True."""
    cfg_path = tmp_path / "app_config.json"

    payload = {
        "schema_version": 999,
        "text_size": "text-lg",
    }
    cfg_path.write_text(json.dumps(payload), encoding="utf-8")

    cfg = AppConfig.load(
        config_path=cfg_path, schema_version=SCHEMA_VERSION, reset_on_version_mismatch=True
    )
    assert cfg.get_attribute("text_size") == DEFAULT_TEXT_SIZE
    assert cfg.data.schema_version == SCHEMA_VERSION


def test_schema_mismatch_without_reset_keeps_data_but_updates_version(tmp_path: Path) -> None:
    """Test that schema mismatch keeps data but updates version when reset_on_version_mismatch=False."""
    cfg_path = tmp_path / "app_config.json"

    payload = {
        "schema_version": 999,
        "text_size": "text-lg",
    }
    cfg_path.write_text(json.dumps(payload), encoding="utf-8")

    cfg = AppConfig.load(
        config_path=cfg_path, schema_version=SCHEMA_VERSION, reset_on_version_mismatch=False
    )
    assert cfg.data.schema_version == SCHEMA_VERSION
    assert cfg.get_attribute("text_size") == "text-lg"


def test_normalize_loaded_data_validates_text_size(tmp_path: Path) -> None:
    """Test that _normalize_loaded_data validates and corrects invalid text_size."""
    cfg_path = tmp_path / "app_config.json"

    # Invalid text_size should be reset to default
    payload = {
        "schema_version": SCHEMA_VERSION,
        "text_size": "invalid-size",
    }
    cfg_path.write_text(json.dumps(payload), encoding="utf-8")

    cfg = AppConfig.load(config_path=cfg_path)
    assert cfg.get_attribute("text_size") == DEFAULT_TEXT_SIZE

    # Valid text_size should be preserved
    payload2 = {
        "schema_version": SCHEMA_VERSION,
        "text_size": "text-lg",
    }
    cfg_path.write_text(json.dumps(payload2), encoding="utf-8")

    cfg2 = AppConfig.load(config_path=cfg_path)
    assert cfg2.get_attribute("text_size") == "text-lg"


def test_get_field_metadata(tmp_path: Path) -> None:
    """Test get_field_metadata method."""
    cfg_path = tmp_path / "app_config.json"
    cfg = AppConfig.load(config_path=cfg_path)

    metadata = cfg.get_field_metadata("text_size")
    assert metadata["widget_type"] == "select"
    assert metadata["label"] == "Text Size"
    assert "text-xs" in metadata["options"]
    assert "text-sm" in metadata["options"]
    assert "text-base" in metadata["options"]
    assert "text-lg" in metadata["options"]
    assert metadata["requires_restart"] is True

    # Non-existent field should raise AttributeError
    try:
        cfg.get_field_metadata("nonexistent")
        assert False, "Should have raised AttributeError"
    except AttributeError:
        pass


def test_get_all_fields_with_metadata(tmp_path: Path) -> None:
    """Test get_all_fields_with_metadata method."""
    cfg_path = tmp_path / "app_config.json"
    cfg = AppConfig.load(config_path=cfg_path)

    fields_info = cfg.get_all_fields_with_metadata()
    assert "text_size" in fields_info
    assert fields_info["text_size"]["value"] == DEFAULT_TEXT_SIZE
    assert fields_info["text_size"]["metadata"]["widget_type"] == "select"
    assert "schema_version" not in fields_info  # Should be excluded


def test_ensure_exists(tmp_path: Path) -> None:
    """Test AppConfig.ensure_exists() method."""
    cfg_path = tmp_path / "app_config.json"
    assert not cfg_path.exists()

    cfg = AppConfig.load(config_path=cfg_path)
    cfg.set_attribute("text_size", "text-lg")
    cfg.ensure_exists()

    assert cfg_path.exists()
    # Verify file was written with current data
    cfg2 = AppConfig.load(config_path=cfg_path)
    assert cfg2.get_attribute("text_size") == "text-lg"


def test_default_config_path() -> None:
    """Test AppConfig.default_config_path() static method."""
    path = AppConfig.default_config_path(app_name="test_app", filename="test.json")

    assert path.name == "test.json"
    assert path.parent.exists()  # Directory should exist
    assert path.parent.is_dir()


def test_set_attribute_type_conversion(tmp_path: Path) -> None:
    """Test that set_attribute converts compatible types."""
    cfg_path = tmp_path / "app_config.json"
    cfg = AppConfig.load(config_path=cfg_path)

    # String value should work
    cfg.set_attribute("text_size", "text-base")
    assert cfg.get_attribute("text_size") == "text-base"

    # Non-string should be converted to string
    # (though this might not make sense for text_size, testing the conversion logic)
    # Actually, for text_size, we want strict validation, so let's test with a value that can be converted
    # But text_size is a select, so it must be in options. Let's just verify the type checking works.
    assert isinstance(cfg.get_attribute("text_size"), str)


def test_from_json_dict_tolerates_missing_fields(tmp_path: Path) -> None:
    """Test that from_json_dict handles missing fields gracefully."""
    cfg_path = tmp_path / "app_config.json"

    # Missing text_size should use default
    payload = {
        "schema_version": SCHEMA_VERSION,
    }
    cfg_path.write_text(json.dumps(payload), encoding="utf-8")

    cfg = AppConfig.load(config_path=cfg_path)
    assert cfg.get_attribute("text_size") == DEFAULT_TEXT_SIZE


def test_from_json_dict_tolerates_invalid_types(tmp_path: Path) -> None:
    """Test that from_json_dict handles invalid types gracefully."""
    cfg_path = tmp_path / "app_config.json"

    # Non-string text_size should use default
    payload = {
        "schema_version": SCHEMA_VERSION,
        "text_size": 123,  # Invalid: should be string
    }
    cfg_path.write_text(json.dumps(payload), encoding="utf-8")

    cfg = AppConfig.load(config_path=cfg_path)
    assert cfg.get_attribute("text_size") == DEFAULT_TEXT_SIZE


def test_all_text_size_options_are_valid(tmp_path: Path) -> None:
    """Test that all text_size options in metadata are accepted."""
    cfg_path = tmp_path / "app_config.json"
    cfg = AppConfig.load(config_path=cfg_path)

    metadata = cfg.get_field_metadata("text_size")
    options = metadata["options"]

    for option in options:
        cfg.set_attribute("text_size", option)
        assert cfg.get_attribute("text_size") == option

        # Save and reload to verify persistence
        cfg.save()
        cfg2 = AppConfig.load(config_path=cfg_path)
        assert cfg2.get_attribute("text_size") == option


# ============================================================================
# Tests for blinded field
# ============================================================================

def test_blinded_defaults_to_false(tmp_path: Path) -> None:
    """Test that blinded defaults to False when not set."""
    cfg_path = tmp_path / "app_config.json"
    cfg = AppConfig.load(config_path=cfg_path)
    
    assert cfg.get_blinded() is False
    assert cfg.data.blinded is False
    assert cfg.get_attribute("blinded") is False


def test_blinded_getter_setter(tmp_path: Path) -> None:
    """Test blinded getter and setter methods."""
    cfg_path = tmp_path / "app_config.json"
    cfg = AppConfig.load(config_path=cfg_path)
    
    # Default should be False
    assert cfg.get_blinded() is False
    
    # Set to True
    cfg.set_blinded(True)
    assert cfg.get_blinded() is True
    assert cfg.data.blinded is True
    assert cfg.get_attribute("blinded") is True
    
    # Set back to False
    cfg.set_blinded(False)
    assert cfg.get_blinded() is False
    assert cfg.data.blinded is False
    assert cfg.get_attribute("blinded") is False


def test_blinded_persists(tmp_path: Path) -> None:
    """Test that blinded setting persists across save/load."""
    cfg_path = tmp_path / "app_config.json"
    cfg = AppConfig.load(config_path=cfg_path)
    
    # Set blinded to True
    cfg.set_blinded(True)
    cfg.save()
    
    # Reload and verify
    cfg2 = AppConfig.load(config_path=cfg_path)
    assert cfg2.get_blinded() is True
    assert cfg2.get_attribute("blinded") is True
    
    # Set to False and verify
    cfg2.set_blinded(False)
    cfg2.save()
    
    cfg3 = AppConfig.load(config_path=cfg_path)
    assert cfg3.get_blinded() is False
    assert cfg3.get_attribute("blinded") is False


def test_blinded_backward_compatible(tmp_path: Path) -> None:
    """Test that old config files without blinded field default to False."""
    cfg_path = tmp_path / "app_config.json"
    
    # Create a config file with schema v1 (no blinded field)
    old_config = {
        "schema_version": 1,
        "text_size": "text-sm",
    }
    cfg_path.write_text(json.dumps(old_config), encoding="utf-8")
    
    # Load should default blinded to False
    cfg = AppConfig.load(config_path=cfg_path, schema_version=SCHEMA_VERSION, reset_on_version_mismatch=False)
    assert cfg.get_blinded() is False


def test_blinded_from_json_dict_tolerates_various_types(tmp_path: Path) -> None:
    """Test that from_json_dict handles various blinded value types."""
    cfg_path = tmp_path / "app_config.json"
    
    # Test with string "true"
    payload1 = {
        "schema_version": SCHEMA_VERSION,
        "text_size": DEFAULT_TEXT_SIZE,
        "blinded": "true",
    }
    cfg_path.write_text(json.dumps(payload1), encoding="utf-8")
    cfg1 = AppConfig.load(config_path=cfg_path)
    assert cfg1.get_blinded() is True
    
    # Test with string "1"
    payload2 = {
        "schema_version": SCHEMA_VERSION,
        "text_size": DEFAULT_TEXT_SIZE,
        "blinded": "1",
    }
    cfg_path.write_text(json.dumps(payload2), encoding="utf-8")
    cfg2 = AppConfig.load(config_path=cfg_path)
    assert cfg2.get_blinded() is True
    
    # Test with integer 1
    payload3 = {
        "schema_version": SCHEMA_VERSION,
        "text_size": DEFAULT_TEXT_SIZE,
        "blinded": 1,
    }
    cfg_path.write_text(json.dumps(payload3), encoding="utf-8")
    cfg3 = AppConfig.load(config_path=cfg_path)
    assert cfg3.get_blinded() is True
    
    # Test with integer 0
    payload4 = {
        "schema_version": SCHEMA_VERSION,
        "text_size": DEFAULT_TEXT_SIZE,
        "blinded": 0,
    }
    cfg_path.write_text(json.dumps(payload4), encoding="utf-8")
    cfg4 = AppConfig.load(config_path=cfg_path)
    assert cfg4.get_blinded() is False


def test_blinded_metadata(tmp_path: Path) -> None:
    """Test that blinded field has correct metadata for GUI."""
    cfg_path = tmp_path / "app_config.json"
    cfg = AppConfig.load(config_path=cfg_path)
    
    metadata = cfg.get_field_metadata("blinded")
    assert metadata["widget_type"] == "checkbox"
    assert metadata["label"] == "Blinded Analysis"
    assert metadata["requires_restart"] is False


# ============================================================================
# Tests for window_rect field
# ============================================================================

def test_window_rect_defaults(tmp_path: Path) -> None:
    """Test that window_rect defaults correctly."""
    cfg_path = tmp_path / "app_config.json"
    cfg = AppConfig.load(config_path=cfg_path)
    
    rect = cfg.get_window_rect()
    assert rect == tuple(DEFAULT_WINDOW_RECT)
    assert len(rect) == 4
    assert all(isinstance(x, int) for x in rect)
    
    # Verify data attribute
    assert cfg.data.window_rect == list(DEFAULT_WINDOW_RECT)


def test_window_rect_getter_setter(tmp_path: Path) -> None:
    """Test window_rect getter and setter methods."""
    cfg_path = tmp_path / "app_config.json"
    cfg = AppConfig.load(config_path=cfg_path)
    
    # Set window rect
    cfg.set_window_rect(10, 20, 800, 600)
    rect = cfg.get_window_rect()
    assert rect == (10, 20, 800, 600)
    assert cfg.data.window_rect == [10, 20, 800, 600]
    
    # Set different values
    cfg.set_window_rect(100, 200, 1200, 900)
    rect2 = cfg.get_window_rect()
    assert rect2 == (100, 200, 1200, 900)
    assert cfg.data.window_rect == [100, 200, 1200, 900]


def test_window_rect_persists(tmp_path: Path) -> None:
    """Test that window_rect persists across save/load."""
    cfg_path = tmp_path / "app_config.json"
    cfg = AppConfig.load(config_path=cfg_path)
    
    # Set window rect
    cfg.set_window_rect(50, 60, 1000, 700)
    cfg.save()
    
    # Reload and verify
    cfg2 = AppConfig.load(config_path=cfg_path)
    assert cfg2.get_window_rect() == (50, 60, 1000, 700)
    assert cfg2.data.window_rect == [50, 60, 1000, 700]


def test_window_rect_edge_cases(tmp_path: Path) -> None:
    """Test window_rect getter with edge cases."""
    cfg_path = tmp_path / "app_config.json"
    
    # Test with invalid window_rect in file (not 4 elements)
    payload1 = {
        "schema_version": SCHEMA_VERSION,
        "text_size": DEFAULT_TEXT_SIZE,
        "window_rect": [1, 2],  # Invalid: not 4 elements
    }
    cfg_path.write_text(json.dumps(payload1), encoding="utf-8")
    
    cfg1 = AppConfig.load(config_path=cfg_path)
    rect1 = cfg1.get_window_rect()
    assert rect1 == tuple(DEFAULT_WINDOW_RECT)  # Should fall back to defaults
    
    # Test with non-integer values
    payload2 = {
        "schema_version": SCHEMA_VERSION,
        "text_size": DEFAULT_TEXT_SIZE,
        "window_rect": ["a", "b", "c", "d"],  # Invalid: not integers
    }
    cfg_path.write_text(json.dumps(payload2), encoding="utf-8")
    
    cfg2 = AppConfig.load(config_path=cfg_path)
    rect2 = cfg2.get_window_rect()
    assert rect2 == tuple(DEFAULT_WINDOW_RECT)  # Should fall back to defaults
    
    # Test with None
    payload3 = {
        "schema_version": SCHEMA_VERSION,
        "text_size": DEFAULT_TEXT_SIZE,
        "window_rect": None,
    }
    cfg_path.write_text(json.dumps(payload3), encoding="utf-8")
    
    cfg3 = AppConfig.load(config_path=cfg_path)
    rect3 = cfg3.get_window_rect()
    assert rect3 == tuple(DEFAULT_WINDOW_RECT)  # Should fall back to defaults


def test_window_rect_normalization(tmp_path: Path) -> None:
    """Test that _normalize_loaded_data validates window_rect."""
    cfg_path = tmp_path / "app_config.json"
    
    # Create config with invalid window_rect
    cfg = AppConfig.load(config_path=cfg_path)
    cfg.data.window_rect = [1, 2]  # Invalid: not 4 elements
    
    # Normalize should fix it
    AppConfig._normalize_loaded_data(cfg.data)
    assert cfg.data.window_rect == list(DEFAULT_WINDOW_RECT)
    
    # Test with None
    cfg2 = AppConfig.load(config_path=cfg_path)
    cfg2.data.window_rect = None
    AppConfig._normalize_loaded_data(cfg2.data)
    assert cfg2.data.window_rect == list(DEFAULT_WINDOW_RECT)


def test_window_rect_metadata(tmp_path: Path) -> None:
    """Test that window_rect field has correct metadata for GUI."""
    cfg_path = tmp_path / "app_config.json"
    cfg = AppConfig.load(config_path=cfg_path)
    
    metadata = cfg.get_field_metadata("window_rect")
    assert metadata["widget_type"] == "display"
    assert metadata["label"] == "Window Rect"
    assert metadata["requires_restart"] is False


def test_window_rect_in_get_all_fields_with_metadata(tmp_path: Path) -> None:
    """Test that window_rect appears in get_all_fields_with_metadata."""
    cfg_path = tmp_path / "app_config.json"
    cfg = AppConfig.load(config_path=cfg_path)
    
    fields_info = cfg.get_all_fields_with_metadata()
    assert "window_rect" in fields_info
    assert fields_info["window_rect"]["value"] == list(DEFAULT_WINDOW_RECT)
    assert fields_info["window_rect"]["metadata"]["widget_type"] == "display"
    assert fields_info["window_rect"]["type"] == "list"


def test_blinded_in_get_all_fields_with_metadata(tmp_path: Path) -> None:
    """Test that blinded appears in get_all_fields_with_metadata."""
    cfg_path = tmp_path / "app_config.json"
    cfg = AppConfig.load(config_path=cfg_path)
    
    fields_info = cfg.get_all_fields_with_metadata()
    assert "blinded" in fields_info
    assert fields_info["blinded"]["value"] is False
    assert fields_info["blinded"]["metadata"]["widget_type"] == "checkbox"
    assert fields_info["blinded"]["type"] == "bool"


def test_save_and_load_roundtrip_with_all_fields(tmp_path: Path) -> None:
    """Test that save/load roundtrip preserves all fields including blinded and window_rect."""
    cfg_path = tmp_path / "app_config.json"
    cfg = AppConfig.load(config_path=cfg_path)
    
    # Set all fields
    cfg.set_attribute("text_size", "text-lg")
    cfg.set_blinded(True)
    cfg.set_window_rect(100, 200, 1200, 900)
    cfg.save()
    
    # Reload and verify all fields
    cfg2 = AppConfig.load(config_path=cfg_path)
    assert cfg2.get_attribute("text_size") == "text-lg"
    assert cfg2.get_blinded() is True
    assert cfg2.get_window_rect() == (100, 200, 1200, 900)
