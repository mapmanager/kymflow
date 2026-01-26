"""Shared navigation and header component."""

from __future__ import annotations

import webbrowser
from typing import TYPE_CHECKING, Callable, Optional

from nicegui import ui, app

if TYPE_CHECKING:
    from kymflow.gui_v2.app_context import AppContext


def open_external(url: str) -> None:
    """Open a URL in the system browser (native) or new tab (browser)."""
    native = getattr(app, "native", None)
    in_native = getattr(native, "main_window", None) is not None
    
    if in_native:
        webbrowser.open(url)
    else:
        ui.run_javascript(f'window.open("{url}", "_blank")')


def build_header(context: AppContext, dark_mode, drawer_toggle_callback: Optional[Callable[[], None]] = None) -> None:
    """Build the shared header with navigation and theme toggle.
    
    In multi-page architecture, this header is rebuilt on each page load.
    
    Args:
        context: Application context
        dark_mode: Dark mode controller for current page
        drawer_toggle_callback: Optional callback to toggle drawer (for Home page only)
    """
    def _navigate(path: str) -> None:
        """Navigate to a different page using NiceGUI routing."""
        ui.run_javascript(f'window.location.href="{path}"')
    
    def _update_theme_icon() -> None:
        icon = "light_mode" if dark_mode.value else "dark_mode"
        theme_button.props(f"icon={icon}")
    
    def _toggle_theme() -> None:
        context.toggle_theme(dark_mode)
        _update_theme_icon()
    
    with ui.header().classes("items-center justify-between"):
        # Left side: Drawer toggle, Title and navigation buttons
        with ui.row().classes("items-center gap-4"):
            # Drawer toggle button (always visible, enabled only on Home page)
            # drawer_button = ui.button(
            #     icon="menu",
            #     on_click=drawer_toggle_callback if drawer_toggle_callback else lambda: None,
            # ).props("flat round dense text-color=white").tooltip("Toggle toolbar drawer")
            
            # if drawer_toggle_callback is None:
            #     drawer_button.disable()
            
            ui.label("KymFlow").classes("text-xl font-bold text-white")
            
            ui.button(
                "Home",
                on_click=lambda: _navigate("/"),
            ).props("flat text-color=white")
            
            ui.button(
                "Batch",
                on_click=lambda: _navigate("/batch"),
            ).props("flat text-color=white")
            
            ui.button(
                "Pool",
                on_click=lambda: _navigate("/pool"),
            ).props("flat text-color=white")
            
            # COMMENTED OUT: About button removed - About tab is now in drawer
            # about_button = ui.button(
            #     "About",
            #     on_click=lambda: _navigate("/about"),
            # ).props("flat text-color=white")
        
        # Right side: Documentation, GitHub and theme buttons
        with ui.row().classes("items-center gap-2"):
            # Documentation button
            ui.button(
                icon="menu_book",
                on_click=lambda _: open_external(
                    "https://mapmanager.github.io/kymflow/"
                ),
            ).props("flat round dense text-color=white").tooltip("Open documentation")
            
            # GitHub button (as clickable image)
            github_icon = ui.image("https://cdn.simpleicons.org/github/ffffff").classes(
                "w-5 h-5 cursor-pointer"
            )
            github_icon.on(
                "click",
                lambda _: open_external("https://github.com/mapmanager/kymflow"),
            )
            github_icon.tooltip("Open GitHub repository")
            
            # Theme toggle button
            theme_button = ui.button(
                icon="light_mode" if dark_mode.value else "dark_mode",
                on_click=_toggle_theme,
            ).props("flat round dense text-color=white").tooltip("Toggle dark / light mode")
            
            _update_theme_icon()


def inject_global_styles() -> None:
    """Add shared CSS tweaks for NiceGUI components."""
    ui.add_head_html(
        """
<style>
.q-expansion-item__container .q-item {
    flex-direction: row-reverse;
}
.q-expansion-item__container .q-item__section--main {
    text-align: left;
}
/* Shift expansion header row left in drawer to align with content body */
.q-drawer .q-expansion-item__container .q-item {
    margin-left: -2rem;  /* -1rem (16px) to shift header row left to align with content */
}

/* Header height customization - adjust HEADER_HEIGHT value to change toolbar height */
:root {
    --kymflow-header-height: 48px;  /* Default header height */
}
.q-header {
    min-height: var(--kymflow-header-height) !important;
    display: flex !important;
    align-items: center !important;
}
.q-header .q-toolbar {
    min-height: var(--kymflow-header-height) !important;
    padding: 0 12px;  /* Reduced horizontal padding for more compact look */
    display: flex !important;
    align-items: center !important;
}
/* Ensure all header content is vertically centered */
.q-header .q-btn,
.q-header .q-img,
.q-header .q-label {
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
}
/* Reduce line-height for label to prevent overflow */
.q-header .q-label {
    line-height: 1.2 !important;
}
</style>
"""
    )

