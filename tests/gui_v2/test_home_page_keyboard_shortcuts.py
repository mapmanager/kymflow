"""Tests for HomePage keyboard shortcuts."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from kymflow.gui_v2.app_context import AppContext
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.events import SaveSelected
from kymflow.gui_v2.pages.home_page import HomePage


def test_save_selected_shortcut_emits_event(bus: EventBus) -> None:
    """Test that _on_save_selected_shortcut emits SaveSelected intent event."""
    context = AppContext()
    page = HomePage(context, bus)

    # Mock bus.emit to capture emitted events
    emitted_events = []
    original_emit = bus.emit

    def capture_emit(event):
        emitted_events.append(event)
        original_emit(event)

    bus.emit = capture_emit

    # Call the shortcut handler
    page._on_save_selected_shortcut({})

    # Verify SaveSelected event was emitted with correct phase
    assert len(emitted_events) == 1
    assert isinstance(emitted_events[0], SaveSelected)
    assert emitted_events[0].phase == "intent"


def test_register_save_selected_shortcut_idempotent(bus: EventBus) -> None:
    """Test that _register_save_selected_shortcut is idempotent."""
    context = AppContext()
    page = HomePage(context, bus)

    # First registration
    with patch("nicegui.ui.on") as mock_on, patch("nicegui.ui.run_javascript") as mock_js:
        page._register_save_selected_shortcut()
        assert page._save_selected_shortcut_registered is True
        assert mock_on.call_count == 1
        assert mock_js.call_count == 1

        # Second registration should not register again
        page._register_save_selected_shortcut()
        assert mock_on.call_count == 1  # Should not call again
        assert mock_js.call_count == 1  # Should not call again


def test_register_save_selected_shortcut_calls_ui_on(bus: EventBus) -> None:
    """Test that _register_save_selected_shortcut calls ui.on with correct event name."""
    context = AppContext()
    page = HomePage(context, bus)

    with patch("nicegui.ui.on") as mock_on, patch("nicegui.ui.run_javascript"):
        page._register_save_selected_shortcut()

        # Verify ui.on was called with correct event name and handler
        assert mock_on.call_count == 1
        call_args = mock_on.call_args
        assert call_args[0][0] == "kymflow_save_selected"
        assert call_args[0][1] == page._on_save_selected_shortcut


def test_register_save_selected_shortcut_injects_javascript(bus: EventBus) -> None:
    """Test that _register_save_selected_shortcut injects JavaScript listener."""
    context = AppContext()
    page = HomePage(context, bus)

    with patch("nicegui.ui.on"), patch("nicegui.ui.run_javascript") as mock_js:
        page._register_save_selected_shortcut()

        # Verify JavaScript was injected
        assert mock_js.call_count == 1
        js_code = mock_js.call_args[0][0]

        # Verify JavaScript contains key checks
        assert "e.metaKey" in js_code or "e.ctrlKey" in js_code
        assert "e.key !== 's'" in js_code or "e.key !== 'S'" in js_code
        assert "e.preventDefault()" in js_code
        assert "emitEvent('kymflow_save_selected'" in js_code
        assert "window._kymflow_save_selected_listener" in js_code


def test_register_save_selected_shortcut_checks_editable(bus: EventBus) -> None:
    """Test that JavaScript checks for editable elements before triggering."""
    context = AppContext()
    page = HomePage(context, bus)

    with patch("nicegui.ui.on"), patch("nicegui.ui.run_javascript") as mock_js:
        page._register_save_selected_shortcut()

        js_code = mock_js.call_args[0][0]

        # Verify JavaScript checks for editable elements (same pattern as Enter shortcut)
        assert "isContentEditable" in js_code
        assert "INPUT" in js_code
        assert "TEXTAREA" in js_code
        assert "ag-cell-edit-input" in js_code
        assert "ag-cell-inline-editing" in js_code


def test_save_selected_shortcut_initial_state(bus: EventBus) -> None:
    """Test that save selected shortcut starts unregistered."""
    context = AppContext()
    page = HomePage(context, bus)

    assert page._save_selected_shortcut_registered is False
    assert page._save_selected_shortcut_event == "kymflow_save_selected"


@pytest.mark.skip(reason="this test is currently broken")
def test_render_registers_save_selected_shortcut(bus: EventBus) -> None:
    """Test that render() calls _register_save_selected_shortcut."""
    context = AppContext()
    page = HomePage(context, bus)

    # Mock dark_mode object that build_header expects
    mock_dark_mode = MagicMock()
    mock_dark_mode.value = False

    # Mock all NiceGUI calls and context methods
    with patch.object(page, "_register_save_selected_shortcut") as mock_register:
        with patch.object(page, "_register_full_zoom_shortcut"):
            with patch.object(page, "_register_next_prev_file_shortcuts"):
                with patch("nicegui.ui.page_title"):
                    with patch("nicegui.ui.dark_mode", return_value=mock_dark_mode):
                        with patch.object(context, "init_dark_mode_for_page", return_value=mock_dark_mode):
                            with patch("kymflow.gui_v2.navigation.build_header"):
                                with patch("nicegui.ui.add_css"):
                                    # Mock splitter as a context manager
                                    mock_splitter = MagicMock()
                                    mock_splitter.before = MagicMock()
                                    mock_splitter.after = MagicMock()
                                    mock_splitter.separator = MagicMock()
                                    mock_splitter.value = 6
                                    mock_splitter.__enter__ = MagicMock(return_value=mock_splitter)
                                    mock_splitter.__exit__ = MagicMock(return_value=None)
                                    
                                    with patch("nicegui.ui.splitter", return_value=mock_splitter):
                                        with patch.object(page, "_drawer_view") as mock_drawer:
                                            mock_drawer.render = MagicMock()
                                            mock_drawer.initialize_views = MagicMock()
                                            with patch("nicegui.ui.column"):
                                                with patch("nicegui.ui.element"):
                                                    with patch("nicegui.ui.button"):
                                                        with patch.object(page, "build"):
                                                            with patch.object(page, "_ensure_setup"):
                                                                page.render(page_title="Test")

                                                                # Verify registration was called
                                                                mock_register.assert_called_once()
