from __future__ import annotations

from nicegui import ui

from kymflow.core.kym_file import ExperimentMetadata
from kymflow.core.state_v2 import AppState


def create_metadata_form(app_state: AppState) -> None:
    """Create metadata form dynamically from ExperimentMetadata schema."""
    ui.label("Experimental Metadata").classes("font-semibold")

    # Get schema from backend (no NiceGUI knowledge in schema)
    schema = ExperimentMetadata.form_schema()

    # Filter to only visible fields
    visible_schema = [f for f in schema if f.get("visible", True)]

    # Create lookup dictionary for read-only fields (for population)
    read_only_fields = {f["name"]: f for f in visible_schema if not f["editable"]}

    # Create widgets dynamically based on schema (preserve order)
    widgets = {}

    def _on_field_blur(field_name: str, widget) -> None:
        """Update metadata when field loses focus or Enter is pressed."""
        kf = app_state.selected_file
        if not kf:
            return

        # Update the specific field
        value = widget.value
        kf.update_experiment_metadata(**{field_name: value})
        app_state.notify_metadata_changed(kf)
        # Refresh file table to show updated metadata (e.g., note field)
        app_state.refresh_file_rows()

    with ui.grid(columns=3).classes("w-full gap-2"):
        # Iterate through visible schema in order to preserve field ordering
        for field_def in visible_schema:
            widget_classes = "w-full"
            if field_def["grid_span"] == 2:
                widget_classes += " col-span-2"

            field_name = field_def["name"]
            is_editable = field_def["editable"]

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
                    "blur", lambda field=field_name, w=widget: _on_field_blur(field, w)
                )
                # Enter key event (only for input, not textarea)
                if field_def["widget_type"] != "multiline":
                    widget.on(
                        "keydown.enter",
                        lambda field=field_name, w=widget: _on_field_blur(field, w),
                    )

            widgets[field_name] = widget

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

    def _on_selection(kf, origin) -> None:
        _populate_fields(kf)
    
    # Register callback (no decorator - explicit registration)
    app_state.on_selection_changed(_on_selection)

    # Commented out: replaced with auto-save on blur/enter
    # def _save() -> None:
    #     """Save metadata from form widgets."""
    #     kf = app_state.selected_file
    #     if not kf:
    #         ui.notify("Select a file first", color="warning")
    #         return
    #
    #     # Build kwargs from editable widgets only
    #     updates = {}
    #     for field_name, widget in widgets.items():
    #         if field_name in editable_fields:
    #             updates[field_name] = widget.value
    #
    #     kf.update_experiment_metadata(**updates)
    #     app_state.notify_metadata_changed(kf)
    #     ui.notify("Metadata updated", color="positive")

    # ui.button("Save metadata", on_click=_save).classes("w-full mt-2")
