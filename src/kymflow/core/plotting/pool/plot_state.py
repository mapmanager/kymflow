"""Plot state management for pool plotting application.

This module defines the PlotType enum and PlotState dataclass used to
serialize and manage plot configuration state.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional


class PlotType(Enum):
    """Enumeration of available plot types."""
    SCATTER = "scatter"
    SWARM = "swarm"
    BOX_PLOT = "box_plot"
    VIOLIN = "violin"
    HISTOGRAM = "histogram"
    CUMULATIVE_HISTOGRAM = "cumulative_histogram"
    GROUPED = "grouped"


@dataclass
class PlotState:
    """Configuration state for a single plot.
    
    This dataclass holds all configurable parameters for a plot, including
    data selection (ROI, columns), plot type, visual options, and statistics
    display settings.
    """
    roi_id: int
    xcol: str
    ycol: str
    plot_type: PlotType = PlotType.SCATTER
    group_col: Optional[str] = None    # used by grouped/scatter/swarm; becomes x-axis for box/violin/swarm
    color_grouping: Optional[str] = None  # nested grouping (color parameter) for box/violin/swarm
    ystat: str = "mean"                # used by grouped only
    use_absolute_value: bool = False   # apply abs() to x and y values before plotting (numeric only)
    swarm_jitter_amount: float = 0.35  # jitter amount for swarm plots (user-controllable)
    swarm_group_offset: float = 0.3    # offset amount for separating color groups in swarm plots
    use_remove_values: bool = False    # enable remove values pre-filter
    remove_values_threshold: Optional[float] = None  # threshold for remove values pre-filter
    show_mean: bool = False            # show mean line for scatter/swarm
    show_std_sem: bool = False         # show std/sem error bars for scatter/swarm
    std_sem_type: str = "std"          # "std" or "sem" for error bars
    mean_line_width: int = 2           # line width for mean line
    error_line_width: int = 2          # line width for error (std/sem) line
    show_raw: bool = True              # show raw data points
    point_size: int = 6                # size of scatter/swarm plot points
    show_legend: bool = True           # show plot legend
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize PlotState to dictionary.
        
        Returns:
            Dictionary representation of PlotState with all fields.
        """
        return {
            "roi_id": self.roi_id,
            "xcol": self.xcol,
            "ycol": self.ycol,
            "plot_type": self.plot_type.value,  # Convert enum to string
            "group_col": self.group_col,
            "color_grouping": self.color_grouping,
            "ystat": self.ystat,
            "use_absolute_value": self.use_absolute_value,
            "swarm_jitter_amount": self.swarm_jitter_amount,
            "swarm_group_offset": self.swarm_group_offset,
            "use_remove_values": self.use_remove_values,
            "remove_values_threshold": self.remove_values_threshold,
            "show_mean": self.show_mean,
            "show_std_sem": self.show_std_sem,
            "std_sem_type": self.std_sem_type,
            "mean_line_width": self.mean_line_width,
            "error_line_width": self.error_line_width,
            "show_raw": self.show_raw,
            "point_size": self.point_size,
            "show_legend": self.show_legend,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlotState":
        """Deserialize PlotState from dictionary.
        
        Args:
            data: Dictionary containing PlotState fields.
            
        Returns:
            PlotState instance created from dictionary data.
        """
        # Convert plot_type string back to enum (legacy "split_scatter" -> scatter)
        pt_val = data.get("plot_type", PlotType.SCATTER.value)
        if pt_val == "split_scatter":
            pt_val = "scatter"
        plot_type = PlotType(pt_val)
        
        return cls(
            roi_id=int(data.get("roi_id", 0)),
            xcol=str(data.get("xcol", "")),
            ycol=str(data.get("ycol", "")),
            plot_type=plot_type,
            group_col=data.get("group_col"),  # Can be None
            color_grouping=data.get("color_grouping"),  # Can be None
            ystat=str(data.get("ystat", "mean")),
            use_absolute_value=bool(data.get("use_absolute_value", False)),
            swarm_jitter_amount=float(data.get("swarm_jitter_amount", 0.35)),
            swarm_group_offset=float(data.get("swarm_group_offset", 0.3)),
            use_remove_values=bool(data.get("use_remove_values", False)),
            remove_values_threshold=data.get("remove_values_threshold"),  # Can be None
            show_mean=bool(data.get("show_mean", False)),
            show_std_sem=bool(data.get("show_std_sem", False)),
            std_sem_type=str(data.get("std_sem_type", "std")),
            mean_line_width=int(data.get("mean_line_width", 2)),
            error_line_width=int(data.get("error_line_width", 2)),
            show_raw=bool(data.get("show_raw", True)),
            point_size=int(data.get("point_size", 6)),
            show_legend=bool(data.get("show_legend", True)),
        )
