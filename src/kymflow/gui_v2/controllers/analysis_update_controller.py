"""Controller for handling analysis update events from the UI.

This module provides a controller that translates user analysis update intents
(AnalysisUpdate phase="intent") into kymanalysis updates and AppState notifications.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from kymflow.gui_v2.state import AppState
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.events import AnalysisUpdate

if TYPE_CHECKING:
    pass


class AnalysisUpdateController:
    """Apply analysis update events to kymanalysis and AppState.

    This controller handles analysis update intent events from the UI (typically
    from file table view when user toggles accepted checkbox) and updates the
    kymanalysis accordingly.

    Update Flow:
        1. User edits analysis field → FileTableView emits AnalysisUpdate(phase="intent")
        2. This controller receives event → calls kymanalysis.set_accepted() etc.
        3. Controller calls app_state.update_analysis(file)
        4. AppState callback → AppStateBridge emits AnalysisUpdate(phase="state")
        5. FileTableBindings receive event and refresh views

    Attributes:
        _app_state: AppState instance to update.
    """

    def __init__(self, app_state: AppState, bus: EventBus) -> None:
        """Initialize analysis update controller.

        Subscribes to AnalysisUpdate (phase="intent") events from the bus.

        Args:
            app_state: AppState instance to update.
            bus: EventBus instance to subscribe to.
        """
        self._app_state: AppState = app_state
        bus.subscribe_intent(AnalysisUpdate, self._on_analysis_update)

    def _on_analysis_update(self, e: AnalysisUpdate) -> None:
        """Handle AnalysisUpdate intent event.

        Updates the file's kymanalysis attributes and notifies AppState.

        Args:
            e: AnalysisUpdate event (phase="intent") containing the file and fields.
        """
        kym_analysis = e.file.get_kym_analysis()
        
        # Update accepted if present in fields
        if "accepted" in e.fields:
            kym_analysis.set_accepted(e.fields["accepted"])
        
        # Notify AppState that analysis was updated
        self._app_state.update_analysis(e.file)
