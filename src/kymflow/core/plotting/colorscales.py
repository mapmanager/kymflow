"""Utilities for managing Plotly colorscales."""

from __future__ import annotations

from typing import Dict, List

# Common Plotly colorscale options
COLORSCALE_OPTIONS: List[Dict[str, str]] = [
    {"label": "Grayscale", "value": "Gray"},
    {"label": "Grayscale (Inverted)", "value": "inverted_grays"},
    {"label": "Viridis", "value": "Viridis"},
    {"label": "Plasma", "value": "Plasma"},
    {"label": "Hot", "value": "Hot"},
    {"label": "Jet", "value": "Jet"},
    {"label": "Cool", "value": "Cool"},
    {"label": "Rainbow", "value": "Rainbow"},
]


def get_colorscale(name: str) -> str | List[List[float | str]]:
    """Get Plotly colorscale string or list from name.

    Args:
        name: Colorscale name (e.g., "Gray", "Viridis", "inverted_grays")

    Returns:
        Colorscale string for built-in scales, or list for custom scales
    """
    # Handle custom inverted grayscale
    if name == "inverted_grays":
        return [[0, "rgb(255,255,255)"], [1, "rgb(0,0,0)"]]

    # Return name as-is for built-in Plotly colorscales
    return name
