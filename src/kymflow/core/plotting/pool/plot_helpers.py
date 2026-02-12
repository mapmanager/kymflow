"""Helper functions for pool plotting application.

This module provides utility functions for column detection and UI styling.
"""

from __future__ import annotations

import pandas as pd
from nicegui import ui


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
