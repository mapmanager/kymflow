"""Header metadata view component.

This module provides a view component that displays a form for editing
AcqImage header metadata. The view emits MetadataUpdate(phase="intent")
events when users edit fields, but does not subscribe to events (that's handled
by MetadataHeaderBindings).
"""

from __future__ import annotations

from typing import Callable, Optional

from nicegui import ui

from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.core.image_loaders.metadata import AcqImgHeader
from kymflow.gui_v2.client_utils import safe_call
from kymflow.gui_v2.events import EditPhysicalUnits, MetadataUpdate, SelectionOrigin
from kymflow.gui_v2.events_state import TaskStateChanged
from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)

OnMetadataUpdate = Callable[[MetadataUpdate], None]
OnEditPhysicalUnits = Callable[[EditPhysicalUnits], None]


class MetadataHeaderView:
    """Header metadata view component.

    This view displays a form for editing AcqImage header metadata.
    The form is generated dynamically from AcqImgHeader.form_schema().
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
    """

    def __init__(
        self,
        *,
        on_metadata_update: OnMetadataUpdate,
        on_edit_physical_units: OnEditPhysicalUnits | None = None,
    ) -> None:
        """Initialize header metadata view.

        Args:
            on_metadata_update: Callback function that receives MetadataUpdate events.
            on_edit_physical_units: Optional callback function that receives EditPhysicalUnits events.
        """
        self._on_metadata_update = on_metadata_update
        self._on_edit_physical_units = on_edit_physical_units

        # UI components (created in render())
        self._widgets: dict[str, ui.input | ui.textarea] = {}
        self._read_only_fields: dict[str, dict] = {}
        self._physical_units_widgets: dict[str, ui.number | ui.button] = {}

        # State
        self._current_file: Optional[KymImage] = None
        self._task_state: Optional[TaskStateChanged] = None

    def render(self) -> None:
        """Create the metadata form UI inside the current container.

        Always creates fresh UI elements because NiceGUI creates a new container
        context on each page navigation. Old UI elements are automatically cleaned
        up by NiceGUI when navigating away.
        """
        # Always reset widget references
        self._widgets = {}
        self._read_only_fields = {}
        self._physical_units_widgets = {}

        ui.label("Image Header Metadata").classes("font-semibold")

        # Get schema from backend (no NiceGUI knowledge in schema)
        schema = AcqImgHeader.form_schema()

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

                # Special case: skip "voxels" field - will create special widgets at end
                if field_name == "voxels":
                    continue

                # Create widget based on type and editability
                if field_def["widget_type"] == "multiline":
                    widget = ui.textarea(field_def["label"]).classes(widget_classes)
                else:  # text, etc.
                    widget = ui.input(field_def["label"]).classes(widget_classes)

                # Disable read-only fields
                if not is_editable:
                    widget.set_enabled(False)

                # Register blur/enter callbacks for editable fields
                if is_editable:
                    # Blur event (field loses focus)
                    widget.on(
                        "blur",
                        lambda field=field_name, w=widget: self._on_field_blur(field, w),
                    )
                    # Enter key event (only for input, not textarea)
                    if field_def["widget_type"] != "multiline":
                        widget.on(
                            "keydown.enter",
                            lambda field=field_name, w=widget: self._on_field_blur(field, w),
                        )

                self._widgets[field_name] = widget
            
            # Special case: physical units editing widgets at the end (spans both columns)
            # Create editable physical units inputs for KymImage
            # Always create these widgets; they'll be populated when a KymImage is selected
            with ui.element('div').classes("col-span-2 w-full"):
                with ui.row().classes("w-full gap-2 items-center"):
                    seconds_input = ui.number(
                        label="seconds/line",
                        value=0.0,
                        format="%.6f",
                        step=0.000001,
                    ).classes("flex-1")
                    um_input = ui.number(
                        label="um/pixel",
                        value=0.0,
                        format="%.3f",
                        step=0.001,
                    ).classes("flex-1")
                    ok_button = ui.button("OK", icon="check").classes("self-end")
                    
                    # Register OK button click handler
                    ok_button.on(
                        "click",
                        lambda: self._on_physical_units_ok(seconds_input, um_input),
                    )
                
                # Store widgets separately
                self._physical_units_widgets["seconds_per_line"] = seconds_input
                self._physical_units_widgets["um_per_pixel"] = um_input
                self._physical_units_widgets["ok_button"] = ok_button
        
        self._update_widget_states()

    def set_selected_file(self, file: Optional[KymImage]) -> None:
        """Populate form fields from file header metadata.

        Called by bindings when FileSelection(phase="state") or MetadataUpdate(phase="state")
        events are received. Populates all fields (editable and read-only) from the file's
        header metadata.

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

        if not file:
            self.clear()
            return

        # Access header via header property
        header = file.header if hasattr(file, "header") else None
        if header is None:
            self.clear()
            return

        # Populate editable fields (direct attribute access)
        for field_name in self._widgets.keys():
            if field_name not in self._read_only_fields:
                # This is an editable field
                value = getattr(header, field_name, None)
                if value is not None:
                    # Convert to string, handling lists/tuples
                    if isinstance(value, (list, tuple)):
                        value_str = ", ".join(str(v) for v in value)
                    else:
                        value_str = str(value)
                    self._widgets[field_name].set_value(value_str)
                else:
                    self._widgets[field_name].set_value("")

        # Populate read-only fields
        for field_name, field_def in self._read_only_fields.items():
            if field_name in self._widgets:
                value = getattr(header, field_name, None) or ""
                # Convert to string, handling lists/tuples
                if isinstance(value, (list, tuple)):
                    value_str = ", ".join(str(v) for v in value)
                else:
                    value_str = str(value)
                self._widgets[field_name].set_value(value_str)
        
        # Populate physical units widgets if they exist and file has valid voxels
        if self._physical_units_widgets and self._is_kym_image_with_2d_voxels(file):
            if header.voxels is not None and len(header.voxels) >= 2:
                seconds_input = self._physical_units_widgets.get("seconds_per_line")
                um_input = self._physical_units_widgets.get("um_per_pixel")
                if seconds_input is not None:
                    seconds_input.set_value(float(header.voxels[0]))
                if um_input is not None:
                    um_input.set_value(float(header.voxels[1]))
        elif self._physical_units_widgets:
            # Clear physical units widgets if file is invalid
            seconds_input = self._physical_units_widgets.get("seconds_per_line")
            um_input = self._physical_units_widgets.get("um_per_pixel")
            if seconds_input is not None:
                seconds_input.set_value(0.0)
            if um_input is not None:
                um_input.set_value(0.0)

    def clear(self) -> None:
        """Clear all form fields.

        Called when no file is selected or file has no header.
        """
        for widget in self._widgets.values():
            widget.set_value("")
        # Clear physical units widgets
        seconds_input = self._physical_units_widgets.get("seconds_per_line")
        um_input = self._physical_units_widgets.get("um_per_pixel")
        if seconds_input is not None:
            seconds_input.set_value(0.0)
        if um_input is not None:
            um_input.set_value(0.0)

    def _update_widget_states(self) -> None:
        """Enable/disable editable fields based on task running state."""
        running = self._task_state.running if self._task_state else False
        for field_name, widget in self._widgets.items():
            if field_name in self._read_only_fields:
                widget.set_enabled(False)
            else:
                widget.set_enabled(not running)
        # Update physical units widgets
        seconds_input = self._physical_units_widgets.get("seconds_per_line")
        um_input = self._physical_units_widgets.get("um_per_pixel")
        ok_button = self._physical_units_widgets.get("ok_button")
        if seconds_input is not None:
            seconds_input.set_enabled(not running)
        if um_input is not None:
            um_input.set_enabled(not running)
        if ok_button is not None:
            ok_button.set_enabled(not running)

    def _on_field_blur(self, field_name: str, widget: ui.input | ui.textarea) -> None:
        """Update metadata when field loses focus or Enter is pressed.

        Emits MetadataUpdate(phase="intent") event with the field update.

        Args:
            field_name: Name of the field being updated.
            widget: The widget that triggered the update.
        """
        if not self._current_file:
            # logger.debug(f'pyinstaller no current file self._current_file:{self._current_file}')
            return

        # Get value from widget
        value = widget.value

        # logger.debug(f'pyinstaller field_name={field_name} widget={widget}value={value}')

        # Parse value based on field type (some header fields are lists)
        # For now, we'll pass the string value and let update_header() handle parsing
        # In the future, we might want to add type-aware parsing here

        # Emit intent event
        self._on_metadata_update(
            MetadataUpdate(
                file=self._current_file,
                metadata_type="header",
                fields={field_name: value},
                origin=SelectionOrigin.EXTERNAL,
                phase="intent",
            )
        )
    
    def _is_kym_image_with_2d_voxels(self, file: KymImage | None) -> bool:
        """Check if file is KymImage with 2D voxels.
        
        Args:
            file: KymImage instance to check, or None.
            
        Returns:
            True if file has header with voxels of length 2, False otherwise.
        """
        if file is None:
            return False
        if not hasattr(file, "header"):
            return False
        header = file.header
        if header is None or header.voxels is None:
            return False
        return len(header.voxels) == 2
    
    def _validate_physical_units(self, seconds_per_line: float | str, um_per_pixel: float | str) -> tuple[float, float] | None:
        """Validate and parse physical units values.
        
        Args:
            seconds_per_line: Seconds per line value (float or string).
            um_per_pixel: Micrometers per pixel value (float or string).
            
        Returns:
            Tuple of (seconds_per_line, um_per_pixel) if valid, None otherwise.
        """
        try:
            sec_val = float(seconds_per_line)
            um_val = float(um_per_pixel)
            if sec_val <= 0 or um_val <= 0:
                logger.warning("Physical units must be positive: seconds_per_line=%s, um_per_pixel=%s", sec_val, um_val)
                return None
            return (sec_val, um_val)
        except (ValueError, TypeError) as e:
            logger.warning("Invalid physical units values: seconds_per_line=%s, um_per_pixel=%s, error=%s", seconds_per_line, um_per_pixel, e)
            return None
    
    def _on_physical_units_ok(self, seconds_input: ui.number, um_input: ui.number) -> None:
        """Handle OK button click for physical units editing.
        
        Validates values and emits EditPhysicalUnits(phase="intent") event.
        
        Args:
            seconds_input: Number input widget for seconds per line.
            um_input: Number input widget for micrometers per pixel.
        """
        if not self._current_file:
            logger.warning("No file selected for physical units edit")
            return
        
        # Validate file is KymImage with 2D voxels
        if not self._is_kym_image_with_2d_voxels(self._current_file):
            logger.warning("File is not a KymImage with 2D voxels")
            return
        
        # Get values from inputs
        sec_val = seconds_input.value
        um_val = um_input.value
        
        # Validate values
        validated = self._validate_physical_units(sec_val, um_val)
        if validated is None:
            return
        
        sec_val, um_val = validated
        
        # Emit intent event if callback is available
        if self._on_edit_physical_units is not None:
            self._on_edit_physical_units(
                EditPhysicalUnits(
                    file=self._current_file,
                    seconds_per_line=sec_val,
                    um_per_pixel=um_val,
                    origin=SelectionOrigin.EXTERNAL,
                    phase="intent",
                )
            )
        else:
            logger.warning("No callback registered for EditPhysicalUnits events")