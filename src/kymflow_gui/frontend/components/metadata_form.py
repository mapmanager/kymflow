from __future__ import annotations

from nicegui import ui

from kymflow_core.state import AppState


def create_metadata_form(app_state: AppState) -> None:
    ui.label("Metadata").classes("text-lg font-semibold")
    species = ui.input("Species").classes("w-full")
    cell_type = ui.input("Cell type").classes("w-full")
    region = ui.input("Region").classes("w-full")
    note = ui.textarea("Note").classes("w-full")

    def _populate_fields(kf) -> None:
        if not kf:
            for widget in (species, cell_type, region, note):
                widget.set_value("")
            return
        meta = kf.biology_metadata
        species.set_value(meta.species or "")
        cell_type.set_value(meta.cell_type or "")
        region.set_value(meta.region or "")
        note.set_value(meta.note or "")

    @app_state.selection_changed.connect
    def _on_selection(kf, origin) -> None:
        _populate_fields(kf)

    def _save() -> None:
        kf = app_state.selected_file
        if not kf:
            ui.notify("Select a file first", color="warning")
            return
        kf.update_biology_metadata(
            species=species.value,
            cell_type=cell_type.value,
            region=region.value,
            note=note.value,
        )
        app_state.notify_metadata_changed(kf)
        ui.notify("Metadata updated", color="positive")

    ui.button("Save metadata", on_click=_save)
