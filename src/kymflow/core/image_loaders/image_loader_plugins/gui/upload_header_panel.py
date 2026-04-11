"""Upload panel: stream in a file and show header JSON."""

from __future__ import annotations

import inspect
import io
import json
from collections.abc import Callable
from typing import Any

from nicegui import ui
from nicegui.events import UploadEventArguments

from kymflow.core.image_loaders.image_loader_plugins.my_image_import import (
    ImageLoaderBase,
    image_loader_from_upload,
)


class UploadHeaderPanel:
    """Drag-and-drop upload with JSON header output."""

    def __init__(
        self,
        *,
        on_upload_preview: Callable[[ImageLoaderBase, str], Any] | None = None,
    ) -> None:
        """Optional ``on_upload_preview(loader, file_name)`` after a successful header parse
        (may be ``async``; used by demos to reuse the catalog Plotly preview).
        """
        self._on_upload_preview = on_upload_preview

    def render(self) -> None:
        """Build UI in the current NiceGUI container."""
        async def handle_upload(e: UploadEventArguments) -> None:
            data = await e.file.read()
            stream = io.BytesIO(data)
            stream.name = e.file.name
            try:
                loader = image_loader_from_upload(stream, e.file.name)
                text = json.dumps(loader.header.as_json_dict(), indent=2)
                output.set_content(text)
                ui.notify(f"Loaded header for {e.file.name}")
                if self._on_upload_preview is not None:
                    result = self._on_upload_preview(loader, e.file.name)
                    if inspect.isawaitable(result):
                        await result
            except ValueError as err:
                output.set_content(str(err))
                ui.notify(f"Error: {err}", type="negative")
            except Exception as err:  # noqa: BLE001 — demo surfaces reader failures
                output.set_content(f"{type(err).__name__}: {err}")
                ui.notify(f"Failed: {err}", type="negative")

        with ui.row().classes("w-full items-start gap-4"):
            ui.upload(
                label="Drag and drop .czi, .oir, .tif, or .tiff",
                on_upload=handle_upload,
                auto_upload=True,
            ).props('accept=".czi,.oir,.tif,.tiff"').classes("shrink-0 w-full max-w-lg")
            output = ui.code("", language="json").classes(
                "flex-1 min-w-0 w-full max-h-96 overflow-auto"
            )
