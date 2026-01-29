"""Tests for bindings subscribing to TaskStateChanged and calling set_task_state (Tier 2)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.events_state import TaskStateChanged
from kymflow.gui_v2.views.analysis_toolbar_bindings import AnalysisToolbarBindings
from kymflow.gui_v2.views.analysis_toolbar_view import AnalysisToolbarView
from kymflow.gui_v2.views.file_table_bindings import FileTableBindings
from kymflow.gui_v2.views.file_table_view import FileTableView
from kymflow.gui_v2.views.folder_selector_bindings import FolderSelectorBindings
from kymflow.gui_v2.views.folder_selector_view import FolderSelectorView
from kymflow.gui_v2.views.metadata_experimental_bindings import MetadataExperimentalBindings
from kymflow.gui_v2.views.metadata_experimental_view import MetadataExperimentalView
from kymflow.gui_v2.views.metadata_header_bindings import MetadataHeaderBindings
from kymflow.gui_v2.views.metadata_header_view import MetadataHeaderView
from kymflow.gui_v2.views.save_buttons_bindings import SaveButtonsBindings
from kymflow.gui_v2.views.save_buttons_view import SaveButtonsView


def test_analysis_toolbar_bindings_subscribes_to_task_state(bus: EventBus) -> None:
    """Test that AnalysisToolbarBindings subscribes to TaskStateChanged."""
    view = AnalysisToolbarView(
        on_analysis_start=lambda e: None,
        on_analysis_cancel=lambda e: None,
        on_add_roi=lambda e: None,
        on_delete_roi=lambda e: None,
        on_set_roi_edit_state=lambda e: None,
        on_roi_selected=lambda e: None,
    )

    view.set_task_state = MagicMock()

    bindings = AnalysisToolbarBindings(bus, view)

    # Emit TaskStateChanged event
    task_state = TaskStateChanged(
        task_type="home", running=True, cancellable=True, progress=0.5, message="Running"
    )
    bus.emit(task_state)

    # Verify set_task_state was called
    view.set_task_state.assert_called_once_with(task_state)

    bindings.teardown()


def test_analysis_toolbar_bindings_filters_task_type(bus: EventBus) -> None:
    """Test that AnalysisToolbarBindings only processes 'home' task type."""
    view = AnalysisToolbarView(
        on_analysis_start=lambda e: None,
        on_analysis_cancel=lambda e: None,
        on_add_roi=lambda e: None,
        on_delete_roi=lambda e: None,
        on_set_roi_edit_state=lambda e: None,
        on_roi_selected=lambda e: None,
    )

    view.set_task_state = MagicMock()

    bindings = AnalysisToolbarBindings(bus, view)

    # Emit TaskStateChanged with different task_type
    task_state_other = TaskStateChanged(
        task_type="other", running=True, cancellable=True, progress=0.5, message="Running"
    )
    bus.emit(task_state_other)

    # Verify set_task_state was NOT called (filtered out)
    view.set_task_state.assert_not_called()

    # Emit TaskStateChanged with 'home' task_type
    task_state_home = TaskStateChanged(
        task_type="home", running=True, cancellable=True, progress=0.5, message="Running"
    )
    bus.emit(task_state_home)

    # Verify set_task_state WAS called for 'home' task
    view.set_task_state.assert_called_once_with(task_state_home)

    bindings.teardown()


def test_save_buttons_bindings_subscribes_to_task_state(bus: EventBus) -> None:
    """Test that SaveButtonsBindings subscribes to TaskStateChanged."""
    view = SaveButtonsView(
        on_save_selected=lambda e: None,
        on_save_all=lambda e: None,
    )

    view.set_task_state = MagicMock()

    bindings = SaveButtonsBindings(bus, view)

    # Emit TaskStateChanged event
    task_state = TaskStateChanged(
        task_type="home", running=True, cancellable=True, progress=0.5, message="Running"
    )
    bus.emit(task_state)

    # Verify set_task_state was called
    view.set_task_state.assert_called_once_with(task_state)

    bindings.teardown()


def test_file_table_bindings_subscribes_to_task_state(bus: EventBus) -> None:
    """Test that FileTableBindings subscribes to TaskStateChanged."""
    view = FileTableView(on_selected=lambda e: None)

    view.set_task_state = MagicMock()

    bindings = FileTableBindings(bus, view)

    # Emit TaskStateChanged event
    task_state = TaskStateChanged(
        task_type="home", running=True, cancellable=True, progress=0.5, message="Running"
    )
    bus.emit(task_state)

    # Verify set_task_state was called
    view.set_task_state.assert_called_once_with(task_state)

    bindings.teardown()


def test_file_table_bindings_filters_task_type(bus: EventBus) -> None:
    """Test that FileTableBindings only processes 'home' task type."""
    view = FileTableView(on_selected=lambda e: None)

    view.set_task_state = MagicMock()

    bindings = FileTableBindings(bus, view)

    # Emit TaskStateChanged with different task_type
    task_state_other = TaskStateChanged(
        task_type="other", running=True, cancellable=True, progress=0.5, message="Running"
    )
    bus.emit(task_state_other)

    # Verify set_task_state was NOT called (filtered out)
    view.set_task_state.assert_not_called()

    # Emit TaskStateChanged with 'home' task_type
    task_state_home = TaskStateChanged(
        task_type="home", running=True, cancellable=True, progress=0.5, message="Running"
    )
    bus.emit(task_state_home)

    # Verify set_task_state WAS called for 'home' task
    view.set_task_state.assert_called_once_with(task_state_home)

    bindings.teardown()


def test_metadata_header_bindings_subscribes_to_task_state(bus: EventBus) -> None:
    """Test that MetadataHeaderBindings subscribes to TaskStateChanged."""
    view = MetadataHeaderView(on_metadata_update=lambda e: None)

    view.set_task_state = MagicMock()

    bindings = MetadataHeaderBindings(bus, view)

    # Emit TaskStateChanged event
    task_state = TaskStateChanged(
        task_type="home", running=True, cancellable=True, progress=0.5, message="Running"
    )
    bus.emit(task_state)

    # Verify set_task_state was called
    view.set_task_state.assert_called_once_with(task_state)

    bindings.teardown()


def test_metadata_experimental_bindings_subscribes_to_task_state(bus: EventBus) -> None:
    """Test that MetadataExperimentalBindings subscribes to TaskStateChanged."""
    view = MetadataExperimentalView(on_metadata_update=lambda e: None)

    view.set_task_state = MagicMock()

    bindings = MetadataExperimentalBindings(bus, view)

    # Emit TaskStateChanged event
    task_state = TaskStateChanged(
        task_type="home", running=True, cancellable=True, progress=0.5, message="Running"
    )
    bus.emit(task_state)

    # Verify set_task_state was called
    view.set_task_state.assert_called_once_with(task_state)

    bindings.teardown()


def test_folder_selector_bindings_subscribes_to_task_state(bus: EventBus) -> None:
    """Test that FolderSelectorBindings subscribes to TaskStateChanged."""
    from kymflow.gui_v2.state import AppState

    app_state = AppState()
    view = FolderSelectorView(bus=bus, app_state=app_state, user_config=None)

    view.set_task_state = MagicMock()

    bindings = FolderSelectorBindings(bus, view)

    # Emit TaskStateChanged event
    task_state = TaskStateChanged(
        task_type="home", running=True, cancellable=True, progress=0.5, message="Running"
    )
    bus.emit(task_state)

    # Verify set_task_state was called
    view.set_task_state.assert_called_once_with(task_state)

    bindings.teardown()


def test_folder_selector_bindings_filters_task_type(bus: EventBus) -> None:
    """Test that FolderSelectorBindings only processes 'home' task type."""
    from kymflow.gui_v2.state import AppState

    app_state = AppState()
    view = FolderSelectorView(bus=bus, app_state=app_state, user_config=None)

    view.set_task_state = MagicMock()

    bindings = FolderSelectorBindings(bus, view)

    # Emit TaskStateChanged with different task_type
    task_state_other = TaskStateChanged(
        task_type="other", running=True, cancellable=True, progress=0.5, message="Running"
    )
    bus.emit(task_state_other)

    # Verify set_task_state was NOT called (filtered out)
    view.set_task_state.assert_not_called()

    # Emit TaskStateChanged with 'home' task_type
    task_state_home = TaskStateChanged(
        task_type="home", running=True, cancellable=True, progress=0.5, message="Running"
    )
    bus.emit(task_state_home)

    # Verify set_task_state WAS called for 'home' task
    view.set_task_state.assert_called_once_with(task_state_home)

    bindings.teardown()
