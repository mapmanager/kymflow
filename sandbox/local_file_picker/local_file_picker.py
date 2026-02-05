import platform
from pathlib import Path
from typing import Any, Dict, List, Optional

from nicegui import events, ui


class local_file_picker(ui.dialog):

    def __init__(
        self,
        directory: str,
        *,
        upper_limit: str | None = ...,
        multiple: bool = False,
        show_hidden_files: bool = False,
        allow_folder_selection: bool = True,
    ) -> None:
        """Local File Picker (NiceGUI + AG Grid)

        Notes:
        - NiceGUI's ui.aggrid selection helpers are most reliable with the legacy
          AG Grid selection config:
              rowSelection: 'single' | 'multiple'
          rather than the newer object-based selection config.
        """
        super().__init__()

        self.path = Path(directory).expanduser()
        if upper_limit is None:
            self.upper_limit = None
        else:
            self.upper_limit = Path(directory if upper_limit == ... else upper_limit).expanduser()

        self.show_hidden_files = show_hidden_files
        self.allow_folder_selection = allow_folder_selection
        self.multiple = multiple

        # Fallback: store last clicked row (because selection can be lost / not tracked)
        self._last_clicked_row: Optional[Dict[str, Any]] = None

        with self, ui.card():
            self.path_label = ui.label(str(self.path)).classes('text-sm font-mono mb-2')
            self.add_drives_toggle()

            self.grid = ui.aggrid(
                {
                    "columnDefs": [{"field": "name", "headerName": "File"}],
                    # IMPORTANT: legacy selection config (works with get_selected_rows)
                    "rowSelection": "multiple" if multiple else "single",
                    "rowMultiSelectWithClick": bool(multiple),
                    "suppressRowClickSelection": False,
                },
                html_columns=[0],
            ).classes("w-96")

            # Save clicked row as a robust fallback for OK
            self.grid.on("rowClicked", self._handle_row_clicked)

            # Double click = navigate into folder or submit file
            self.grid.on("cellDoubleClicked", self.handle_double_click)

            with ui.row().classes("w-full justify-end"):
                ui.button("Cancel", on_click=self.close).props("outline")
                ui.button("Ok", on_click=self._handle_ok)

        self.update_grid()

    def add_drives_toggle(self) -> None:
        if platform.system() == "Windows":
            import win32api  # type: ignore

            drives = win32api.GetLogicalDriveStrings().split("\000")[:-1]
            self.drives_toggle = ui.toggle(drives, value=drives[0], on_change=self.update_drive)

    def update_drive(self) -> None:
        self.path = Path(self.drives_toggle.value).expanduser()
        self.path_label.text = str(self.path)
        self.update_grid()

    def update_grid(self) -> None:
        self.path_label.text = str(self.path)

        paths = list(self.path.glob("*"))
        if not self.show_hidden_files:
            paths = [p for p in paths if not p.name.startswith(".")]

        # sort: folders first, then alpha
        paths.sort(key=lambda p: p.name.lower())
        paths.sort(key=lambda p: not p.is_dir())

        row_data: List[Dict[str, Any]] = [
            {
                "name": f'📁 <strong>{p.name}</strong>' if p.is_dir() else p.name,
                "path": str(p),
            }
            for p in paths
        ]

        # add ".." navigation row if allowed
        if (self.upper_limit is None and self.path != self.path.parent) or (
            self.upper_limit is not None and self.path != self.upper_limit
        ):
            row_data.insert(
                0,
                {
                    "name": "📁 <strong>..</strong>",
                    "path": str(self.path.parent),
                },
            )

        self.grid.options["rowData"] = row_data
        self.grid.update()

        # reset fallback click when the grid content changes
        self._last_clicked_row = None

    def _handle_row_clicked(self, e: events.GenericEventArguments) -> None:
        # Keep a fallback copy of the clicked row
        row = e.args.get("data")
        if isinstance(row, dict):
            self._last_clicked_row = row
            print(f"[DEBUG] _handle_row_clicked: saved last row: {row}")

    def handle_double_click(self, e: events.GenericEventArguments) -> None:
        print(f"[DEBUG] handle_double_click called, e.args: {e.args}")

        row = e.args.get("data") or {}
        path_str = row.get("path")
        if not isinstance(path_str, str):
            return

        self.path = Path(path_str)
        print(
            f"[DEBUG] handle_double_click: path={self.path}, "
            f"is_dir()={self.path.is_dir()}, is_file()={self.path.is_file()}"
        )

        if self.path.is_dir():
            self.path_label.text = str(self.path)
            self.update_grid()
        else:
            print(f"[DEBUG] handle_double_click: submitting file path: {self.path}")
            self.submit([str(self.path)])

    async def _handle_ok(self) -> None:
        print("[DEBUG] _handle_ok called")
        print(f"[DEBUG] _handle_ok: allow_folder_selection={self.allow_folder_selection}")

        rows = await self.grid.get_selected_rows()
        print(f"[DEBUG] _handle_ok: get_selected_rows() returned: {rows}")

        # Fallback: if selection API returned nothing, use last clicked row
        if not rows and self._last_clicked_row is not None:
            print("[DEBUG] _handle_ok: No selected rows; using _last_clicked_row fallback")
            rows = [self._last_clicked_row]

        if not rows:
            print("[DEBUG] _handle_ok: No rows selected and no fallback; returning early")
            return

        selected_paths: List[str] = []
        for i, row in enumerate(rows):
            if not isinstance(row, dict):
                continue

            path_str = row.get("path")
            if not isinstance(path_str, str):
                continue

            path = Path(path_str)
            print(
                f"[DEBUG] _handle_ok: row {i} path={path}, "
                f"is_dir()={path.is_dir()}, is_file()={path.is_file()}"
            )

            if path.is_dir():
                if self.allow_folder_selection:
                    selected_paths.append(str(path))
                else:
                    # folder clicked but folder selection disabled -> ignore
                    continue
            elif path.is_file():
                selected_paths.append(str(path))

        print(f"[DEBUG] _handle_ok: selected_paths={selected_paths}")
        if selected_paths:
            self.submit(selected_paths)