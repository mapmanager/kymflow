"""Folder catalog: :class:`MyImageList`, :class:`MyFileTable`, Plotly preview."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from nicegui import run, ui

from kymflow.core.image_loaders.image_loader_plugins.gui.image_plot_plotly import (
    image_plot_plotly,
)
from kymflow.core.image_loaders.image_loader_plugins.gui.my_file_table import MyFileTable
from kymflow.core.image_loaders.image_loader_plugins.my_image_import import (
    ImageHeader,
    ImageLoaderBase,
    preview_yx_shape_hint_from_catalog_record,
)
from kymflow.core.image_loaders.image_loader_plugins.my_image_list import MyImageList

# (field, header label) — fields match :meth:`MyImageList.header_records`.
_AGGRID_COLUMNS: list[tuple[str, str]] = [
    ("file_name", "File"),
    ("parent_name", "Parent"),
    ("grandparent_name", "Grandparent"),
    # ("format", "Format"),
    ("num_channels", "Channels"),
    # ("num_scenes", "Scenes"),
    ("dims_display", "Dims"),
    ("shape_display", "Shape"),
    ("dtype", "Dtype"),
    ("physical_units", "Phys. units"),
    ("physical_units_labels", "Phys. unit labels"),
    ("header_loaded", "Header"),
    ("error", "Error"),
    ("relative_path", "Rel. path"),
]


def default_fixtures_dir() -> Path:
    """``tests/fixtures`` next to this package's ``tests`` tree."""
    return Path(__file__).resolve().parent.parent / "tests" / "fixtures"


def _preview_channel_index(rec: dict) -> int:
    """Demo rule: two-channel CZI uses channel 1 for 2D preview."""
    if rec.get("format") == "czi" and rec.get("num_channels") == 2:
        return 1
    return 0


def _preview_channel_index_for_loader(loader: ImageLoaderBase) -> int:
    """Same channel rule as :func:`_preview_channel_index` using loader header / path."""
    if loader.header.num_channels == 2 and str(loader.header.path).lower().endswith(".czi"):
        return 1
    return 0


def _extract_2d_for_demo(loader: ImageLoaderBase, *, channel: int = 0) -> np.ndarray:
    """Best-effort 2D slice for heatmap preview."""
    dims = loader.header.dims
    if "Y" in dims and "X" in dims:
        try:
            return loader.get_slice_data(channel, z=0, t=0)
        except (ValueError, IndexError):
            pass
    ch = loader.get_channel_data(channel)
    while ch.ndim > 2:
        ch = np.take(ch, 0, axis=0)
    if ch.ndim != 2:
        raise ValueError(
            f"Demo preview needs a 2D array; got shape {ch.shape} after reduction "
            f"(dims={loader.header.dims})"
        )
    return ch


def _sync_load_folder_preview(
    catalog: MyImageList,
    relative_path: str,
    channel: int,
) -> np.ndarray:
    """Run in a worker thread via :func:`nicegui.run.io_bound` (blocking I/O + NumPy)."""
    loader = catalog.get_loader_for_relative_path(relative_path)
    return _extract_2d_for_demo(loader, channel=channel)


def _sync_extract_upload_preview(loader: ImageLoaderBase) -> np.ndarray:
    """2D slice for an upload stream loader (worker thread)."""
    ch = _preview_channel_index_for_loader(loader)
    return _extract_2d_for_demo(loader, channel=ch)


def _cell_str(v: object) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "yes" if v else "no"
    s = str(v)
    return s if len(s) <= 200 else f"{s[:197]}..."


def _rows_for_aggrid(records: list[dict]) -> list[dict]:
    """Stringify cells; keep ``relative_path`` for row id and selection."""
    fields = [f for f, _ in _AGGRID_COLUMNS]
    out: list[dict] = []
    for rec in records:
        row: dict = {}
        for f in fields:
            row[f] = _cell_str(rec.get(f))
        out.append(row)
    return out


class FolderCatalogPanel:
    """Scan a folder with :class:`MyImageList`, show rows in :class:`MyFileTable`, Plotly."""

    def __init__(
        self,
        folder: str | Path,
        *,
        find_these_extensions: list[str] | None = None,
        max_depth: int = 4,
        footer_status: ui.label | None = None,
        footer_spinner: ui.spinner | None = None,
    ) -> None:
        exts = find_these_extensions if find_these_extensions is not None else [
            "czi",
            "oir",
            "tif",
        ]
        self._catalog = MyImageList(folder, find_these_extensions=exts, max_depth=max_depth)
        self._plot_dict: dict = image_plot_plotly(None).to_dict()
        self._plot: ui.plotly | None = None
        self._status: ui.label | None = None
        self._footer_status = footer_status
        self._footer_spinner = footer_spinner

    @classmethod
    def from_default_fixtures(
        cls,
        *,
        footer_status: ui.label | None = None,
        footer_spinner: ui.spinner | None = None,
    ) -> FolderCatalogPanel:
        """Catalog ``tests/fixtures`` under ``image_loader_plugins``.

        If that directory is missing, the panel still builds with an empty file table.
        """
        return cls(
            default_fixtures_dir(),
            footer_status=footer_status,
            footer_spinner=footer_spinner,
        )

    def _set_footer(self, text: str) -> None:
        if self._footer_status is not None:
            self._footer_status.set_text(text)

    def _set_footer_loading(self, loading: bool) -> None:
        """Show or hide the footer spinner only; footer text is set by the caller."""
        if self._footer_spinner is not None:
            self._footer_spinner.visible = loading

    def render(self) -> None:
        """Build UI in the current NiceGUI container."""
        # ui.label("Folder catalog (MyImageList + 2D preview)").classes("text-h6 q-mb-sm")

        records = self._catalog.header_records()
        grid_rows = _rows_for_aggrid(records)

        self._status = ui.label("Select a row to load pixels and show a 2D heatmap.").classes(
            "text-body2 q-mb-sm"
        )

        self._plot = ui.plotly(self._plot_dict).classes("w-full max-w-5xl h-[520px]")

        async def on_row_selected(row_id: str, _row: dict) -> None:
            await self._load_row_for_relative_path_async(row_id)

        MyFileTable(
            grid_rows,
            columns=_AGGRID_COLUMNS,
            row_id_field="relative_path",
            on_selected=on_row_selected,
        ).render().classes("mt-4")

        ui.label(f"Root: {self._catalog.folder}").classes("text-caption text-grey-7 q-mb-sm")

    async def show_upload_preview_async(
        self,
        loader: ImageLoaderBase,
        file_name: str,
    ) -> None:
        """Show the same Plotly heatmap as row selection, using an upload-time loader."""
        if self._plot is None or self._status is None:
            return
        self._set_footer(f"Loading upload preview {file_name} …")
        self._set_footer_loading(True)
        try:
            img2d = await run.io_bound(_sync_extract_upload_preview, loader)
        except Exception as exc:  # noqa: BLE001 — demo
            self._status.set_text(f"{type(exc).__name__}: {exc}")
            self._set_plot_image(None)
            ui.notify(f"Upload preview failed: {exc}", type="negative")
            self._set_footer(f"Upload preview failed: {exc}")
            return
        finally:
            self._set_footer_loading(False)
        ch_idx = _preview_channel_index_for_loader(loader)
        ch_note = f" ch={ch_idx}" if ch_idx else ""
        self._status.set_text(
            f"{file_name} (upload) — shape {img2d.shape} ({img2d.dtype}){ch_note}"
        )
        self._set_footer(f"Loaded {file_name} (upload).")
        display = self._set_plot_image(img2d, header=loader.header)
        disp_shape = display.shape if display is not None else ()
        self._set_footer(
            f"Displaying {file_name} (upload) — shape {disp_shape} "
            f"(source {img2d.dtype}, uint8 heatmap for Plotly)"
        )

    async def _load_row_for_relative_path_async(self, relative_path: str) -> None:
        assert self._plot is not None
        assert self._status is not None
        self._set_footer("Ready.")
        policy = self._catalog.describe_pixel_load(relative_path)
        if not policy.allowed:
            msg = policy.message or policy.code
            self._status.set_text(msg)
            self._set_plot_image(None)
            if policy.code == "ome_tiff_unsupported":
                ui.notify("OME-TIFF not supported", type="warning")
            elif policy.code == "header_error":
                ui.notify("Row has header error", type="warning")
            else:
                ui.notify(msg, type="warning")
            self._set_footer(f"Cannot load: {msg}")
            return
        rec = self._catalog.record_for_relative_path(relative_path)
        if rec is None:
            self._status.set_text(f"Unknown path: {relative_path}")
            self._set_footer("Ready.")
            return
        if rec["format"] not in ("tif", "tiff") and not rec.get("header_loaded"):
            self._status.set_text("Header not loaded yet (unexpected).")
            self._set_footer("Ready.")
            return
        ch_idx = _preview_channel_index(rec)
        file_name = Path(rec["path"]).name
        hint = preview_yx_shape_hint_from_catalog_record(rec)
        self._set_footer(f"Loading {file_name} (expected preview {hint}) …")
        self._set_footer_loading(True)
        try:
            img2d = await run.io_bound(
                _sync_load_folder_preview,
                self._catalog,
                relative_path,
                ch_idx,
            )
        except Exception as exc:  # noqa: BLE001 — demo
            self._status.set_text(f"{type(exc).__name__}: {exc}")
            self._set_plot_image(None)
            ui.notify(f"Preview failed: {exc}", type="negative")
            self._set_footer(f"Preview failed: {exc}")
            return
        finally:
            self._set_footer_loading(False)
        ch_note = f" ch={ch_idx}" if ch_idx else ""
        self._status.set_text(
            f"{file_name} — shape {img2d.shape} ({img2d.dtype}){ch_note}"
        )
        self._set_footer(f"Loaded {file_name}.")
        row_loader = self._catalog.get_loader_for_relative_path(relative_path)
        display = self._set_plot_image(img2d, header=row_loader.header)
        disp_shape = display.shape if display is not None else ()
        self._set_footer(
            f"Displaying {file_name} — shape {disp_shape} "
            f"(source {img2d.dtype}, uint8 heatmap for Plotly)"
        )

    def _set_plot_image(
        self,
        image: np.ndarray | None,
        *,
        header: ImageHeader | None = None,
    ) -> np.ndarray | None:
        """Update the Plotly heatmap; return the uint8 array passed to Plotly (or ``None``)."""
        assert self._plot is not None
        display = None if image is None else ImageLoaderBase.array_for_plotly_display(image)
        new_fig = image_plot_plotly(display, header=header)
        new_dict = new_fig.to_dict()
        self._plot_dict["data"] = new_dict["data"]
        self._plot_dict["layout"] = new_dict["layout"]
        self._plot.update()
        return display
