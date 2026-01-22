"""Base page class for GUI v2 with shared layout and lifecycle management."""

from __future__ import annotations

from abc import ABC, abstractmethod

from nicegui import ui

from kymflow.gui_v2.app_context import AppContext
from kymflow.gui_v2.navigation import build_header
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

        NiceGUI creates a fresh container context on each page navigation. When
        navigating from one route to another, NiceGUI:
        - Destroys all UI elements from the previous route
        - Creates a new DOM container for the new route
        - Calls this render() method with a fresh container

        Therefore, build() should always create fresh UI elements. Controllers
        and bindings are created in _ensure_setup() (called once per client) to
        avoid duplicate event subscriptions.

        Args:
            page_title: HTML page title to display in the browser tab.
        """
        ui.page_title(page_title)

        dark_mode = self.context.init_dark_mode_for_page()
        build_header(self.context, dark_mode)

        with ui.column().classes("w-full p-4 gap-4"):
            # Ensure setup is called once per client before building
            # This creates controllers/bindings (Python objects that persist)
            self._ensure_setup()
            # build() creates fresh UI elements in the new container context
            # NiceGUI automatically cleans up old UI elements from previous navigation
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

        This method is called every time the page is rendered (e.g., on each
        navigation). NiceGUI creates a fresh container context for each page
        navigation, so this method should always create new UI elements.

        Important:
        - UI elements (ui.select, ui.plotly, etc.) are destroyed by NiceGUI
          when navigating away and must be recreated here
        - Views should reset their UI element references at the start of render()
          and create fresh elements each time
        - Controllers and bindings should be created in _ensure_setup() (called
          once per client) to avoid duplicate event subscriptions
        - NiceGUI automatically cleans up old UI elements when navigating away

        Example:
            def build(self) -> None:
                # Always create fresh UI elements
                self._view.render()  # View's render() resets and recreates UI
        """
        raise NotImplementedError
