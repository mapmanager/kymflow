"""Helper functions for pool plotting application.

This module provides utility functions for column detection, UI styling,
and geometry (e.g. point-in-polygon for lasso selection).
"""

from __future__ import annotations

import re
import numpy as np
import pandas as pd
from nicegui import ui


def parse_plotly_path_to_xy(path: str) -> tuple[list[float], list[float]]:
    """Parse Plotly layout.selections[].path (SVG path string) to x and y lists.

    Path is in data coordinates, e.g. "M 1 2 L 3 4 L 5 6 Z". Returns (x_list, y_list)
    for use with points_in_polygon. Returns ([], []) if parsing fails.
    """
    if not path or not isinstance(path, str):
        return [], []
    # Match number pairs: optional minus, digits/dots, optional exponent; comma or space separated
    pairs = re.findall(r"([-\d.eE+]+)[,\s]+([-\d.eE+]+)", path.strip())
    if len(pairs) < 3:
        return [], []
    xs = [float(a) for a, _ in pairs]
    ys = [float(b) for _, b in pairs]
    return xs, ys


def points_in_polygon(
    points: np.ndarray,
    polygon_xy: np.ndarray | list[tuple[float, float]],
) -> np.ndarray:
    """Test which points fall inside a polygon (ray-casting, even-odd rule).

    No dependency on matplotlib: uses only numpy. Suitable for lasso selection.

    Args:
        points: Shape (N, 2), each row is (x, y).
        polygon_xy: Polygon vertices, shape (M, 2) or list of (x,y) tuples.
                   First and last vertex need not coincide (closed automatically).

    Returns:
        Boolean array of shape (N,); True where the point is inside the polygon.
    """
    if len(points) == 0:
        return np.array([], dtype=bool)
    pts = np.asarray(points, dtype=float)
    if pts.ndim != 2 or pts.shape[1] != 2:
        raise ValueError("points must have shape (N, 2)")
    poly = np.asarray(polygon_xy, dtype=float)
    if poly.ndim != 2 or poly.shape[1] != 2 or len(poly) < 3:
        raise ValueError("polygon_xy must have shape (M, 2) with M >= 3")
    px = pts[:, 0]
    py = pts[:, 1]
    vx = poly[:, 0]
    vy = poly[:, 1]
    n = len(poly)
    # Ray from each point going right (+x); count crossings with polygon edges
    inside = np.zeros(pts.shape[0], dtype=bool)
    for i in range(n):
        j = (i + 1) % n
        # Edge from (vx[i], vy[i]) to (vx[j], vy[j])
        if vy[i] == vy[j]:
            continue  # horizontal edge: ray doesn't cross
        # Straddle: py must be strictly between vy[i] and vy[j] for ray to cross
        if vy[i] < vy[j]:
            cross = (py > vy[i]) & (py <= vy[j])
        else:
            cross = (py > vy[j]) & (py <= vy[i])
        if not np.any(cross):
            continue
        # x where edge crosses horizontal line at py
        x_intersect = vx[i] + (vx[j] - vx[i]) * (py - vy[i]) / (vy[j] - vy[i])
        cross = cross & (px < x_intersect)
        inside ^= cross  # odd number of crossings -> inside
    return inside


# CSS for compact aggrid styling (injected once)
_AGGRID_COMPACT_CSS_INJECTED = False


def _ensure_aggrid_compact_css() -> None:
    """Inject CSS for compact aggrid styling (smaller font, tighter spacing)."""
    global _AGGRID_COMPACT_CSS_INJECTED
    if not _AGGRID_COMPACT_CSS_INJECTED:
        ui.add_head_html("""
        <style>
        .aggrid-compact .ag-cell,
        .aggrid-compact .ag-header-cell {
            padding: 2px 6px;
            font-size: 0.75rem;
            line-height: 1.2;
        }
        </style>
        """)
        _AGGRID_COMPACT_CSS_INJECTED = True


_NUMERIC_KINDS = {"i", "u", "f"}  # int, unsigned, float (pandas dtype.kind)


def numeric_columns(df: pd.DataFrame) -> list[str]:
    """Extract list of numeric column names from dataframe.
    
    Args:
        df: DataFrame to analyze.
        
    Returns:
        List of column names that are numeric (int, unsigned, float).
    """
    out: list[str] = []
    for c in df.columns:
        s = df[c]
        if getattr(s.dtype, "kind", None) in _NUMERIC_KINDS:
            out.append(str(c))
    return out


def categorical_candidates(df: pd.DataFrame) -> list[str]:
    """Heuristic: object/category/bool, or low-ish cardinality.

    Identifies columns that are good candidates for categorical grouping:
    - Object, category, or boolean dtype columns
    - Numeric columns with low cardinality (<= 20 or <= 5% of rows)

    Args:
        df: DataFrame to analyze.

    Returns:
        List of column names that are categorical candidates.
    """
    out: list[str] = []
    n = len(df)
    for c in df.columns:
        s = df[c]
        kind = getattr(s.dtype, "kind", None)
        if kind in {"O", "b"} or str(s.dtype) == "category":
            out.append(str(c))
            continue
        nunique = s.nunique(dropna=True)
        if n > 0 and nunique <= max(20, int(0.05 * n)):
            out.append(str(c))
    return out


def is_categorical_column(df: pd.DataFrame, col: str) -> bool:
    """Return True if col is a categorical candidate (suitable for box plot x-axis, etc.)."""
    if col not in df.columns:
        return False
    return col in categorical_candidates(df)
