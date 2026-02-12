"""Linked selection handling for pool plots (rect/lasso, extend modifier, apply to plots)."""

from __future__ import annotations

from typing import Any, Callable, Optional

import numpy as np
import pandas as pd

from kymflow.core.utils.logging import get_logger
from kymflow.core.plotting.pool.plot_state import PlotType, PlotState
from kymflow.core.plotting.pool.plot_helpers import parse_plotly_path_to_xy, points_in_polygon
from kymflow.core.plotting.pool.dataframe_processor import DataFrameProcessor
from kymflow.core.plotting.pool.figure_generator import FigureGenerator

logger = get_logger(__name__)


def is_selection_compatible(plot_type: PlotType) -> bool:
    """True if plot type supports rect/lasso selection."""
    return plot_type in {PlotType.SCATTER, PlotType.SWARM}


def _compute_selected_points_from_range(
    data_processor: DataFrameProcessor,
    figure_generator: FigureGenerator,
    row_id_col: str,
    df_f: pd.DataFrame,
    state: PlotState,
    x_range: Optional[tuple[float, float]] = None,
    y_range: Optional[tuple[float, float]] = None,
) -> set[str]:
    """Compute selected row_ids from box select range."""
    if not len(df_f):
        return set()
    x_axis = figure_generator.get_axis_x_for_selection(df_f, state)
    y_vals = data_processor.get_y_values(df_f, state.ycol, state.use_absolute_value)
    row_ids = df_f[row_id_col].astype(str)
    mask = pd.Series(True, index=df_f.index)
    if x_range is not None:
        x_min, x_max = x_range
        mask = mask & (x_axis >= x_min) & (x_axis <= x_max)
    if y_range is not None:
        y_min, y_max = y_range
        mask = mask & (y_vals >= y_min) & (y_vals <= y_max)
    return set(row_ids[mask].tolist())


def _compute_selected_points_from_lasso(
    data_processor: DataFrameProcessor,
    figure_generator: FigureGenerator,
    row_id_col: str,
    df_f: pd.DataFrame,
    state: PlotState,
    lasso_x: list[float],
    lasso_y: list[float],
) -> set[str]:
    """Compute selected row_ids from lasso polygon."""
    if not len(df_f) or not lasso_x or not lasso_y or len(lasso_x) != len(lasso_y):
        return set()
    x_axis = figure_generator.get_axis_x_for_selection(df_f, state)
    y_vals = data_processor.get_y_values(df_f, state.ycol, state.use_absolute_value)
    points = np.column_stack([x_axis.values, y_vals.values])
    polygon_xy = np.column_stack([lasso_x, lasso_y])
    mask = points_in_polygon(points, polygon_xy)
    row_ids = df_f[row_id_col].astype(str)
    return set(row_ids.loc[mask].tolist())


class PlotSelectionHandler:
    """Handles linked selection: rect/lasso parsing, extend modifier, apply to plots, label update."""

    def __init__(
        self,
        data_processor: DataFrameProcessor,
        figure_generator: FigureGenerator,
        row_id_col: str,
        get_filtered_df: Callable[[PlotState], pd.DataFrame],
        on_apply_selection: Callable[[], None],
        on_update_label: Callable[[int], None],
    ) -> None:
        self._data_processor = data_processor
        self._figure_generator = figure_generator
        self._row_id_col = row_id_col
        self._get_filtered_df = get_filtered_df
        self._on_apply_selection = on_apply_selection
        self._on_update_label = on_update_label
        self._selected_row_ids: set[str] = set()
        self._extend_selection_modifier: bool = False

    def get_selected_row_ids(self) -> set[str]:
        return set(self._selected_row_ids)

    def set_selected_row_ids(self, ids: set[str]) -> None:
        self._selected_row_ids = set(ids)

    def handle_relayout(self, payload: dict, plot_index: int, plot_state: PlotState) -> None:
        """Parse rect/lasso from relayout payload, compute row_ids, update selection, apply and update label."""
        if "selections" not in payload:
            return
        selections = payload.get("selections") or []
        if not selections:
            if self._selected_row_ids:
                self._selected_row_ids = set()
                self._on_apply_selection()
                self._on_update_label(0)
            return

        if not is_selection_compatible(plot_state.plot_type):
            return
        df_f = self._get_filtered_df(plot_state)
        selected_row_ids: set[str] = set()
        source = "none"

        x0 = payload.get("selections[0].x0")
        x1 = payload.get("selections[0].x1")
        y0 = payload.get("selections[0].y0")
        y1 = payload.get("selections[0].y1")
        if x0 is not None and x1 is not None and y0 is not None and y1 is not None:
            try:
                x_range = (float(min(x0, x1)), float(max(x0, x1)))
                y_range = (float(min(y0, y1)), float(max(y0, y1)))
                selected_row_ids = _compute_selected_points_from_range(
                    self._data_processor,
                    self._figure_generator,
                    self._row_id_col,
                    df_f,
                    plot_state,
                    x_range=x_range,
                    y_range=y_range,
                )
                source = "rect"
            except (TypeError, ValueError):
                pass

        if not selected_row_ids and selections:
            sel = selections[0] if isinstance(selections[0], dict) else None
            if sel:
                stype = sel.get("type")
                if stype == "rect":
                    try:
                        x0, x1 = sel.get("x0"), sel.get("x1")
                        y0, y1 = sel.get("y0"), sel.get("y1")
                        if x0 is not None and x1 is not None and y0 is not None and y1 is not None:
                            x_range = (float(min(x0, x1)), float(max(x0, x1)))
                            y_range = (float(min(y0, y1)), float(max(y0, y1)))
                            selected_row_ids = _compute_selected_points_from_range(
                                self._data_processor,
                                self._figure_generator,
                                self._row_id_col,
                                df_f,
                                plot_state,
                                x_range=x_range,
                                y_range=y_range,
                            )
                            source = "rect"
                    except (TypeError, ValueError):
                        pass
                elif stype == "path":
                    path_str = sel.get("path")
                    lasso_x, lasso_y = parse_plotly_path_to_xy(path_str or "")
                    if lasso_x and lasso_y and len(lasso_x) == len(lasso_y):
                        selected_row_ids = _compute_selected_points_from_lasso(
                            self._data_processor,
                            self._figure_generator,
                            self._row_id_col,
                            df_f,
                            plot_state,
                            lasso_x=lasso_x,
                            lasso_y=lasso_y,
                        )
                        source = "lasso"

        if not selected_row_ids:
            return
        if self._extend_selection_modifier and self._selected_row_ids:
            self._selected_row_ids = self._selected_row_ids | selected_row_ids
            self._extend_selection_modifier = False
            logger.info(
                "Extend selection on plot %s: source=%s, added %s, total %s",
                plot_index + 1,
                source,
                len(selected_row_ids),
                len(self._selected_row_ids),
            )
        else:
            self._selected_row_ids = selected_row_ids
            logger.info(
                "Selection on plot %s: source=%s, selected_count=%s",
                plot_index + 1,
                source,
                len(selected_row_ids),
            )
        self._on_apply_selection()
        self._on_update_label(len(self._selected_row_ids))

    def handle_clear(self) -> None:
        if not self._selected_row_ids:
            return
        self._selected_row_ids = set()
        self._on_apply_selection()
        self._on_update_label(0)
        logger.info("Selection cleared")

    def handle_key(self, key_name: Optional[str], action: Any = None) -> None:
        if key_name == "Escape":
            if self._selected_row_ids:
                self.handle_clear()
            return
        if key_name in ("Meta", "Control"):
            if action and getattr(action, "keydown", False):
                self._extend_selection_modifier = True
            elif action and getattr(action, "keyup", False):
                self._extend_selection_modifier = False

    def select_by_row_id(self, row_id: str, plot_states: list[PlotState]) -> None:
        """Programmatically set selection to the point(s) with the given row_id."""
        scatter_index = None
        for i, state in enumerate(plot_states):
            if state.plot_type == PlotType.SCATTER:
                scatter_index = i
                break
        if scatter_index is None:
            logger.warning("No scatter plot found for programmatic selection")
            return
        state = plot_states[scatter_index]
        df_f = self._get_filtered_df(state)
        matching = df_f[df_f[self._row_id_col] == row_id]
        if len(matching) == 0:
            logger.warning("Row ID %s not found in filtered dataframe", row_id)
            return
        ids = set(matching[self._row_id_col].astype(str).unique())
        self._selected_row_ids = ids
        self._on_apply_selection()
        self._on_update_label(len(self._selected_row_ids))
        logger.info("Programmatically selected %s point(s) by row_id=%s", len(ids), row_id)
