"""Controller for handling metadata update events from the UI.

This module provides a controller that translates user metadata update intents
(MetadataUpdate phase="intent") into file updates and AppState notifications.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from kymflow.gui_v2.state import AppState
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.events import MetadataUpdate

if TYPE_CHECKING:
    pass


class MetadataController:
    """Apply metadata update events to files and AppState.

    This controller handles metadata update intent events from the UI (typically
    from metadata form widgets) and updates the file accordingly.

    Update Flow:
        1. User edits field → MetadataView emits MetadataUpdate(phase="intent")
        2. This controller receives event → calls file.update_experiment_metadata() or file.update_header()
        3. Controller calls app_state.update_metadata(file)
        4. AppState callback → AppStateBridge emits MetadataUpdate(phase="state")
        5. MetadataBindings receive event and refresh views

    Attributes:
        _app_state: AppState instance to update.
    """

    def __init__(self, app_state: AppState, bus: EventBus) -> None:
        """Initialize metadata controller.

        Subscribes to MetadataUpdate (phase="intent") events from the bus.

        Args:
            app_state: AppState instance to update.
            bus: EventBus instance to subscribe to.
        """
        self._app_state: AppState = app_state
        bus.subscribe_intent(MetadataUpdate, self._on_metadata_update)

    def _on_metadata_update(self, e: MetadataUpdate) -> None:
        """Handle MetadataUpdate intent event.

        Updates the file's metadata and notifies AppState.

        Args:
            e: MetadataUpdate event (phase="intent") containing the file, metadata type, and fields.
        """
        if e.metadata_type == "experimental":
            e.file.update_experiment_metadata(**e.fields)
        elif e.metadata_type == "header":
            e.file.update_header(**e.fields)
        else:
            # Unknown metadata type - log warning but don't crash
            from kymflow.core.utils.logging import get_logger
            logger = get_logger(__name__)
            logger.warning(f"Unknown metadata type: {e.metadata_type}")

        # Notify AppState that metadata was updated
        self._app_state.update_metadata(e.file)
