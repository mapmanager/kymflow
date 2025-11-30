"""Pytest configuration and fixtures for kymflow_gui tests."""

from __future__ import annotations

from pathlib import Path

import pytest

# Note: Parent conftest.py fixtures (like test_data_dir) are automatically available
# pytest_plugins is now defined in tests/conftest.py (top-level)


@pytest.fixture
def app_state(test_data_dir: Path) -> "AppState":
    """Fixture providing an AppState instance with test data loaded.
    
    Args:
        test_data_dir: Test data directory fixture from parent conftest
        
    Returns:
        AppState instance with test folder loaded
    """
    from kymflow_core.state import AppState
    
    app_state = AppState()
    if test_data_dir.exists():
        app_state.load_folder(test_data_dir)
    return app_state

