# menu_demo_app.py
from __future__ import annotations

from nicegui import ui

from menu_demo_menu import apply_menu_defaults, build_recent_menu


def main() -> None:
    apply_menu_defaults(text_size="text-xs")

    ui.label("Recent menu demo").classes("text-xl font-semibold")

    recent_menu = build_recent_menu()

    ui.button(icon="menu", on_click=recent_menu.open).props("flat round")

    ui.run(native=True, title="Recent Menu Demo")


if __name__ in {"__main__", "__mp_main__"}:
    main()