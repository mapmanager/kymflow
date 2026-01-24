"""Pool page for GUI v2."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import ui

from kymflow.gui_v2.app_context import AppContext
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.pages.base_page import BasePage

if TYPE_CHECKING:
    pass


class PoolPage(BasePage):
    """Pool page for pool operations.

    This is a skeleton page that will be implemented in the future.
    """

    def __init__(self, context: AppContext, bus: EventBus) -> None:
        """Initialize Pool page.

        Args:
            context: Shared application context.
            bus: Per-client EventBus instance.
        """
        super().__init__(context, bus)

    def build(self) -> None:
        """Build the Pool page UI."""
        ui.label("Pool is coming soon").classes("text-2xl font-bold")
