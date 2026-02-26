"""Tests for about.py getVersionInfo function."""

from __future__ import annotations

from kymflow.core.utils.about import getVersionInfo


def test_getversioninfo_returns_dict() -> None:
    """Test that getVersionInfo returns a dictionary."""
    info = getVersionInfo()
    assert isinstance(info, dict)




def test_getversioninfo_github_url() -> None:
    """Test that GitHub URL is not present (removed from API)."""
    info = getVersionInfo()
    # GitHub key was removed from getVersionInfo()
    assert "GitHub" not in info



def test_getversioninfo_user_config_path() -> None:
    """Test that User Config path is a valid string path."""
    info = getVersionInfo()
    user_config = info["User Config"]
    assert isinstance(user_config, str)
    assert len(user_config) > 0


