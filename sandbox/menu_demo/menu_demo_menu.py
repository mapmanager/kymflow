# menu_demo_menu.py
from __future__ import annotations

from pathlib import Path
from typing import Callable, List, Optional

from nicegui import ui


def get_recent_folders() -> List[str]:
    return [
        "/Users/cudmore/Documents",
        "/Users/cudmore/Desktop/some_old_folder",
    ]


def get_recent_files() -> List[str]:
    return [
        "/Users/cudmore/Downloads/sample.tif",
        "/Users/cudmore/Desktop/missing_file.csv",
    ]


def show_missing_path_dialog(path: str) -> None:
    print(f"[dialog] Item does not exist: {path}")
    with ui.dialog() as dialog, ui.card().classes("w-[520px]"):
        ui.label("Item does not exist").classes("text-lg font-semibold")
        ui.label(path).classes("text-sm break-all")
        with ui.row().classes("justify-end w-full"):
            ui.button("OK", on_click=dialog.close)
    dialog.open()


def on_path_selected(path: str) -> None:
    if not Path(path).exists():
        show_missing_path_dialog(path)
        return

    print(f"[selected] {path}")
    # ui.notify(f"Selected: {path}", type="positive")  # intentionally commented out


def clear_recently_opened() -> None:
    print("[clear] Cleared recently opened items")
    # ui.notify("Cleared recently opened items", type="warning")  # intentionally commented out


def apply_menu_defaults(*, text_size: str = "text-xs") -> None:
    ui.menu.default_classes(text_size)
    ui.menu.default_props("dense")
    ui.menu_item.default_classes(text_size)
    ui.menu_item.default_props("dense")


def build_recent_menu(
    *,
    recent_folders: Optional[List[str]] = None,
    recent_files: Optional[List[str]] = None,
    on_select: Callable[[str], None] = on_path_selected,
    on_clear: Callable[[], None] = clear_recently_opened,
) -> ui.menu:
    """Create and return a ui.menu for recent folders/files.

    Caller can open it via menu.open() from a button.
    """
    folders = recent_folders if recent_folders is not None else get_recent_folders()
    files = recent_files if recent_files is not None else get_recent_files()

    with ui.menu() as menu:
        header_folders = ui.menu_item("Folders")
        header_folders.disable()

        for path in folders:
            ui.menu_item(
                f"📁  {Path(path).name}",
                lambda p=path: on_select(p),
            )

        ui.separator()

        header_files = ui.menu_item("Files")
        header_files.disable()

        for path in files:
            ui.menu_item(
                f"📄  {Path(path).name}",
                lambda p=path: on_select(p),
            )

        ui.separator()

        ui.menu_item("🗑  Clear Recently Opened …", on_clear)

    return menu