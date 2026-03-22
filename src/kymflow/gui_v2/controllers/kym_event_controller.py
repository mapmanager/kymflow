"""Unified controller for velocity (kym) event intents and range UI state.

This module consolidates intent-phase handling that was previously split across
``KymEventController``, ``VelocityEventUpdateController``, and
``KymEventRangeStateController``:

* **CRUD:** ``AddKymEvent``, ``DeleteKymEvent``, ``VelocityEventUpdate`` — apply
  mutations to the file's kym analysis layer and emit
  state plus :class:`~kymflow.gui_v2.events.FileChanged` where applicable.
* **Range UI:** ``SetKymEventRangeState`` — mirror intent to state for plot
  bindings, then emit :class:`~kymflow.gui_v2.events_state.InteractionBlocked`
  so other views can disable chrome (file table, folder bar).

Google-style docstrings are used for public APIs; non-trivial branches include
inline comments.
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
    SetKymEventRangeState,
    VelocityEventUpdate,
)
from kymflow.gui_v2.events_state import BlockingMode, InteractionBlocked
from kymflow.gui_v2.state import AppState

logger = get_logger(__name__)


def _crud_origin_allowed(origin: SelectionOrigin) -> bool:
    """Return whether velocity-event CRUD from ``origin`` is handled.

    Today only :attr:`SelectionOrigin.EVENT_TABLE` is allowed. Extend this
    function when adding alternate flows (e.g. batch or API-driven edits).

    Args:
        origin: Selection origin from the intent event.

    Returns:
        ``True`` if the controller should process the CRUD intent.
    """
    return origin == SelectionOrigin.EVENT_TABLE


class KymEventController:
    """Handles kym velocity-event intents: CRUD, range UI mirror, interaction block.

    Subscribes to:

    * ``AddKymEvent``, ``DeleteKymEvent``, ``VelocityEventUpdate`` (intent) —
      mutates analysis and emits state for cache sync and views.
    * ``SetKymEventRangeState`` (intent) — mirrors to state and emits
      :class:`~kymflow.gui_v2.events_state.InteractionBlocked` (state).

    Attributes:
        _app_state: Application state used to resolve files and selections.
        _bus: Event bus for subscribing to intents and emitting state events.
    """

    def __init__(self, app_state: AppState, bus: EventBus) -> None:
        """Initialize the controller and subscribe to all kym-event intents.

        Args:
            app_state: Shared AppState for the current GUI session.
            bus: EventBus used for subscribing to intents and emitting state.
        """
        self._app_state: AppState = app_state
        self._bus: EventBus = bus

        bus.subscribe_intent(AddKymEvent, self._on_add_event)
        bus.subscribe_intent(DeleteKymEvent, self._on_delete_event)
        bus.subscribe_intent(VelocityEventUpdate, self._on_velocity_event_update)
        bus.subscribe_intent(SetKymEventRangeState, self._on_set_kym_event_range_state)

    def _resolve_file(self, path: Optional[str]):
        """Resolve a KymImage from an explicit path or the selected file.

        Args:
            path: Optional filesystem path for the file that owns velocity
                events. When ``None``, uses the currently selected file from
                ``AppState``.

        Returns:
            The resolved ``KymImage``, or ``None`` if none matches.
        """
        return self._app_state.get_file_by_path_or_selected(path)

    def _emit_file_changed(self, kym_file) -> None:
        """Emit ``FileChanged(state, change_type='analysis')`` for one file.

        Args:
            kym_file: The ``KymImage`` whose analysis was mutated.
        """
        self._bus.emit(
            FileChanged(
                file=kym_file,
                change_type="analysis",
                origin=SelectionOrigin.EXTERNAL,
            )
        )

    def _on_add_event(self, e: AddKymEvent) -> None:
        """Handle ``AddKymEvent`` intent: create event and emit state.

        Args:
            e: Intent event with ``roi_id``, ``t_start``, ``t_end``, and
                ``origin``.
        """
        if not _crud_origin_allowed(e.origin):
            return

        kym_file = self._resolve_file(e.path)
        if kym_file is None:
            logger.warning("AddKymEvent: no file available (path=%s)", e.path)
            return

        try:
            event_id = kym_file.get_kym_analysis().add_velocity_event(
                roi_id=e.roi_id,
                channel=e.channel,
                t_start=e.t_start,
                t_end=e.t_end,
            )

            self._bus.emit(
                AddKymEvent(
                    event_id=event_id,
                    roi_id=e.roi_id,
                    channel=e.channel,
                    path=e.path,
                    t_start=e.t_start,
                    t_end=e.t_end,
                    origin=e.origin,
                    phase="state",
                )
            )

            self._emit_file_changed(kym_file)
        except ValueError as exc:
            logger.warning("AddKymEvent: failed to create event: %s", exc)

    def _on_delete_event(self, e: DeleteKymEvent) -> None:
        """Handle ``DeleteKymEvent`` intent: delete event and emit state.

        Args:
            e: Intent event with ``event_id`` and optional ``roi_id`` / ``path``.
        """
        if not _crud_origin_allowed(e.origin):
            return

        logger.debug("DeleteKymEvent intent event_id=%s", e.event_id)

        kym_file = self._resolve_file(e.path)
        if kym_file is None:
            logger.warning("DeleteKymEvent: no file available (path=%s)", e.path)
            return

        deleted = kym_file.get_kym_analysis().delete_velocity_event(e.event_id)
        if not deleted:
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

    def _on_velocity_event_update(self, e: VelocityEventUpdate) -> None:
        """Handle ``VelocityEventUpdate`` intent: apply field/range updates.

        Args:
            e: Intent event with ``event_id``, optional ``updates`` or
                ``field``/``value``, and ``path``.
        """
        if not _crud_origin_allowed(e.origin):
            return
        logger.debug("VelocityEventUpdate intent event_id=%s", e.event_id)

        kym_file = self._app_state.get_file_by_path_or_selected(e.path)
        if kym_file is None:
            return

        updates = e.updates
        if updates is None:
            if e.field is None:
                return
            updates = {e.field: e.value}

        new_event_id = e.event_id

        # Atomic range update when both ends change (avoids event_id mismatch).
        if "t_start" in updates and "t_end" in updates:
            new_event_id = kym_file.get_kym_analysis().update_velocity_event_range(
                event_id=e.event_id,
                t_start=updates["t_start"],
                t_end=updates["t_end"],
            )
            if new_event_id is None:
                logger.warning(
                    "VelocityEventUpdate: event not found (event_id=%s, path=%s)",
                    e.event_id,
                    e.path,
                )
                return
        else:
            for field, value in updates.items():
                result = kym_file.get_kym_analysis().update_velocity_event_field(
                    event_id=new_event_id,
                    field=field,
                    value=value,
                )
                if result is None:
                    logger.warning(
                        "VelocityEventUpdate: event not found (event_id=%s, path=%s)",
                        new_event_id,
                        e.path,
                    )
                    return
                new_event_id = result

        updated = kym_file.get_kym_analysis().find_event_by_uuid(new_event_id)
        velocity_event = updated[3] if updated is not None else None

        self._bus.emit(
            VelocityEventUpdate(
                event_id=new_event_id,
                path=e.path,
                updates=updates,
                origin=e.origin,
                phase="state",
                velocity_event=velocity_event,
            )
        )
        self._emit_file_changed(kym_file)

    def _on_set_kym_event_range_state(self, e: SetKymEventRangeState) -> None:
        """Mirror ``SetKymEventRangeState`` intent to state and notify blocking.

        Emit order (same on enable and disable; plot bindings run before chrome):

            #. ``SetKymEventRangeState(phase="state")`` — image/line viewer arms
               or disarms draw-rect for the event range.
            #. ``InteractionBlocked(phase="state")`` — file table, folder bar,
               etc. update pointer/disabled state.

        Args:
            e: Intent event with ``enabled``, ``event_id``, ``roi_id``, ``path``.
        """
        self._bus.emit(
            SetKymEventRangeState(
                enabled=e.enabled,
                event_id=e.event_id,
                roi_id=e.roi_id,
                path=e.path,
                origin=e.origin,
                phase="state",
            )
        )
        mode = BlockingMode.KYM_EVENT_RANGE if e.enabled else BlockingMode.NONE
        self._bus.emit(
            InteractionBlocked(
                blocked=e.enabled,
                mode=mode,
                phase="state",
            )
        )
