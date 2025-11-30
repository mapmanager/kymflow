from __future__ import annotations

from nicegui import ui

from kymflow_core.kym_file import AnalysisParameters
from kymflow_core.state import AppState


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

    def _populate_fields(kf) -> None:
        """Populate form fields from KymFile analysis parameters."""
        if not kf:
            for widget in widgets.values():
                widget.set_value("")
            return

        analysis_params = kf.analysis_parameters

        # Populate all fields
        for field_name, field_def in read_only_fields.items():
            if field_name in widgets:
                value = getattr(analysis_params, field_name)
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

    @app_state.selection_changed.connect
    def _on_selection(kf, origin) -> None:
        _populate_fields(kf)
