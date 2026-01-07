# src/kymflow/gui_v2/pages/base_page.py
from __future__ import annotations

from abc import ABC, abstractmethod

from nicegui import ui

from kymflow.gui.app_context import AppContext
from kymflow.gui.navigation import build_header
from kymflow.gui_v2.bus import EventBus


class BasePage(ABC):
    """Base class for all v2 pages with shared header."""

    def __init__(self, context: AppContext, bus: EventBus) -> None:
        self.context = context
        self.bus = bus

    def render(self, *, page_title: str) -> None:
        """Render shared header, then page-specific content."""
        ui.page_title(page_title)

        dark_mode = self.context.init_dark_mode_for_page()
        build_header(self.context, dark_mode)

        with ui.column().classes("w-full p-4 gap-4"):
            self.build()

    @abstractmethod
    def build(self) -> None:
        """Build page-specific content."""
        raise NotImplementedError
