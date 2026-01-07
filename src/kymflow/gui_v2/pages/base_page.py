"""Base page class for GUI v2 with shared layout and lifecycle management."""

from __future__ import annotations

from abc import ABC, abstractmethod

from nicegui import ui

from kymflow.gui.app_context import AppContext
from kymflow.gui.navigation import build_header
from kymflow.gui_v2.bus import EventBus, get_client_id


class BasePage(ABC):
    """Base class for all v2 pages with shared header and lifecycle management.

    Provides:
    - Consistent header/navigation across all pages
    - Client ID tracking for per-client initialization
    - Lifecycle hooks for setup and teardown

    Attributes:
        context: Shared application context (singleton).
        bus: Per-client EventBus instance.
        _client_id: Client identifier for this page instance.
    """

    def __init__(self, context: AppContext, bus: EventBus) -> None:
        """Initialize base page.

        Args:
            context: Shared application context (process-level singleton).
            bus: Per-client EventBus instance.
        """
        self.context: AppContext = context
        self.bus: EventBus = bus
        self._client_id: str = get_client_id()

    def render(self, *, page_title: str) -> None:
        """Render shared header, then page-specific content.

        This is the main entry point for rendering a page. It sets up the common
        layout (header, navigation, theme) and then calls the subclass's build()
        method to create page-specific content.

        Args:
            page_title: HTML page title to display in the browser tab.
        """
        ui.page_title(page_title)

        dark_mode = self.context.init_dark_mode_for_page()
        build_header(self.context, dark_mode)

        with ui.column().classes("w-full p-4 gap-4"):
            # Ensure setup is called once per client before building
            self._ensure_setup()
            self.build()

    def _ensure_setup(self) -> None:
        """Ensure page setup is called once per client.

        Override this method in subclasses to perform one-time initialization
        (e.g., subscribing to events). This method is idempotent and will only
        run once per client session.

        By default, does nothing. Subclasses should override if they need setup.
        """
        pass

    @abstractmethod
    def build(self) -> None:
        """Build page-specific content.

        This method is called every time the page is rendered. It should create
        the UI elements specific to this page. UI elements are created fresh
        on each render, but controllers and bindings should be created in _ensure_setup()
        to avoid duplicate subscriptions.
        """
        raise NotImplementedError
