"""Options tab view component.

This module provides a view component that displays app configuration options
with dynamically generated widgets based on AppConfig field metadata.
"""

from __future__ import annotations

from typing import Any

from nicegui import ui

from kymflow.core.utils.logging import get_logger
from kymflow.gui_v2.app_config import AppConfig

logger = get_logger(__name__)


class OptionsTabView:
    """Options tab view component (app configuration editor)."""

    def __init__(self, app_config: AppConfig) -> None:
        """Initialize options tab view.

        Args:
            app_config: AppConfig instance to read/write settings.
        """
        self._app_config = app_config

    def render(self) -> None:
        """Create the Options tab UI inside the current container."""
        ui.label("App Settings").classes("text-lg font-semibold")
        ui.label("Changes require app restart to take effect.").classes("text-sm text-gray-500 mb-4")

        # Get all fields with metadata
        fields_info = self._app_config.get_all_fields_with_metadata()

        for field_name, field_info in fields_info.items():
            metadata = field_info["metadata"]
            current_value = field_info["value"]
            widget_type = metadata.get("widget_type", "input")
            label = metadata.get("label", field_name.replace("_", " ").title())

            with ui.row().classes("w-full items-center gap-4 mb-4"):
                ui.label(label).classes("min-w-32 text-sm")
                widget = self._create_widget_from_metadata(
                    field_name=field_name,
                    metadata=metadata,
                    current_value=current_value,
                )
                widget.classes("flex-1")

                # Show restart notification if required
                if metadata.get("requires_restart", False):
                    ui.label("(restart required)").classes("text-xs text-gray-400")

    def _create_widget_from_metadata(
        self, field_name: str, metadata: dict[str, Any], current_value: Any
    ) -> ui.element:
        """Create a NiceGUI widget from field metadata.

        Args:
            field_name: Name of the field
            metadata: Metadata dict with widget_type, options, etc.
            current_value: Current value of the field

        Returns:
            NiceGUI widget element
        """
        widget_type = metadata.get("widget_type", "input")

        if widget_type == "select":
            options = metadata.get("options", [])
            if not options:
                logger.warning(f"No options provided for select widget '{field_name}'")
                options = [str(current_value)] if current_value else []

            # Convert to dict format for ui.select
            options_dict = {opt: opt for opt in options}

            widget = ui.select(
                options=options_dict,
                value=current_value,
                on_change=lambda e, fn=field_name: self._on_value_change(fn, e.value),
            )
            return widget

        elif widget_type == "number":
            min_val = metadata.get("min")
            max_val = metadata.get("max")
            step = metadata.get("step", 1.0)

            widget = ui.number(
                value=float(current_value) if current_value is not None else 0.0,
                min=min_val,
                max=max_val,
                step=step,
                on_change=lambda e, fn=field_name: self._on_value_change(fn, e.value),
            )
            return widget

        elif widget_type == "slider":
            min_val = metadata.get("min", 0.0)
            max_val = metadata.get("max", 100.0)
            step = metadata.get("step", 1.0)

            widget = ui.slider(
                value=float(current_value) if current_value is not None else min_val,
                min=min_val,
                max=max_val,
                step=step,
                on_change=lambda e, fn=field_name: self._on_value_change(fn, e.value),
            )
            return widget

        elif widget_type == "checkbox":
            widget = ui.checkbox(
                value=bool(current_value) if current_value is not None else False,
                on_change=lambda e, fn=field_name: self._on_value_change(fn, e.value),
            )
            return widget

        elif widget_type == "input":
            widget = ui.input(
                value=str(current_value) if current_value is not None else "",
                on_change=lambda e, fn=field_name: self._on_value_change(fn, e.value),
            )
            return widget

        else:
            logger.warning(f"Unknown widget_type '{widget_type}' for field '{field_name}', using input")
            widget = ui.input(
                value=str(current_value) if current_value is not None else "",
                on_change=lambda e, fn=field_name: self._on_value_change(fn, e.value),
            )
            return widget

    def _on_value_change(self, field_name: str, new_value: Any) -> None:
        """Handle value change from widget.

        Args:
            field_name: Name of the field being changed
            new_value: New value from the widget
        """
        try:
            self._app_config.set_attribute(field_name, new_value)
            logger.info(f"App config updated: {field_name} = {new_value}")
        except (AttributeError, ValueError) as e:
            logger.error(f"Failed to update app config '{field_name}': {e}")
            ui.notify(f"Invalid value for {field_name}: {e}", type="negative")
