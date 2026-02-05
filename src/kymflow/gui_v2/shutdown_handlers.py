from __future__ import annotations

from nicegui import app

from kymflow.gui_v2.app_context import AppContext

from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)


def save_all_configs(context: AppContext) -> bool:
    """Save both user_config and app_config to disk.
    
    Single source of truth for persisting all application configs.
    Used by both shutdown handler and manual save button.
    
    Args:
        context: AppContext instance containing user_config and app_config.
    
    Returns:
        True if both configs saved successfully, False otherwise.
    """
    success = True
    
    cfg = getattr(context, "user_config", None)
    if cfg is not None:
        try:
            cfg.save()
            logger.info("user_config saved successfully")
        except Exception:
            logger.exception("Failed to save user_config")
            success = False

    app_cfg = getattr(context, "app_config", None)
    if app_cfg is not None:
        try:
            app_cfg.save()
            logger.info("app_config saved successfully")
        except Exception:
            logger.exception("Failed to save app_config")
            success = False
    
    return success


def install_shutdown_handlers(context: AppContext, *, native: bool) -> None:
    """Register app shutdown handlers for GUI v2."""
    logger.info("install_shutdown_handlers(native=%s)", native)

    async def _persist_on_shutdown() -> None:
        """Persist user and app config on shutdown without touching native window APIs."""
        save_all_configs(context)

    app.on_shutdown(_persist_on_shutdown)

    # NOTE: No runtime timer here. We only capture at shutdown to avoid
    # introducing startup-time timer errors.
