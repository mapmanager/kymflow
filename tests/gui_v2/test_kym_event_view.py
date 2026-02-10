"""Tests for KymEventView - range-setting state and cancel functionality."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from kymflow.gui_v2.events import SetKymEventRangeState
from kymflow.gui_v2.views.kym_event_view import KymEventView


@pytest.fixture
def mock_app_context():
    """Create a mock AppContext for testing."""
    mock_context = MagicMock()
    mock_app_config = MagicMock()
    mock_app_config.get_blinded.return_value = False
    mock_context.app_config = mock_app_config
    return mock_context


@pytest.fixture
def kym_event_view(mock_app_context) -> KymEventView:
    """Create a KymEventView instance for testing."""
    return KymEventView(
        mock_app_context,
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


def test_event_filter_initialization(kym_event_view: KymEventView) -> None:
    """Test that event filter is initialized with default values."""
    # Verify default filter state (nan_gap is False by default)
    assert kym_event_view._event_filter == {
        "baseline_drop": True,
        "baseline_rise": True,
        "nan_gap": False,  # False by default
        "zero_gap": True,
        "User Added": True,
    }
    assert kym_event_view._on_event_filter_changed is None


def test_on_event_type_filter_changed_updates_filter(kym_event_view: KymEventView) -> None:
    """Test that _on_event_type_filter_changed updates filter and calls callback."""
    callback_calls: list[dict[str, bool]] = []

    def on_filter_changed(filter: dict[str, bool]) -> None:
        callback_calls.append(filter)

    kym_event_view._on_event_filter_changed = on_filter_changed

    # Set up some test rows
    kym_event_view._all_rows = [
        {"event_id": "1", "roi_id": 1, "event_type": "baseline_drop", "t_start": 0.0},
        {"event_id": "2", "roi_id": 1, "event_type": "baseline_rise", "t_start": 1.0},
        {"event_id": "3", "roi_id": 1, "event_type": "nan_gap", "t_start": 2.0},
    ]

    # Enable nan_gap in filter so it's visible (default is False)
    kym_event_view._event_filter["nan_gap"] = True

    # Mock grid
    mock_grid = MagicMock()
    kym_event_view._grid = mock_grid

    # Toggle baseline_drop to False
    kym_event_view._on_event_type_filter_changed("baseline_drop", False)

    # Verify filter was updated
    assert kym_event_view._event_filter["baseline_drop"] is False
    assert kym_event_view._event_filter["baseline_rise"] is True  # Unchanged
    assert kym_event_view._event_filter["nan_gap"] is True  # Still enabled

    # Verify callback was called with updated filter
    assert len(callback_calls) == 1
    assert callback_calls[0]["baseline_drop"] is False

    # Verify grid was updated (filtered rows)
    assert mock_grid.set_data.called
    call_args = mock_grid.set_data.call_args[0][0]
    # Should only include baseline_rise and nan_gap (baseline_drop filtered out)
    assert len(call_args) == 2
    event_types = {row["event_type"] for row in call_args}
    assert "baseline_rise" in event_types
    assert "nan_gap" in event_types
    assert "baseline_drop" not in event_types


def test_apply_filter_filters_by_event_type(kym_event_view: KymEventView) -> None:
    """Test that _apply_filter filters rows by event_type."""
    # Set up test rows with different event types
    kym_event_view._all_rows = [
        {"event_id": "1", "roi_id": 1, "event_type": "baseline_drop", "t_start": 0.0},
        {"event_id": "2", "roi_id": 1, "event_type": "baseline_rise", "t_start": 1.0},
        {"event_id": "3", "roi_id": 1, "event_type": "nan_gap", "t_start": 2.0},
        {"event_id": "4", "roi_id": 1, "event_type": "zero_gap", "t_start": 3.0},
        {"event_id": "5", "roi_id": 1, "event_type": "User Added", "t_start": 4.0},
    ]

    # Set filter to show only baseline_drop and baseline_rise
    kym_event_view._event_filter = {
        "baseline_drop": True,
        "baseline_rise": True,
        "nan_gap": False,
        "zero_gap": False,
        "User Added": False,
    }

    # Mock grid
    mock_grid = MagicMock()
    kym_event_view._grid = mock_grid

    # Apply filter
    kym_event_view._apply_filter()

    # Verify grid was updated with filtered rows
    assert mock_grid.set_data.called
    filtered_rows = mock_grid.set_data.call_args[0][0]
    assert len(filtered_rows) == 2
    event_types = {row["event_type"] for row in filtered_rows}
    assert "baseline_drop" in event_types
    assert "baseline_rise" in event_types
    assert "nan_gap" not in event_types
    assert "zero_gap" not in event_types
    assert "User Added" not in event_types


def test_apply_filter_combines_roi_and_event_type_filters(kym_event_view: KymEventView) -> None:
    """Test that _apply_filter combines ROI filter and event type filter."""
    # Set up test rows with different ROIs and event types
    kym_event_view._all_rows = [
        {"event_id": "1", "roi_id": 1, "event_type": "baseline_drop", "t_start": 0.0},
        {"event_id": "2", "roi_id": 1, "event_type": "baseline_rise", "t_start": 1.0},
        {"event_id": "3", "roi_id": 2, "event_type": "baseline_drop", "t_start": 2.0},
        {"event_id": "4", "roi_id": 2, "event_type": "baseline_rise", "t_start": 3.0},
    ]

    # Set ROI filter to ROI 1
    kym_event_view._roi_filter = 1

    # Set event type filter to show only baseline_drop
    kym_event_view._event_filter = {
        "baseline_drop": True,
        "baseline_rise": False,
        "nan_gap": False,
        "zero_gap": False,
        "User Added": False,
    }

    # Mock grid
    mock_grid = MagicMock()
    kym_event_view._grid = mock_grid

    # Apply filter
    kym_event_view._apply_filter()

    # Verify grid was updated with filtered rows (ROI 1 AND baseline_drop)
    assert mock_grid.set_data.called
    filtered_rows = mock_grid.set_data.call_args[0][0]
    assert len(filtered_rows) == 1
    assert filtered_rows[0]["roi_id"] == 1
    assert filtered_rows[0]["event_type"] == "baseline_drop"


def test_kym_event_view_blinded_displays_blinded_data() -> None:
    """Test that KymEventView uses blinded data when blinded=True."""
    from unittest.mock import MagicMock
    from kymflow.core.image_loaders.kym_image import KymImage
    from pathlib import Path
    import numpy as np
    
    # Create mock app context with blinded=True
    mock_context = MagicMock()
    mock_app_config = MagicMock()
    mock_app_config.get_blinded.return_value = True
    mock_context.app_config = mock_app_config
    
    # Create a KymImage with path
    test_path = Path("/a/b/c/test_file.tif")
    test_image = np.zeros((100, 200), dtype=np.uint16)
    kym_image = KymImage(path=test_path, img_data=test_image, load_image=False)
    kym_image.update_header(shape=(100, 200), ndim=2, voxels=[0.001, 0.284])
    
    kym_analysis = kym_image.get_kym_analysis()
    from kymflow.core.image_loaders.roi import RoiBounds
    bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
    roi = kym_image.rois.create_roi(bounds=bounds)
    kym_analysis.add_velocity_event(roi.id, t_start=0.5, t_end=1.0)
    
    # Create view with blinded context
    view = KymEventView(
        mock_context,
        on_selected=lambda e: None,
    )
    
    # Get velocity report (should be blinded)
    report = kym_analysis.get_velocity_report(roi_id=roi.id, blinded=True)
    view.set_events(report)
    
    # Check that all_rows has blinded data
    assert len(view._all_rows) == 1
    row = view._all_rows[0]
    
    # file_name should be blinded
    assert row["file_name"] == "Blinded"
    
    # grandparent_folder should be blinded
    assert row["grandparent_folder"] == "Blinded"
    
    # Other fields should remain unchanged
    assert row["roi_id"] == roi.id
    assert row["t_start"] == 0.5


def test_apply_filter_with_all_event_types_disabled(kym_event_view: KymEventView) -> None:
    """Test that _apply_filter returns empty list when all event types are disabled."""
    kym_event_view._all_rows = [
        {"event_id": "1", "roi_id": 1, "event_type": "baseline_drop", "t_start": 0.0},
        {"event_id": "2", "roi_id": 1, "event_type": "baseline_rise", "t_start": 1.0},
    ]

    # Disable all event types
    kym_event_view._event_filter = {
        "baseline_drop": False,
        "baseline_rise": False,
        "nan_gap": False,
        "zero_gap": False,
        "User Added": False,
    }

    # Mock grid
    mock_grid = MagicMock()
    kym_event_view._grid = mock_grid

    # Apply filter
    kym_event_view._apply_filter()

    # Verify grid was updated with empty list
    assert mock_grid.set_data.called
    filtered_rows = mock_grid.set_data.call_args[0][0]
    assert len(filtered_rows) == 0
