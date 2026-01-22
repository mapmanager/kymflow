"""Tests for contrast widget (view, bindings, controller)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from kymflow.core.plotting.theme import ThemeMode
from kymflow.gui_v2.events_legacy import ImageDisplayOrigin
from kymflow.gui_v2.state import AppState, ImageDisplayParams
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.controllers.image_display_controller import ImageDisplayController
from kymflow.gui_v2.events import FileSelection, ImageDisplayChange, SelectionOrigin
from kymflow.gui_v2.events_state import ThemeChanged
from kymflow.gui_v2.views.contrast_bindings import ContrastBindings
from kymflow.gui_v2.views.contrast_view import ContrastView


def test_contrast_view_emits_intent_on_slider_change(bus: EventBus) -> None:
    """Test that ContrastView emits ImageDisplayChange(phase="intent") when slider changes."""
    received: list[ImageDisplayChange] = []

    def on_change(event: ImageDisplayChange) -> None:
        received.append(event)

    view = ContrastView(on_image_display_change=on_change)
    # Mock UI elements since we can't render in tests
    view._min_slider = MagicMock()
    view._min_slider.value = 10
    view._max_slider = MagicMock()
    view._max_slider.value = 100
    view._display_params = ImageDisplayParams(
        colorscale="Gray", zmin=0, zmax=255, origin=ImageDisplayOrigin.OTHER
    )
    view._updating_programmatically = False

    # Simulate slider change
    view._on_slider_change()

    assert len(received) == 1
    assert received[0].phase == "intent"
    assert received[0].params.zmin == 10
    assert received[0].params.zmax == 100
    assert received[0].origin == SelectionOrigin.IMAGE_VIEWER


def test_contrast_view_emits_intent_on_colorscale_change(bus: EventBus) -> None:
    """Test that ContrastView emits ImageDisplayChange(phase="intent") when colorscale changes."""
    received: list[ImageDisplayChange] = []

    def on_change(event: ImageDisplayChange) -> None:
        received.append(event)

    view = ContrastView(on_image_display_change=on_change)
    view._colorscale_select = MagicMock()
    view._colorscale_select.value = "Viridis"
    view._display_params = ImageDisplayParams(
        colorscale="Gray", zmin=0, zmax=255, origin=ImageDisplayOrigin.OTHER
    )
    view._updating_programmatically = False

    # Simulate colorscale change
    view._on_colorscale_change()

    assert len(received) == 1
    assert received[0].phase == "intent"
    assert received[0].params.colorscale == "Viridis"


def test_contrast_bindings_subscribes_to_events(bus: EventBus) -> None:
    """Test that ContrastBindings subscribes to correct events."""
    view = ContrastView(on_image_display_change=lambda e: None)
    bindings = ContrastBindings(bus, view)

    # Verify subscriptions by emitting events and checking view methods are called
    view.set_selected_file = MagicMock()
    view.set_image_display = MagicMock()
    view.set_theme = MagicMock()

    # Emit FileSelection
    bus.emit(
        FileSelection(
            path=None, file=None, origin=SelectionOrigin.EXTERNAL, phase="state"
        )
    )
    view.set_selected_file.assert_called_once()

    # Emit ImageDisplayChange
    params = ImageDisplayParams(
        colorscale="Gray", zmin=0, zmax=255, origin=ImageDisplayOrigin.OTHER
    )
    bus.emit(
        ImageDisplayChange(
            params=params, origin=SelectionOrigin.EXTERNAL, phase="state"
        )
    )
    view.set_image_display.assert_called_once_with(params)

    # Emit ThemeChanged
    from kymflow.gui_v2.events_state import ThemeChanged
    bus.emit(ThemeChanged(theme=ThemeMode.LIGHT))
    view.set_theme.assert_called_once_with(ThemeMode.LIGHT)

    bindings.teardown()


def test_image_display_controller_calls_app_state(bus: EventBus, app_state: AppState) -> None:
    """Test that ImageDisplayController calls app_state.set_image_display()."""
    controller = ImageDisplayController(app_state, bus)

    # Track calls to set_image_display
    calls = []
    original_set = app_state.set_image_display

    def track_set(params: ImageDisplayParams) -> None:
        calls.append(params)
        original_set(params)

    app_state.set_image_display = track_set

    # Emit intent event
    params = ImageDisplayParams(
        colorscale="Viridis", zmin=10, zmax=200, origin=ImageDisplayOrigin.CONTRAST_WIDGET
    )
    bus.emit(
        ImageDisplayChange(
            params=params, origin=SelectionOrigin.IMAGE_VIEWER, phase="intent"
        )
    )

    assert len(calls) == 1
    assert calls[0].colorscale == "Viridis"
    assert calls[0].zmin == 10
    assert calls[0].zmax == 200
