"""Controller for syncing velocity event cache whenever kym events change (add/delete/update/detect)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from kymflow.core.utils.logging import get_logger
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.events import DetectEvents, KymEvent
from kymflow.gui_v2.events_state import VelocityEventDbUpdated
from kymflow.gui_v2.state import AppState

if TYPE_CHECKING:
    from kymflow.gui_v2.app_context import AppContext

logger = get_logger(__name__)


class KymEventCacheSyncController:
    """Sync velocity event cache whenever kym events change (add/delete/update/detect).

    Subscribes to state events. Ensures Pool Plot (Velocity Events) reflects current
    runtime state, including unsaved changes.

    During batch kym-event analysis, :attr:`AppContext.suppress_velocity_event_cache_sync_on_detect_events`
    is set so per-file :class:`DetectEvents` (state) from the batch does not touch the
    in-memory DB or emit :class:`VelocityEventDbUpdated` until the batch finalizes.

    Attributes:
        _app_state: Application state (file list, selection).
        _bus: Event bus.
        _app_context: Application context (suppression flag).
    """

    def __init__(self, app_state: AppState, bus: EventBus, app_context: "AppContext") -> None:
        """Initialize and subscribe to state-phase kym-event and detect-events notifications.

        Args:
            app_state: Shared application state.
            bus: Per-client event bus.
            app_context: Application context (batch suppression flag).
        """
        self._app_state = app_state
        self._bus = bus
        self._app_context = app_context
        for evt in (KymEvent, DetectEvents):
            bus.subscribe_state(evt, self._on_kym_event_mutated)

    def _on_kym_event_mutated(
        self,
        e: KymEvent | DetectEvents,
    ) -> None:
        if (
            isinstance(e, DetectEvents)
            and self._app_context.suppress_velocity_event_cache_sync_on_detect_events
        ):
            return
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
