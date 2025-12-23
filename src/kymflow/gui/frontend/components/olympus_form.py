# This file is deprecated and will be replaced with an AcqImageHeader form in the future.
# Commented out to prevent import errors during migration.

# from __future__ import annotations
# 
# from nicegui import ui
# 
# # from kymflow.core.kym_file import OlympusHeader
# from kymflow.core.image_loaders.read_olympus_header import OlympusHeader
# from kymflow.gui.state import AppState
# 
# 
# def create_olympus_form(app_state: AppState) -> None:
#     """Create Olympus metadata form dynamically from OlympusHeader schema."""
#     ui.label("Olympus Metadata").classes("font-semibold")
# 
#     # Get schema from backend (no NiceGUI knowledge in schema)
#     schema = OlympusHeader.form_schema()
# 
#     # Filter to only visible fields
#     visible_schema = [f for f in schema if f.get("visible", True)]
# 
#     # All fields are read-only for now
#     read_only_fields = {f["name"]: f for f in visible_schema}
# 
#     # Create widgets dynamically based on schema (preserve order)
#     widgets = {}
#     with ui.grid(columns=3).classes("w-full gap-2"):
#         # Iterate through visible schema in order to preserve field ordering
#         for field_def in visible_schema:
#             widget_classes = "w-full"
#             if field_def["grid_span"] == 2:
#                 widget_classes += " col-span-2"
# 
#             # Create widget based on type
#             if field_def["widget_type"] == "multiline":
#                 widget = ui.textarea(field_def["label"]).classes(widget_classes)
#             else:  # text, etc.
#                 widget = ui.input(field_def["label"]).classes(widget_classes)
# 
#             # All fields are read-only initially
#             widget.set_enabled(False)
# 
#             widgets[field_def["name"]] = widget
# 
#     def _populate_fields(kf) -> None:
#         """Populate form fields from KymFile acquisition metadata."""
#         if not kf:
#             for widget in widgets.values():
#                 widget.set_value("")
#             return
# 
#         header = kf.acquisition_metadata
# 
#         # Populate all fields
#         for field_name, field_def in read_only_fields.items():
#             if field_name in widgets:
#                 value = getattr(header, field_name)
#                 # Handle None, dict, and other types
#                 if value is None:
#                     widgets[field_name].set_value("")
#                 elif isinstance(value, dict):
#                     widgets[field_name].set_value(str(value))
#                 else:
#                     widgets[field_name].set_value(str(value))
# 
#     def _on_selection(kf, origin) -> None:
#         _populate_fields(kf)
#     
#     # Register callback (no decorator - explicit registration)
#     app_state.on_selection_changed(_on_selection)
