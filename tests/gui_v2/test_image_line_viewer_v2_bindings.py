"""Unit tests for ImageLineViewerV2Bindings (Phase 3)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from kymflow.gui_v2.events import (
    KymEventSelection,
    KymEvent,
    KymEventAction,
    FileSelection,
    KymScrollXEvent,
    FileChanged,
    ROISelection,
    SelectionOrigin,
)
from kymflow.gui_v2.events_state import ThemeChanged
from kymflow.gui_v2.views.image_line_viewer_v2_bindings import (
    ImageLineViewerV2Bindings,
)
from kymflow.core.plotting.theme import ThemeMode


@pytest.fixture
def mock_v2_view() -> MagicMock:
    """Create a mock ImageLineViewerV2View."""
    view = MagicMock()
    view._current_file = MagicMock()
    view._current_file.path = "/fake/path.tif"
    return view


@pytest.fixture
def mock_bus() -> MagicMock:
    """Create a mock EventBus."""
    return MagicMock()


@pytest.mark.asyncio
async def test_file_selection_calls_view(
    mock_v2_view: MagicMock, mock_bus: MagicMock
) -> None:
    """FileSelection(state) calls set_selected_file with full selection state."""
    bindings = ImageLineViewerV2Bindings(mock_bus, mock_v2_view)
    file_mock = MagicMock()
    event = FileSelection(
        path=None,
        file=file_mock,
        roi_id=1,
        origin=SelectionOrigin.FILE_TABLE,
        phase="state",
    )
    await bindings._on_file_selection_changed(event)
    # v2 view set_selected_file receives (file, channel, roi_id); channel is None
    # in this test to keep focus on ROI selection behavior.
    mock_v2_view.set_selected_file.assert_called_once_with(file_mock, None, 1)


def test_roi_selection_calls_view(mock_v2_view: MagicMock, mock_bus: MagicMock) -> None:
    """ROISelection(state) calls set_selected_roi."""
    bindings = ImageLineViewerV2Bindings(mock_bus, mock_v2_view)
    event = ROISelection(
        roi_id=2,
        origin=SelectionOrigin.ANALYSIS_TOOLBAR,
        phase="state",
    )
    bindings._on_roi_changed(event)
    mock_v2_view.set_selected_roi.assert_called_once_with(2)


def test_theme_changed_calls_view(mock_v2_view: MagicMock, mock_bus: MagicMock) -> None:
    """ThemeChanged calls set_theme."""
    bindings = ImageLineViewerV2Bindings(mock_bus, mock_v2_view)
    event = ThemeChanged(theme=ThemeMode.LIGHT)
    bindings._on_theme_changed(event)
    mock_v2_view.set_theme.assert_called_once_with(ThemeMode.LIGHT)


def test_kym_event_add_calls_on_kym_event(mock_v2_view: MagicMock, mock_bus: MagicMock) -> None:
    """KymEvent(ADD) calls view.on_kym_event."""
    bindings = ImageLineViewerV2Bindings(mock_bus, mock_v2_view)
    event = KymEvent(
        action=KymEventAction.ADD,
        event_id="ev-1",
        roi_id=1,
        path=None,
        origin=SelectionOrigin.EVENT_TABLE,
        phase="state",
        t_start=1.0,
        t_end=2.0,
    )
    bindings._on_kym_event(event)
    mock_v2_view.on_kym_event.assert_called_once_with(event)


def test_kym_event_delete_calls_on_kym_event(mock_v2_view: MagicMock, mock_bus: MagicMock) -> None:
    """KymEvent(DELETE) calls view.on_kym_event."""
    bindings = ImageLineViewerV2Bindings(mock_bus, mock_v2_view)
    event = KymEvent(
        action=KymEventAction.DELETE,
        event_id="ev-1",
        roi_id=1,
        path=None,
        origin=SelectionOrigin.EVENT_TABLE,
        phase="state",
    )
    bindings._on_kym_event(event)
    mock_v2_view.on_kym_event.assert_called_once_with(event)


def test_event_selection_calls_zoom(mock_v2_view: MagicMock, mock_bus: MagicMock) -> None:
    """KymEventSelection calls zoom_to_event."""
    bindings = ImageLineViewerV2Bindings(mock_bus, mock_v2_view)
    event = KymEventSelection(
        event_id="ev-1",
        roi_id=1,
        path=None,
        event=None,
        options=None,
        origin=SelectionOrigin.EVENT_TABLE,
        phase="state",
    )
    bindings._on_event_selected(event)
    mock_v2_view.zoom_to_event.assert_called_once_with(event)


def test_kym_scroll_x_calls_view(mock_v2_view: MagicMock, mock_bus: MagicMock) -> None:
    """KymScrollXEvent calls scroll_x with direction."""
    bindings = ImageLineViewerV2Bindings(mock_bus, mock_v2_view)
    event = KymScrollXEvent(
        direction="next",
        origin=SelectionOrigin.EXTERNAL,
        phase="intent",
    )
    bindings._on_kym_scroll_x(event)
    mock_v2_view.scroll_x.assert_called_once_with("next")


def test_file_changed_roi_triggers_refresh_for_current_file(
    mock_v2_view: MagicMock, mock_bus: MagicMock
) -> None:
    """FileChanged(change_type='roi') for current file calls refresh_rois_for_current_file."""
    from kymflow.gui_v2.events import SelectionOrigin

    bindings = ImageLineViewerV2Bindings(mock_bus, mock_v2_view)
    event = FileChanged(
        file=mock_v2_view._current_file,
        change_type="roi",
        origin=SelectionOrigin.IMAGE_VIEWER,
    )
    bindings._on_file_changed(event)
    mock_v2_view.refresh_rois_for_current_file.assert_called_once()


def test_teardown_unsubscribes(mock_v2_view: MagicMock, mock_bus: MagicMock) -> None:
    """teardown() unsubscribes from all events."""
    bindings = ImageLineViewerV2Bindings(mock_bus, mock_v2_view)
    bindings.teardown()
    assert mock_bus.unsubscribe_state.call_count >= 10
    assert mock_bus.unsubscribe.call_count >= 1
    assert mock_bus.unsubscribe_intent.call_count >= 1
