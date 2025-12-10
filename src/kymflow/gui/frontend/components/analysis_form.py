from __future__ import annotations

from nicegui import ui

from kymflow.core.metadata import AnalysisParameters
from kymflow.gui.state import AppState


def create_analysis_form(app_state: AppState) -> None:
    """Create Analysis Parameters form dynamically from AnalysisParameters schema."""
    ui.label("Analysis Parameters").classes("font-semibold")

    # Get schema from backend (no NiceGUI knowledge in schema)
    schema = AnalysisParameters.form_schema()

    # Filter to only visible fields
    visible_schema = [f for f in schema if f.get("visible", True)]

    # All fields are read-only
    read_only_fields = {f["name"]: f for f in visible_schema}

    # Create widgets dynamically based on schema (preserve order)
    widgets = {}
    with ui.grid(columns=3).classes("w-full gap-2"):
        # Iterate through visible schema in order to preserve field ordering
        for field_def in visible_schema:
            widget_classes = "w-full"
            if field_def["grid_span"] == 2:
                widget_classes += " col-span-2"

            # Create widget based on type
            if field_def["widget_type"] == "multiline":
                widget = ui.textarea(field_def["label"]).classes(widget_classes)
            else:  # text, etc.
                widget = ui.input(field_def["label"]).classes(widget_classes)

            # All fields are read-only
            widget.set_enabled(False)

            widgets[field_def["name"]] = widget

    def _populate_fields() -> None:
        """Populate form fields from selected ROI's analysis parameters."""
        kf = app_state.selected_file
        roi_id = app_state.selected_roi_id
        
        # Clear fields if no file or no ROI selected
        if not kf or roi_id is None or kf.kymanalysis is None:
            for widget in widgets.values():
                widget.set_value("")
            return

        # Get ROI and its analysis parameters
        roi = kf.kymanalysis.get_roi(roi_id)
        if not roi:
            for widget in widgets.values():
                widget.set_value("")
            return

        # Populate all fields from ROI's AnalysisParameters
        for field_name, field_def in read_only_fields.items():
            if field_name in widgets:
                value = getattr(roi, field_name)
                # Handle None, dict, datetime, and Path types
                if value is None:
                    widgets[field_name].set_value("")
                elif isinstance(value, dict):
                    # Convert dict to readable string format
                    import json

                    widgets[field_name].set_value(json.dumps(value, indent=2))
                elif hasattr(value, "isoformat"):  # datetime
                    widgets[field_name].set_value(value.isoformat())
                elif hasattr(value, "__str__"):  # Path or other objects
                    widgets[field_name].set_value(str(value))
                else:
                    widgets[field_name].set_value(str(value))

    def _on_selection(kf, origin) -> None:
        """Handle file selection change - update form if ROI is selected."""
        _populate_fields()
    
    def _on_roi_selection_change(roi_id) -> None:
        """Handle ROI selection change - update form with new ROI's parameters."""
        _populate_fields()
    
    # Register callbacks (no decorator - explicit registration)
    app_state.on_selection_changed(_on_selection)
    app_state.on_roi_selection_changed(_on_roi_selection_change)
    
    # Initial population if file/ROI already selected
    _populate_fields()
