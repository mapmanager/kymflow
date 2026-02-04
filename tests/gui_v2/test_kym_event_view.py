"""Tests for KymEventView - range-setting state and cancel functionality."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from kymflow.gui_v2.events import SetKymEventRangeState
from kymflow.gui_v2.views.kym_event_view import KymEventView


@pytest.fixture
def kym_event_view() -> KymEventView:
    """Create a KymEventView instance for testing."""
    return KymEventView(
        on_selected=lambda e: None,
        on_file_selected=lambda e: None,
        on_event_update=lambda e: None,
        on_range_state=lambda e: None,
        on_add_event=lambda e: None,
        on_delete_event=lambda e: None,
        on_next_prev_file=lambda e: None,
    )


def test_notification_cancel_button_cancels_state(kym_event_view: KymEventView) -> None:
    """Test that clicking Cancel in notification cancels the range-setting state."""
    received_range_states: list[SetKymEventRangeState] = []

    def on_range_state(event: SetKymEventRangeState) -> None:
        received_range_states.append(event)

    kym_event_view._on_range_state = on_range_state

    # Set up: enter range-setting state
    kym_event_view._selected_event_id = "test-event-1"
    kym_event_view._selected_event_roi_id = 1
    kym_event_view._selected_event_path = "/test/path.tif"
    kym_event_view._setting_kym_event_range_state = True

    # Mock notification
    mock_notification = MagicMock()
    kym_event_view._range_notification = mock_notification
    kym_event_view._dismissing_programmatically = False

    # Simulate user clicking Cancel button in notification
    # This calls _on_notification_dismissed() which then calls _on_cancel_event_range_clicked()
    kym_event_view._on_notification_dismissed(MagicMock())

    # Verify state was cancelled
    assert kym_event_view._setting_kym_event_range_state is False
    assert kym_event_view._range_notification is None
    # Verify SetKymEventRangeState(enabled=False) was emitted
    assert len(received_range_states) == 1
    assert received_range_states[0].enabled is False
    assert received_range_states[0].event_id == "test-event-1"


def test_toolbar_cancel_button_cancels_state(kym_event_view: KymEventView) -> None:
    """Test that clicking Cancel in toolbar cancels the range-setting state."""
    received_range_states: list[SetKymEventRangeState] = []

    def on_range_state(event: SetKymEventRangeState) -> None:
        received_range_states.append(event)

    kym_event_view._on_range_state = on_range_state

    # Set up: enter range-setting state
    kym_event_view._selected_event_id = "test-event-1"
    kym_event_view._selected_event_roi_id = 1
    kym_event_view._selected_event_path = "/test/path.tif"
    kym_event_view._setting_kym_event_range_state = True

    # Mock notification
    mock_notification = MagicMock()
    kym_event_view._range_notification = mock_notification

    # Simulate user clicking Cancel button in toolbar
    kym_event_view._on_cancel_event_range_clicked()

    # Verify state was cancelled
    assert kym_event_view._setting_kym_event_range_state is False
    # Verify SetKymEventRangeState(enabled=False) was emitted
    assert len(received_range_states) == 1
    assert received_range_states[0].enabled is False
    assert received_range_states[0].event_id == "test-event-1"


def test_both_cancel_buttons_do_same_thing(kym_event_view: KymEventView) -> None:
    """Test that notification cancel and toolbar cancel both call the same cancel handler."""
    received_range_states: list[SetKymEventRangeState] = []

    def on_range_state(event: SetKymEventRangeState) -> None:
        received_range_states.append(event)

    kym_event_view._on_range_state = on_range_state

    # Set up: enter range-setting state
    kym_event_view._selected_event_id = "test-event-1"
    kym_event_view._selected_event_roi_id = 1
    kym_event_view._selected_event_path = "/test/path.tif"
    kym_event_view._setting_kym_event_range_state = True
    kym_event_view._range_notification = MagicMock()
    kym_event_view._dismissing_programmatically = False

    # Simulate notification cancel (calls _on_notification_dismissed -> _on_cancel_event_range_clicked)
    kym_event_view._on_notification_dismissed(MagicMock())
    assert kym_event_view._setting_kym_event_range_state is False
    assert len(received_range_states) == 1
    assert received_range_states[0].enabled is False

    # Reset and simulate toolbar cancel (calls _on_cancel_event_range_clicked directly)
    kym_event_view._setting_kym_event_range_state = True
    kym_event_view._range_notification = MagicMock()
    received_range_states.clear()
    kym_event_view._on_cancel_event_range_clicked()
    assert kym_event_view._setting_kym_event_range_state is False
    assert len(received_range_states) == 1
    assert received_range_states[0].enabled is False

    # Both paths should have the same effect: state cancelled and event emitted


def test_render_cancels_state_on_recreation(kym_event_view: KymEventView) -> None:
    """Test that render() cancels range-setting state when view is recreated (navigation away/back)."""
    received_range_states: list[SetKymEventRangeState] = []

    def on_range_state(event: SetKymEventRangeState) -> None:
        received_range_states.append(event)

    kym_event_view._on_range_state = on_range_state

    # Set up: enter range-setting state
    kym_event_view._selected_event_id = "test-event-1"
    kym_event_view._selected_event_roi_id = 1
    kym_event_view._selected_event_path = "/test/path.tif"
    kym_event_view._setting_kym_event_range_state = True

    # Mock notification
    mock_notification = MagicMock()
    kym_event_view._range_notification = mock_notification

    # Simulate view recreation (e.g., navigating away and back)
    # This should cancel the state
    with patch("kymflow.gui_v2.views.kym_event_view.ui"):
        kym_event_view.render()

    # Verify state was cancelled
    assert kym_event_view._setting_kym_event_range_state is False
    assert kym_event_view._range_notification is None
    # Verify SetKymEventRangeState(enabled=False) was emitted
    assert len(received_range_states) == 1
    assert received_range_states[0].enabled is False


def test_render_cancels_adding_new_event_state(kym_event_view: KymEventView) -> None:
    """Test that render() cancels adding_new_event state when view is recreated."""
    received_range_states: list[SetKymEventRangeState] = []

    def on_range_state(event: SetKymEventRangeState) -> None:
        received_range_states.append(event)

    kym_event_view._on_range_state = on_range_state

    # Set up: enter adding new event state
    kym_event_view._roi_filter = 1
    kym_event_view._current_file_path = "/test/path.tif"
    kym_event_view._adding_new_event = True
    kym_event_view._setting_kym_event_range_state = True

    # Mock notification
    mock_notification = MagicMock()
    kym_event_view._range_notification = mock_notification

    # Simulate view recreation
    with patch("kymflow.gui_v2.views.kym_event_view.ui"):
        kym_event_view.render()

    # Verify state was cancelled
    assert kym_event_view._adding_new_event is False
    assert kym_event_view._setting_kym_event_range_state is False
    assert kym_event_view._range_notification is None
    # Verify SetKymEventRangeState(enabled=False) was emitted
    assert len(received_range_states) == 1
    assert received_range_states[0].enabled is False


def test_render_no_op_when_state_not_active(kym_event_view: KymEventView) -> None:
    """Test that render() does nothing when range-setting state is not active."""
    received_range_states: list[SetKymEventRangeState] = []

    def on_range_state(event: SetKymEventRangeState) -> None:
        received_range_states.append(event)

    kym_event_view._on_range_state = on_range_state

    # Set up: NOT in range-setting state
    kym_event_view._setting_kym_event_range_state = False
    kym_event_view._adding_new_event = False
    kym_event_view._range_notification = None

    # Simulate view recreation
    with patch("kymflow.gui_v2.views.kym_event_view.ui"):
        kym_event_view.render()

    # Verify no state change and no event emitted
    assert kym_event_view._setting_kym_event_range_state is False
    assert kym_event_view._adding_new_event is False
    assert len(received_range_states) == 0


def test_notification_dismissed_programmatic_vs_user(kym_event_view: KymEventView) -> None:
    """Test that notification dismissal distinguishes between programmatic and user-initiated."""
    cancel_call_count = 0

    def mock_cancel() -> None:
        nonlocal cancel_call_count
        cancel_call_count += 1

    kym_event_view._on_cancel_event_range_clicked = mock_cancel

    # Set up: enter range-setting state
    kym_event_view._setting_kym_event_range_state = True
    mock_notification = MagicMock()
    kym_event_view._range_notification = mock_notification

    # Test programmatic dismiss (should NOT call cancel)
    kym_event_view._dismissing_programmatically = True
    kym_event_view._on_notification_dismissed(MagicMock())
    assert cancel_call_count == 0
    assert kym_event_view._range_notification is None

    # Reset
    kym_event_view._range_notification = MagicMock()
    kym_event_view._setting_kym_event_range_state = True

    # Test user-initiated dismiss (should call cancel)
    kym_event_view._dismissing_programmatically = False
    kym_event_view._on_notification_dismissed(MagicMock())
    assert cancel_call_count == 1
    assert kym_event_view._range_notification is None
