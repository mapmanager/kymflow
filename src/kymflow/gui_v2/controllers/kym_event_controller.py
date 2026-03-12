"""Unified controller for velocity (kym) event CRUD intents.

This controller consolidates intent-phase handling for velocity event
creation and deletion, replacing the older AddKymEventController and
DeleteKymEventController classes.

The controller:
  * Listens for AddKymEvent(intent) and DeleteKymEvent(intent) on the bus.
  * Resolves the target KymImage from AppState (by explicit path when
    provided, or via the currently selected file).
  * Applies the requested mutation to the underlying KymAnalysis object.
  * Emits corresponding state-phase AddKymEvent/DeleteKymEvent events so
    any existing listeners (e.g., cache sync) continue to work.
  * Emits FileChanged(state, change_type="analysis") to signal that the
    analysis metadata for a file has changed, allowing views and tables
    to refresh derived information (e.g., event counts).

Google-style docstrings are used for all public methods, and complex
logic is documented with inline comments.
"""

from __future__ import annotations

from typing import Optional

from kymflow.core.utils.logging import get_logger
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.events import (
    AddKymEvent,
    DeleteKymEvent,
    FileChanged,
    SelectionOrigin,
)
from kymflow.gui_v2.state import AppState


logger = get_logger(__name__)


class KymEventController:
    """Controller that handles velocity (kym) event CRUD intents.

    This controller subscribes to AddKymEvent and DeleteKymEvent intent-phase
    events from the GUI, mutates the underlying KymAnalysis objects associated
    with KymImage instances, and then emits state-phase events plus a
    FileChanged(state, change_type="analysis") notification so that views and
    cache-sync logic can react.

    Attributes:
        _app_state: Application state used to resolve files and selections.
        _bus: Event bus used to subscribe to intents and emit state events.
    """

    def __init__(self, app_state: AppState, bus: EventBus) -> None:
        """Initialize the unified kym event controller.

        The controller immediately subscribes to AddKymEvent and DeleteKymEvent
        intent-phase events on the provided event bus.

        Args:
            app_state: Shared AppState instance for the current GUI session.
            bus: EventBus used for subscribing to intents and emitting state.
        """
        self._app_state: AppState = app_state
        self._bus: EventBus = bus

        bus.subscribe_intent(AddKymEvent, self._on_add_event)
        bus.subscribe_intent(DeleteKymEvent, self._on_delete_event)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_file(self, path: Optional[str]):
        """Resolve a KymImage from an explicit path or the selected file.

        This helper encapsulates the common pattern for looking up the
        KymImage that a kym event mutation should apply to.

        Args:
            path: Optional filesystem path for the file that owns the
                velocity events. When None, the currently selected file
                from AppState is used instead.

        Returns:
            The resolved KymImage instance, or None if no matching file is
            available in the current AppState.
        """
        return self._app_state.get_file_by_path_or_selected(path)

    def _emit_file_changed(self, kym_file) -> None:
        """Emit a FileChanged(state) event for analysis-related changes.

        This helper standardizes the FileChanged emission for velocity
        event mutations so that any interested bindings or controllers
        can respond by pulling updated analysis state.

        Args:
            kym_file: The KymImage instance whose analysis has changed.
        """
        self._bus.emit(
            FileChanged(
                file=kym_file,
                change_type="analysis",
                origin=SelectionOrigin.EXTERNAL,
            )
        )

    # ------------------------------------------------------------------
    # Intent handlers
    # ------------------------------------------------------------------

    def _on_add_event(self, e: AddKymEvent) -> None:
        """Handle AddKymEvent intent events.

        This handler validates the event origin, resolves the target file,
        and delegates creation of a new velocity event to the file's
        KymAnalysis object. It then emits:

        * AddKymEvent(state) with the created event_id, and
        * FileChanged(state, change_type="analysis") for downstream
          consumers such as cache sync and views.

        Args:
            e: AddKymEvent instance with roi_id, t_start, t_end, and origin.
        """
        if e.origin != SelectionOrigin.EVENT_TABLE:
            # Only events originating from the event table are handled here,
            # to avoid interfering with any future alternate flows.
            return

        kym_file = self._resolve_file(e.path)
        if kym_file is None:
            logger.warning("AddKymEvent: no file available (path=%s)", e.path)
            return

        try:
            # Delegate actual creation to the KymAnalysis attached to the file.
            event_id = kym_file.get_kym_analysis().add_velocity_event(
                roi_id=e.roi_id,
                t_start=e.t_start,
                t_end=e.t_end,
            )

            # Mirror the mutation as a state-phase AddKymEvent so any existing
            # listeners (e.g., cache sync, bindings) continue to work.
            self._bus.emit(
                AddKymEvent(
                    event_id=event_id,
                    roi_id=e.roi_id,
                    path=e.path,
                    t_start=e.t_start,
                    t_end=e.t_end,
                    origin=e.origin,
                    phase="state",
                )
            )

            # Notify the rest of the app that this file's analysis has changed.
            self._emit_file_changed(kym_file)
        except ValueError as exc:
            logger.warning("AddKymEvent: failed to create event: %s", exc)

    def _on_delete_event(self, e: DeleteKymEvent) -> None:
        """Handle DeleteKymEvent intent events.

        This handler validates the event origin, resolves the target file,
        and asks the file's KymAnalysis object to delete the requested
        velocity event. If the deletion succeeds, it emits:

        * DeleteKymEvent(state) mirroring the deleted event, and
        * FileChanged(state, change_type="analysis") so that caches and
          views can refresh derived state.

        Args:
            e: DeleteKymEvent instance with event_id, optional roi_id/path,
                and origin.
        """
        if e.origin != SelectionOrigin.EVENT_TABLE:
            return

        logger.debug("DeleteKymEvent intent event_id=%s", e.event_id)

        kym_file = self._resolve_file(e.path)
        if kym_file is None:
            logger.warning("DeleteKymEvent: no file available (path=%s)", e.path)
            return

        deleted = kym_file.get_kym_analysis().delete_velocity_event(e.event_id)
        if not deleted:
            # If the event is missing, log a warning but do not emit any
            # state-phase events because there was no actual change.
            logger.warning(
                "DeleteKymEvent: event not found (event_id=%s, path=%s)",
                e.event_id,
                e.path,
            )
            return

        logger.debug("DeleteKymEvent: deleted event_id=%s", e.event_id)

        self._bus.emit(
            DeleteKymEvent(
                event_id=e.event_id,
                roi_id=e.roi_id,
                path=e.path,
                origin=e.origin,
                phase="state",
            )
        )
        self._emit_file_changed(kym_file)

