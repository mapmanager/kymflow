"""NiceGUI demo: upload headers + folder catalog with 2D Plotly preview.

Run from ``kymflow`` project root::

    uv run python src/kymflow/core/image_loaders/image_loader_plugins/gui/demo_upload_app.py
"""

from __future__ import annotations

from nicegui import ui

from kymflow.core.image_loaders.image_loader_plugins.gui.folder_catalog_panel import (
    FolderCatalogPanel,
)
from kymflow.core.image_loaders.image_loader_plugins.gui.upload_header_panel import (
    UploadHeaderPanel,
)

from kymflow.core.utils.logging import get_logger, setup_logging
logger = get_logger(__name__)

setup_logging(level="DEBUG")

@ui.page("/")
def main_page() -> None:
    ui.label("Kymflow image_loader_plugins demos").classes("text-h5 q-mb-md")

    # QFooter lives in the layout slot (see NiceGUI Footer); keep status first so the
    # label keeps width in the flex row (spinner can squeeze a trailing label).
    with ui.footer(bordered=True).classes("w-full bg-grey-2 text-grey-9"):
        with ui.row().classes("items-center gap-3 w-full q-px-md q-py-sm"):
            footer_status = ui.label("Ready").classes("text-body2 flex-1 min-w-0")
            footer_spinner = ui.spinner(size="sm").props("color=primary")
            footer_spinner.visible = False

    folder = FolderCatalogPanel.from_default_fixtures(
        footer_status=footer_status,
        footer_spinner=footer_spinner,
    )

    async def on_upload_preview(loader, file_name: str) -> None:
        await folder.show_upload_preview_async(loader, file_name)

    with ui.column().classes("w-full max-w-6xl mx-auto gap-2"):
        UploadHeaderPanel(on_upload_preview=on_upload_preview).render()
        ui.separator().classes("q-my-md")
        folder.render()


if __name__ in {"__main__", "__mp_main__"}:
    logger.info('Starting demo_upload_app')
    ui.run(native=False, title="Kymflow image plugins demo")
