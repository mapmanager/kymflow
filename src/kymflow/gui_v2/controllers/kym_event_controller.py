"""Unified controller for velocity (kym) event intents and range UI state.

This module consolidates intent-phase handling that was previously split across
``KymEventController``, ``VelocityEventUpdateController``, and
``KymEventRangeStateController``:

* **CRUD:** ``KymEvent`` (action ADD/EDIT/DELETE) — apply mutations to the file's
  kym analysis layer and emit state plus
  :class:`~kymflow.gui_v2.events.FileChanged` where applicable.
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
    FileChanged,
    KymEvent,
    KymEventAction,
    KymEventSelectionOptions,
    SelectionOrigin,
    SetKymEventRangeState,
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

    * ``KymEvent`` (intent) — mutates analysis and emits state for cache sync and views.
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

        bus.subscribe_intent(KymEvent, self._on_kym_event)
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

    def _select_new_velocity_event_after_add(
        self, kym_file, event_id: str, path: Optional[str]
    ) -> None:
        """Update AppState so bridge emits KymEventSelection(state); grid and line stay unified.

        Called after ``KymEvent(ADD)`` state and ``FileChanged`` so bindings refresh
        table data before selection state. Uses ``KymEventSelectionOptions(zoom=False)``
        (no zoom padding).

        Args:
            kym_file: File that owns the new event.
            event_id: UUID returned from ``add_velocity_event``.
            path: Path from the add intent (fallback if ``kym_file.path`` is unset).
        """
        found = kym_file.get_kym_analysis().find_event_by_uuid(event_id)
        if found is None:
            logger.warning(
                "KymEvent(ADD): find_event_by_uuid missing after add (event_id=%s)",
                event_id,
            )
            return
        roi_id, _channel, _index, velocity_event = found
        file_path = str(kym_file.path) if getattr(kym_file, "path", None) else path
        options = KymEventSelectionOptions(zoom=False)
        self._app_state.select_velocity_event(
            event_id=event_id,
            roi_id=roi_id,
            path=file_path,
            event=velocity_event,
            options=options,
            origin=SelectionOrigin.EXTERNAL,
        )

    def _on_kym_event(self, e: KymEvent) -> None:
        """Handle ``KymEvent`` intent: ADD, EDIT, or DELETE."""
        if not _crud_origin_allowed(e.origin):
            return
        if e.action == KymEventAction.ADD:
            self._on_kym_event_add(e)
        elif e.action == KymEventAction.EDIT:
            self._on_kym_event_edit(e)
        elif e.action == KymEventAction.DELETE:
            self._on_kym_event_delete(e)

    def _on_kym_event_add(self, e: KymEvent) -> None:
        if e.roi_id is None:
            return
        kym_file = self._resolve_file(e.path)
        if kym_file is None:
            logger.warning("KymEvent(ADD): no file available (path=%s)", e.path)
            return
        if e.t_start is None:
            return
        try:
            event_id = kym_file.get_kym_analysis().add_velocity_event(
                roi_id=e.roi_id,
                channel=e.channel,
                t_start=e.t_start,
                t_end=e.t_end,
            )
            self._bus.emit(
                KymEvent(
                    action=KymEventAction.ADD,
                    event_id=event_id,
                    roi_id=e.roi_id,
                    path=e.path,
                    origin=e.origin,
                    phase="state",
                    t_start=e.t_start,
                    t_end=e.t_end,
                    channel=e.channel,
                )
            )
            self._emit_file_changed(kym_file)
            self._select_new_velocity_event_after_add(kym_file, event_id, e.path)
        except ValueError as exc:
            logger.warning("KymEvent(ADD): failed to create event: %s", exc)

    def _on_kym_event_delete(self, e: KymEvent) -> None:
        if e.event_id is None:
            return
        kym_file = self._resolve_file(e.path)
        if kym_file is None:
            logger.warning("KymEvent(DELETE): no file available (path=%s)", e.path)
            return
        deleted = kym_file.get_kym_analysis().delete_velocity_event(e.event_id)
        if not deleted:
            logger.warning(
                "KymEvent(DELETE): event not found (event_id=%s, path=%s)",
                e.event_id,
                e.path,
            )
            return
        self._bus.emit(
            KymEvent(
                action=KymEventAction.DELETE,
                event_id=e.event_id,
                roi_id=e.roi_id,
                path=e.path,
                origin=e.origin,
                phase="state",
            )
        )
        self._emit_file_changed(kym_file)

    def _on_kym_event_edit(self, e: KymEvent) -> None:
        if e.event_id is None:
            return
        kym_file = self._app_state.get_file_by_path_or_selected(e.path)
        if kym_file is None:
            return
        updates = e.updates
        if updates is None:
            if e.field is None:
                return
            updates = {e.field: e.value}
        new_event_id = e.event_id
        if "t_start" in updates and "t_end" in updates:
            new_event_id = kym_file.get_kym_analysis().update_velocity_event_range(
                event_id=e.event_id,
                t_start=updates["t_start"],
                t_end=updates["t_end"],
            )
            if new_event_id is None:
                logger.warning(
                    "KymEvent(EDIT): event not found (event_id=%s, path=%s)",
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
                        "KymEvent(EDIT): event not found (event_id=%s, path=%s)",
                        new_event_id,
                        e.path,
                    )
                    return
                new_event_id = result
        updated = kym_file.get_kym_analysis().find_event_by_uuid(new_event_id)
        velocity_event = updated[3] if updated is not None else None
        self._bus.emit(
            KymEvent(
                action=KymEventAction.EDIT,
                event_id=new_event_id,
                roi_id=e.roi_id,
                path=e.path,
                origin=e.origin,
                phase="state",
                updates=updates,
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
