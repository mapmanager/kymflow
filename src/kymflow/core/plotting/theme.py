from __future__ import annotations

from kymflow.core.enums import ThemeMode


def get_theme_colors(theme: ThemeMode) -> tuple[str, str]:
    """Get background and foreground colors for a theme.

    Args:
        theme: Theme mode (DARK or LIGHT)

    Returns:
        Tuple of (background_color, foreground_color) as hex strings
    """
    if theme is ThemeMode.DARK:
        return "#000000", "#ffffff"
    else:  # LIGHT
        return "#ffffff", "#000000"


def get_theme_template(theme: ThemeMode) -> str:
    """Get Plotly template name for a theme.

    Args:
        theme: Theme mode (DARK or LIGHT)

    Returns:
        Plotly template name string
    """
    if theme is ThemeMode.DARK:
        return "plotly_dark"
    else:  # LIGHT
        return "plotly_white"
