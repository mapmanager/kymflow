"""Tests for about.py getVersionInfo function."""

from __future__ import annotations

from kymflow.core.utils.about import getVersionInfo


def test_getversioninfo_returns_dict() -> None:
    """Test that getVersionInfo returns a dictionary."""
    info = getVersionInfo()
    assert isinstance(info, dict)


def test_getversioninfo_has_required_keys() -> None:
    """Test that getVersionInfo returns expected keys."""
    info = getVersionInfo()
    
    required_keys = [
        "KymFlow Core version",
        "KymFlow GUI version",
        "Python version",
        "Python platform",
        "NiceGUI version",
        "User Config",
        "Log file",
        "email",
    ]
    
    for key in required_keys:
        assert key in info, f"Missing key: {key}"


def test_getversioninfo_values_are_strings() -> None:
    """Test that all values in getVersionInfo are strings."""
    info = getVersionInfo()
    
    for key, value in info.items():
        assert isinstance(value, str), f"Value for {key} is not a string: {type(value)}"


def test_getversioninfo_github_url() -> None:
    """Test that GitHub URL is not present (removed from API)."""
    info = getVersionInfo()
    # GitHub key was removed from getVersionInfo()
    assert "GitHub" not in info


def test_getversioninfo_email() -> None:
    """Test that email is correct."""
    info = getVersionInfo()
    assert info["email"] == "robert.cudmore@gmail.com"


def test_getversioninfo_gui_version_placeholder() -> None:
    """Test that GUI version shows placeholder when not imported."""
    info = getVersionInfo()
    assert "N/A" in info["KymFlow GUI version"]
    assert "N/A" in info["NiceGUI version"]


def test_getversioninfo_python_version_format() -> None:
    """Test that Python version is in expected format (e.g., '3.11.0')."""
    info = getVersionInfo()
    python_version = info["Python version"]
    # Should be in format like "3.11.0" or "3.12.1"
    parts = python_version.split(".")
    assert len(parts) >= 2
    assert all(part.isdigit() for part in parts)


def test_getversioninfo_user_config_path() -> None:
    """Test that User Config path is a valid string path."""
    info = getVersionInfo()
    user_config = info["User Config"]
    assert isinstance(user_config, str)
    assert len(user_config) > 0


def test_getversioninfo_log_file_path() -> None:
    """Test that Log file path is a valid string path."""
    info = getVersionInfo()
    log_file = info["Log file"]
    assert isinstance(log_file, str)
    # May be empty string if logging not initialized, but should be a string
    assert isinstance(log_file, str)
