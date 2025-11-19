from __future__ import annotations

from nicegui import ui

from kymflow_core.kym_file import ExperimentMetadata
from kymflow_core.state import AppState


def create_metadata_form(app_state: AppState) -> None:
    """Create metadata form dynamically from ExperimentMetadata schema."""
    ui.label("Experimental Metadata").classes("font-semibold")
    
    # Get schema from backend (no NiceGUI knowledge in schema)
    schema = ExperimentMetadata.form_schema()
    
    # Filter to only visible fields
    visible_schema = [f for f in schema if f.get("visible", True)]
    
    # Create lookup dictionaries for editable/read-only fields
    editable_fields = {f["name"]: f for f in visible_schema if f["editable"]}
    read_only_fields = {f["name"]: f for f in visible_schema if not f["editable"]}
    
    # Create widgets dynamically based on schema (preserve order)
    widgets = {}
    with ui.grid(columns=3).classes("w-full gap-2"):
        # Iterate through visible schema in order to preserve field ordering
        for field_def in visible_schema:
            widget_classes = "w-full"
            if field_def["grid_span"] == 2:
                widget_classes += " col-span-2"
            
            # Create widget based on type and editability
            if field_def["widget_type"] == "multiline":
                widget = ui.textarea(field_def["label"]).classes(widget_classes)
            else:  # text, etc.
                widget = ui.input(field_def["label"]).classes(widget_classes)
            
            # Disable read-only fields
            if not field_def["editable"]:
                widget.set_enabled(False)
            
            widgets[field_def["name"]] = widget

    def _populate_fields(kf) -> None:
        """Populate form fields from KymFile metadata."""
        if not kf:
            for widget in widgets.values():
                widget.set_value("")
            return
        
        meta = kf.experiment_metadata
        # Use get_editable_values() for editable fields
        editable_values = meta.get_editable_values()
        for field_name, value in editable_values.items():
            if field_name in widgets:
                widgets[field_name].set_value(str(value))
        
        # Populate read-only fields
        for field_name, field_def in read_only_fields.items():
            if field_name in widgets:
                value = getattr(meta, field_name) or ""
                widgets[field_name].set_value(str(value))

    @app_state.selection_changed.connect
    def _on_selection(kf, origin) -> None:
        _populate_fields(kf)

    def _save() -> None:
        """Save metadata from form widgets."""
        kf = app_state.selected_file
        if not kf:
            ui.notify("Select a file first", color="warning")
            return
        
        # Build kwargs from editable widgets only
        updates = {}
        for field_name, widget in widgets.items():
            if field_name in editable_fields:
                updates[field_name] = widget.value
        
        kf.update_experiment_metadata(**updates)
        app_state.notify_metadata_changed(kf)
        ui.notify("Metadata updated", color="positive")

    ui.button("Save metadata", on_click=_save).classes("w-full mt-2")
