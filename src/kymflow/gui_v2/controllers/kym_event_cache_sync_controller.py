"""Controller for syncing velocity event cache whenever kym events change (add/delete/update/detect)."""

from __future__ import annotations

from kymflow.core.utils.logging import get_logger
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.events import AddKymEvent, DeleteKymEvent, DetectEvents, VelocityEventUpdate
from kymflow.gui_v2.events_state import VelocityEventDbUpdated
from kymflow.gui_v2.state import AppState

logger = get_logger(__name__)


class KymEventCacheSyncController:
    """Sync velocity event cache whenever kym events change (add/delete/update/detect).

    Subscribes to state events. Ensures Pool Plot (Velocity Events) reflects current
    runtime state, including unsaved changes.
    """

    def __init__(self, app_state: AppState, bus: EventBus) -> None:
        self._app_state = app_state
        self._bus = bus
        for evt in (AddKymEvent, DeleteKymEvent, VelocityEventUpdate, DetectEvents):
            bus.subscribe_state(evt, self._on_kym_event_mutated)

    def _on_kym_event_mutated(
        self,
        e: AddKymEvent | DeleteKymEvent | VelocityEventUpdate | DetectEvents,
    ) -> None:
        path = getattr(e, "path", None)
        kym_file = self._app_state.get_file_by_path_or_selected(path)
        if kym_file is None:
            return
        if not hasattr(self._app_state.files, "update_velocity_event_cache_only"):
            return
        try:
            self._app_state.files.update_velocity_event_cache_only(kym_file)
            self._bus.emit(VelocityEventDbUpdated())
        except Exception as ex:
            logger.warning("KymEventCacheSync: update failed: %s", ex)
