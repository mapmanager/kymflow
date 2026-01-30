from __future__ import annotations

from nicegui import app

from kymflow.gui_v2.app_context import AppContext


def install_shutdown_handlers(context: AppContext) -> None:
    """Register app shutdown handlers for GUI v2."""

    def _save_user_config() -> None:
        context.user_config.save()

    app.on_shutdown(_save_user_config)
