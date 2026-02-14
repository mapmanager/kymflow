# demo_upload_tif.py
"""
NiceGUI 3.7.x demo (native=False): upload a .tif/.tiff and read it with tifffile.

This version handles BOTH:
- SmallFileUpload (in-memory)
- LargeFileUpload (server-side temp file)

via normalize_uploaded_file().
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import tifffile
from nicegui import run, ui

from kymflow.gui_v2.upload_utils import normalize_uploaded_file
from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class TiffSummary:
    filename: str
    source_path: str
    shape: tuple[int, ...]
    dtype: str
    vmin: float
    vmax: float


def _read_tiff_summary_from_path(path: Path) -> TiffSummary:
    """Worker-safe: read TIFF and return summary (no UI code)."""
    arr = tifffile.imread(str(path))
    vmin = float(np.nanmin(arr))
    vmax = float(np.nanmax(arr))
    return TiffSummary(
        filename=path.name,
        source_path=str(path),
        shape=tuple(int(x) for x in arr.shape),
        dtype=str(arr.dtype),
        vmin=vmin,
        vmax=vmax,
    )


def main() -> None:
    ui.page_title("TIFF Upload Demo (NiceGUI 3.7.x, native=False)")

    with ui.column().classes("w-full max-w-3xl mx-auto gap-4"):
        ui.label("TIFF Upload Demo").classes("text-2xl font-semibold")
        ui.label("Upload a .tif/.tiff; server reads it with tifffile.").classes(
            "text-sm text-gray-600"
        )

        status = ui.label("Status: idle").classes("text-sm")
        spinner = ui.spinner(size="lg").props("color=primary")
        spinner.visible = False

        summary_card = ui.card().classes("w-full")
        summary_card.visible = False
        with summary_card:
            summary_title = ui.label("").classes("text-lg font-semibold")
            summary_md = ui.markdown("")

        with ui.dialog() as err_dialog, ui.card():
            ui.label("Upload error").classes("text-lg font-semibold text-red-600")
            err_body = ui.label("").classes("text-sm")
            ui.button("Close", on_click=err_dialog.close).props("outline dense")

        async def handle_upload(e) -> None:
            spinner.visible = True
            summary_card.visible = False

            try:
                upload_file = e.file
                filename = Path(upload_file.name).name
                status.text = f"Status: received {filename} ..."

                # ✅ ONE-LINE FIX: works for small + large uploads
                uploaded_path: Path = normalize_uploaded_file(upload_file)

                status.text = f"Status: reading TIFF from {uploaded_path} ..."
                summ = await run.io_bound(_read_tiff_summary_from_path, uploaded_path)

                summary_title.text = summ.filename
                summary_md.content = (
                    f"- **Temp path:** `{summ.source_path}`\n"
                    f"- **Shape:** `{summ.shape}`\n"
                    f"- **Dtype:** `{summ.dtype}`\n"
                    f"- **Min/Max:** `{summ.vmin}` / `{summ.vmax}`\n"
                )
                summary_card.visible = True
                status.text = "Status: done"

                print(
                    f"[upload] OK: {summ.filename} path={summ.source_path} "
                    f"shape={summ.shape} dtype={summ.dtype} min={summ.vmin} max={summ.vmax}"
                )

            except Exception as ex:
                status.text = "Status: error"
                err_body.text = f"{type(ex).__name__}: {ex}"
                err_dialog.open()
                logger.exception("Upload failed")

            finally:
                spinner.visible = False

        ui.upload(
            label="Upload TIFF (.tif/.tiff)",
            auto_upload=True,
            multiple=False,
            on_upload=handle_upload,
        ).props("accept=.tif,.tiff max-files=1").classes("w-full")

        ui.separator()
        ui.markdown(
            "- Uses normalize_uploaded_file() to handle SmallFileUpload and LargeFileUpload\n"
            "- TIFF is always read from a real filesystem path\n"
        ).classes("text-sm text-gray-700")

    port = int(os.getenv("PORT", "8080"))
    ui.run(native=False, reload=False, port=port, show=True)


if __name__ in {"__main__", "__mp_main__"}:
    main()