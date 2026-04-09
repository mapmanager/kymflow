"""Confirm ROI delete/edit from the image viewer and clear dependent KymAnalysis.

Shows a NiceGUI dialog listing analysis dependencies (all channels for the ROI).
On OK: clears in-memory analysis via :meth:`KymAnalysis.clear_all_analysis_for_roi`,
then emits the original intent on the bus for :class:`~kymflow.gui_v2.controllers.roi_controller.RoiController`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from nicegui import ui

from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.core.utils.logging import get_logger
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.events import DeleteRoi, EditRoi, SelectionOrigin

if TYPE_CHECKING:
    from kymflow.gui_v2.state import AppState

logger = get_logger(__name__)


def resolve_kym_image_for_viewer_intent(
    app_state: "AppState",
    path: str | None,
) -> KymImage | None:
    """Resolve the current KymImage when handling a viewer ROI intent.

    Requires a selected file. If ``path`` is set, it must match the selected
    file's path (no silent fallback to another file).

    Args:
        app_state: Application state.
        path: Path from the intent, or None.

    Returns:
        Selected ``KymImage`` when valid; otherwise None.
    """
    selected = app_state.selected_file
    if selected is None:
        logger.warning("ROI intent: no selected file")
        return None
    if path is not None:
        if selected.path is None:
            logger.warning(
                "ROI intent: event path=%s but selected file has no path",
                path,
            )
            return None
        if str(selected.path) != str(path):
            logger.warning(
                "ROI intent: path mismatch selected=%s event=%s",
                selected.path,
                path,
            )
            return None
    return selected


def build_roi_mutation_message(
    *,
    operation: str,
    roi_id: int,
    deps: list[dict],
) -> tuple[str, str]:
    """Build dialog title and body for delete or edit confirmation.

    Args:
        operation: ``\"delete\"`` or ``\"edit\"``.
        roi_id: ROI id for display.
        deps: Output of :meth:`KymAnalysis.get_roi_dependencies_all_channels`.

    Returns:
        ``(title, body)`` strings for the dialog.
    """
    if operation == "delete":
        title = f"Delete ROI {roi_id}?"
    else:
        title = f"Apply edit to ROI {roi_id}?"

    if deps:
        lines = [
            "The following in-memory analysis will be removed for this ROI (all channels). "
            "Changes are not saved to disk until you save the file.",
            "",
        ]
        for d in deps:
            name = d.get("analysis_name", "?")
            ch = d.get("channel", "?")
            lines.append(f"• {name} (channel {ch})")
    else:
        lines = [
            "No analysis is registered for this ROI in the current session.",
            "",
            "The ROI will still be "
            + ("removed." if operation == "delete" else "updated (geometry will change)."),
        ]

    body = "\n".join(lines)
    return title, body


def _emit_after_clear(kym: KymImage, roi_id: int, bus: EventBus, emit: Callable[[], None]) -> None:
    """Clear all analysis for ``roi_id`` then run ``emit`` (typically ``bus.emit``)."""
    kym.get_kym_analysis().clear_all_analysis_for_roi(roi_id)
    emit()


def confirm_delete_roi_intent(app_state: "AppState", bus: EventBus, e: DeleteRoi) -> None:
    """Open confirmation dialog; on OK clear analysis and emit ``DeleteRoi`` intent."""
    if e.phase != "intent" or e.origin != SelectionOrigin.IMAGE_VIEWER:
        bus.emit(e)
        return

    kym = resolve_kym_image_for_viewer_intent(app_state, e.path)
    if kym is None:
        return
    if kym.rois.get(e.roi_id) is None:
        logger.warning(
            "DeleteRoi intent: ROI %s not found on selected file",
            e.roi_id,
        )
        return

    deps = kym.get_kym_analysis().get_roi_dependencies_all_channels(e.roi_id)
    title, body = build_roi_mutation_message(operation="delete", roi_id=e.roi_id, deps=deps)

    def _apply() -> None:
        _emit_after_clear(kym, e.roi_id, bus, lambda: bus.emit(e))

    with ui.dialog() as dialog, ui.card():
        ui.label(title).classes("text-h6")
        ui.label(body).classes("whitespace-pre-wrap text-body2")
        with ui.row():

            def _on_ok_delete() -> None:
                dialog.close()
                _apply()

            ui.button("Cancel", on_click=dialog.close)
            ui.button("Delete ROI", on_click=_on_ok_delete).props("color=negative")
    dialog.open()


def confirm_edit_roi_intent(app_state: "AppState", bus: EventBus, e: EditRoi) -> None:
    """Open confirmation dialog; on OK clear analysis and emit ``EditRoi`` intent."""
    if e.phase != "intent" or e.origin != SelectionOrigin.IMAGE_VIEWER:
        bus.emit(e)
        return

    kym = resolve_kym_image_for_viewer_intent(app_state, e.path)
    if kym is None:
        return
    if kym.rois.get(e.roi_id) is None:
        logger.warning(
            "EditRoi intent: ROI %s not found on selected file",
            e.roi_id,
        )
        return

    deps = kym.get_kym_analysis().get_roi_dependencies_all_channels(e.roi_id)
    title, body = build_roi_mutation_message(operation="edit", roi_id=e.roi_id, deps=deps)

    def _apply() -> None:
        _emit_after_clear(kym, e.roi_id, bus, lambda: bus.emit(e))

    with ui.dialog() as dialog, ui.card():
        ui.label(title).classes("text-h6")
        ui.label(body).classes("whitespace-pre-wrap text-body2")
        with ui.row():

            def _on_ok_edit() -> None:
                dialog.close()
                _apply()

            ui.button("Cancel", on_click=dialog.close)
            ui.button("Apply edit", on_click=_on_ok_edit)
    dialog.open()
