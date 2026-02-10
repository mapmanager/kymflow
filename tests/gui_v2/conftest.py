"""Pytest fixtures for GUI v2 tests."""

from __future__ import annotations

from typing import Generator
from unittest.mock import MagicMock

import pytest

from kymflow.gui_v2.state import AppState
from kymflow.gui_v2.bus import BusConfig, EventBus


@pytest.fixture
def bus() -> Generator[EventBus, None, None]:
    """Create an EventBus instance for testing.

    Yields:
        EventBus instance with trace enabled for test visibility.
    """
    # For tests, we create buses directly (not via get_event_bus)
    # to avoid needing NiceGUI client context
    test_bus = EventBus(client_id="test-client", config=BusConfig(trace=False))
    yield test_bus


@pytest.fixture
def app_state() -> Generator[AppState, None, None]:
    """Create an AppState instance for testing.

    Yields:
        AppState instance with empty initial state.
    """
    state = AppState()
    yield state


@pytest.fixture
def mock_app_context():
    """Create a mock AppContext for testing."""
    mock_context = MagicMock()
    mock_app_config = MagicMock()
    mock_app_config.get_blinded.return_value = False
    mock_context.app_config = mock_app_config
    return mock_context

