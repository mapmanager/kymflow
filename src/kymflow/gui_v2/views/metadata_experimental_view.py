"""Experimental metadata view component.

This module provides a view component that displays a form for editing
AcqImage experimental metadata. The view emits MetadataUpdate(phase="intent")
events when users edit fields, but does not subscribe to events (that's handled
by MetadataExperimentalBindings).

Commit-only behavior: we do not use on_value_change for editable fields.
We use blur and keydown.enter only, so events fire when the user commits
(Enter/Tab/click away), not on every keystroke or when set_value is called.
"""

from __future__ import annotations

from typing import Callable, Optional

from nicegui import ui

from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.core.image_loaders.metadata import ExperimentMetadata
from kymflow.gui_v2.client_utils import safe_call
from kymflow.gui_v2.events import MetadataUpdate, SelectionOrigin
from kymflow.gui_v2.events_state import TaskStateChanged
from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)

OnMetadataUpdate = Callable[[MetadataUpdate], None]


class MetadataExperimentalView:
    """Experimental metadata view component.

    This view displays a form for editing AcqImage experimental metadata.
    The form is generated dynamically from ExperimentMetadata.form_schema().
    Users can edit fields, which triggers MetadataUpdate(phase="intent") events.

    Lifecycle:
        - UI elements are created in render() (not __init__) to ensure correct
          DOM placement within NiceGUI's client context
        - Data updates via setter methods (called by bindings)
        - Events emitted via on_metadata_update callback

    Attributes:
        _on_metadata_update: Callback function that receives MetadataUpdate events.
        _widgets: Dictionary mapping field names to UI widgets (created in render()).
        _read_only_fields: Dictionary of read-only field definitions (for population).
        _current_file: Currently selected file (for populating fields).
        _get_field_options: Optional callback to provide preset options per field.
    """

    def __init__(
        self,
        *,
        on_metadata_update: OnMetadataUpdate,
        get_field_options: Callable[[str], list[str]] | None = None,
    ) -> None:
        """Initialize experimental metadata view.

        Args:
            on_metadata_update: Callback function that receives MetadataUpdate events.
            get_field_options: Optional callback taking a field name and returning
                a list of preset string options for that field. Used by the UI
                to populate select dropdowns from the current file list.
        """
        self._on_metadata_update = on_metadata_update
        self._get_field_options = get_field_options

        # UI components (created in render())
        self._widgets: dict[str, ui.input | ui.textarea | ui.select] = {}
        self._read_only_fields: dict[str, dict] = {}

        # State
        self._current_file: Optional[KymImage] = None
        self._task_state: Optional[TaskStateChanged] = None
        # Suppress intent emissions while we are syncing form from set_selected_file/clear
        self._suppress_field_change: bool = False
        # Field names that use ui.select (set in render())
        self._select_field_names: set[str] = set()
        # Last committed value per field; used to avoid emitting when user blurs without changing
        self._last_committed_values: dict[str, str] = {}

    def render(self) -> None:
        """Create the metadata form UI inside the current container.

        Always creates fresh UI elements because NiceGUI creates a new container
        context on each page navigation. Old UI elements are automatically cleaned
        up by NiceGUI when navigating away.
        """
        # Always reset widget references
        self._widgets = {}
        self._read_only_fields = {}
        self._select_field_names = set()

        ui.label("Experimental Metadata").classes("font-semibold")

        # Get schema from backend (no NiceGUI knowledge in schema)
        schema = ExperimentMetadata.form_schema()

        # Filter to only visible fields
        visible_schema = [f for f in schema if f.get("visible", True)]

        # Create lookup dictionary for read-only fields (for population)
        self._read_only_fields = {f["name"]: f for f in visible_schema if not f["editable"]}

        # Create widgets dynamically based on schema (preserve order)
        _numColumns = 2
        with ui.grid(columns=_numColumns).classes("w-full gap-2"):
            # Iterate through visible schema in order to preserve field ordering
            for field_def in visible_schema:
                widget_classes = "w-full"
                if field_def["grid_span"] == 2:
                    widget_classes += " col-span-2"

                field_name = field_def["name"]
                is_editable = field_def["editable"]
                widget_type = field_def["widget_type"]

                # Create widget based on type and editability
                if widget_type == "multiline":
                    # Always use textarea for multiline widgets
                    widget = ui.textarea(field_def["label"]).classes(widget_classes)

                    # Register blur callback for editable textarea fields
                    if is_editable:
                        widget.on(
                            "blur",
                            lambda field=field_name, w=widget: self._on_field_change(
                                field, w.value
                            ),
                        )
                elif widget_type == "text" and is_editable:
                    # Editable text fields: use ui.select with preset options + free entry
                    widget = ui.select(
                        options=[],
                        label=field_def["label"],
                        new_value_mode="add",
                        clearable=True,
                    ).classes(widget_classes)
                    self._select_field_names.add(field_name)

                    # Lazy-load options when the dropdown is opened or gains focus.
                    # Ensure current widget value stays in options so display is not wiped.
                    def _lazy_load_options(
                        field: str = field_name, w: ui.select = widget
                    ) -> None:
                        if self._get_field_options is None:
                            return
                        try:
                            options = list(self._get_field_options(field) or [])
                        except Exception:
                            logger.exception(
                                "Error getting field options for experimental metadata field '%s'",
                                field,
                            )
                            options = []
                        current = w.value
                        if current is not None and str(current).strip():
                            cur_str = str(current).strip()
                            if cur_str not in options:
                                options = [cur_str] + options
                        w.set_options(options, value=current)
                        w.update()

                    widget.on("popup-show", lambda _: _lazy_load_options())
                    widget.on("focus", lambda _: _lazy_load_options())

                    # Emit when user selects a pre-existing option from the dropdown.
                    # Only fire if value is in preset options (selection), not when typing (blur/enter handle that).
                    # After selection, blur the widget so it returns to display state (not edit state).
                    def _on_select_value_change(e, field: str = field_name, w: ui.select = widget) -> None:
                        if e.value is None:
                            return
                        opts = (self._get_field_options(field) or []) if self._get_field_options else []
                        if opts and str(e.value).strip() in [str(o).strip() for o in opts]:
                            self._on_field_change(field, e.value)
                            try:
                                w.run_method("blur")
                            except Exception:
                                pass

                    widget.on_value_change(_on_select_value_change)

                    # Commit-only for free-form edit: emit on blur/enter.
                    widget.on(
                        "blur",
                        lambda field=field_name, w=widget: self._on_field_change(
                            field, w.value
                        ),
                    )
                    widget.on(
                        "keydown.enter",
                        lambda field=field_name, w=widget: self._on_field_change(
                            field, w.value
                        ),
                    )
                else:
                    # Non-editable text/number fields: simple input with blur/enter handlers if editable
                    widget = ui.input(field_def["label"]).classes(widget_classes)

                    if is_editable:
                        widget.on(
                            "blur",
                            lambda field=field_name, w=widget: self._on_field_change(
                                field, w.value
                            ),
                        )
                        widget.on(
                            "keydown.enter",
                            lambda field=field_name, w=widget: self._on_field_change(
                                field, w.value
                            ),
                        )

                # Disable read-only fields
                if not is_editable:
                    widget.set_enabled(False)

                self._widgets[field_name] = widget
        self._update_widget_states()

    def set_selected_file(self, file: Optional[KymImage]) -> None:
        """Populate form fields from file metadata.

        Called by bindings when FileSelection(phase="state") or MetadataUpdate(phase="state")
        events are received. Populates all fields (editable and read-only) from the file's
        experimental metadata.

        Args:
            file: Selected KymImage instance, or None if selection cleared.
        """
        safe_call(self._set_selected_file_impl, file)

    def set_task_state(self, task_state: TaskStateChanged) -> None:
        """Update view for task state changes."""
        safe_call(self._set_task_state_impl, task_state)

    def _set_task_state_impl(self, task_state: TaskStateChanged) -> None:
        """Internal implementation of set_task_state."""
        self._task_state = task_state
        self._update_widget_states()

    def _set_selected_file_impl(self, file: Optional[KymImage]) -> None:
        """Internal implementation of set_selected_file."""
        self._current_file = file
        self._suppress_field_change = True
        try:
            if not file:
                self.clear()
                return

            meta = file.experiment_metadata
            if meta is None:
                self.clear()
                return

            # Use get_editable_values() for editable fields
            editable_values = meta.get_editable_values()
            for field_name, value in editable_values.items():
                if field_name not in self._widgets:
                    continue
                widget = self._widgets[field_name]
                value_str = str(value) if value is not None else ""
                normalized = (value_str.strip() if value_str else "")

                if field_name in self._select_field_names:
                    # Preload options and set value so current value is displayed
                    options = list(self._get_field_options(field_name) or []) if self._get_field_options else []
                    if normalized and normalized not in options:
                        options = [normalized] + options
                    widget.set_options(options, value=value_str or None)
                else:
                    widget.set_value(value_str)
                self._last_committed_values[field_name] = normalized

            # Populate read-only fields
            for field_name, field_def in self._read_only_fields.items():
                if field_name in self._widgets:
                    value = getattr(meta, field_name) or ""
                    self._widgets[field_name].set_value(str(value))
                    self._last_committed_values[field_name] = (str(value).strip() if value else "")
        finally:
            self._suppress_field_change = False

    def clear(self) -> None:
        """Clear all form fields.

        Called when no file is selected or file has no metadata.
        """
        self._suppress_field_change = True
        try:
            for field_name, widget in self._widgets.items():
                if field_name in self._select_field_names:
                    widget.set_options([], value=None)
                else:
                    widget.set_value("")
                self._last_committed_values[field_name] = ""
        finally:
            self._suppress_field_change = False

    def _update_widget_states(self) -> None:
        """Enable/disable editable fields based on task running state."""
        running = self._task_state.running if self._task_state else False
        for field_name, widget in self._widgets.items():
            if field_name in self._read_only_fields:
                widget.set_enabled(False)
            else:
                widget.set_enabled(not running)

    def _on_field_change(self, field_name: str, value: str | None) -> None:
        """Update metadata when a field value changes (commit-only: blur/enter).

        Emits MetadataUpdate(phase="intent") only when not syncing and value
        actually changed.

        Args:
            field_name: Name of the field being updated.
            value: The new value for the field.
        """
        if not self._current_file:
            return
        if self._suppress_field_change:
            return

        # Normalize for comparison: None and "" treated as empty
        new_val = (value or "").strip() if isinstance(value, str) else (str(value).strip() if value is not None else "")
        # Only emit if value actually changed from last committed (avoids emit on "click away" without edit)
        if new_val == self._last_committed_values.get(field_name, ""):
            return

        self._on_metadata_update(
            MetadataUpdate(
                file=self._current_file,
                metadata_type="experimental",
                fields={field_name: value},
                origin=SelectionOrigin.EXTERNAL,
                phase="intent",
            )
        )
        self._last_committed_values[field_name] = new_val
