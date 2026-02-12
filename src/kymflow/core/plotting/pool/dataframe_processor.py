"""DataFrame processing for pool plotting application.

This module provides the DataFrameProcessor class for core data manipulation
operations, separating data processing logic from UI/plotting concerns.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd


class DataFrameProcessor:
    """Processes DataFrames for plotting operations.
    
    Encapsulates core DataFrame manipulation operations including filtering,
    value extraction, and statistical calculations. This class separates
    data processing logic from UI/plotting code for better testability
    and reusability.
    
    Attributes:
        df: The source DataFrame.
        roi_id_col: Column name containing ROI identifiers.
        row_id_col: Column name containing unique row identifiers.
    """
    
    def __init__(
        self,
        df: pd.DataFrame,
        *,
        roi_id_col: str = "roi_id",
        row_id_col: str = "path",
    ) -> None:
        """Initialize DataFrameProcessor with dataframe and column configuration.
        
        Args:
            df: DataFrame containing plot data with required columns.
            roi_id_col: Column name containing ROI identifiers.
            row_id_col: Column name containing unique row identifiers.
            
        Raises:
            ValueError: If required columns are missing or no ROI values found.
        """
        self.df = df
        self.roi_id_col = roi_id_col
        self.row_id_col = row_id_col

        if self.roi_id_col not in df.columns:
            raise ValueError(f"df must contain required column {roi_id_col!r}")
        if self.row_id_col not in df.columns:
            raise ValueError(f"df must contain required unique id column {row_id_col!r}")

        roi_values = self.get_roi_values()
        if not roi_values:
            raise ValueError(f"No ROI values found in column {roi_id_col!r}")

    def get_roi_values(self) -> list[int]:
        """Get sorted list of unique ROI IDs from the dataframe.
        
        Returns:
            Sorted list of unique ROI ID integers.
        """
        s = pd.to_numeric(self.df[self.roi_id_col], errors="coerce").dropna().astype(int)
        vals = sorted(set(s.tolist()))
        return vals

    def filter_by_roi(self, roi_id: int) -> pd.DataFrame:
        """Filter dataframe to rows matching the ROI ID.
        
        Args:
            roi_id: ROI ID to filter by.
            
        Returns:
            Filtered dataframe containing only rows with matching ROI ID,
            with rows missing row_id_col removed.
        """
        df_f = self.df[self.df[self.roi_id_col].astype(int) == int(roi_id)]
        df_f = df_f.dropna(subset=[self.row_id_col])
        return df_f

    def build_row_id_index(self, df_f: pd.DataFrame) -> dict[str, int]:
        """Build mapping from row_id to iloc index in filtered dataframe.
        
        Args:
            df_f: Filtered dataframe to build index for.
            
        Returns:
            Dictionary mapping row_id (as string) to iloc index (0-based).
        """
        row_ids = df_f[self.row_id_col].astype(str).tolist()
        # map row_id -> iloc within df_f
        return {rid: i for i, rid in enumerate(row_ids)}

    def get_y_values(
        self, 
        df_f: pd.DataFrame, 
        ycol: str, 
        use_absolute: bool = False
    ) -> pd.Series:
        """Get y column values, optionally applying absolute value.
        
        Args:
            df_f: Filtered dataframe.
            ycol: Column name for y values.
            use_absolute: If True, apply abs() to values.
            
        Returns:
            Series of y values, with abs() applied if use_absolute is True.
        """
        y = pd.to_numeric(df_f[ycol], errors="coerce")
        if use_absolute:
            y = y.abs()
        return y

    def calculate_group_stats(
        self,
        df_f: pd.DataFrame,
        group_col: str,
        ycol: str,
        use_absolute: bool = False,
        xcol: Optional[str] = None,
        include_x: bool = False,
    ) -> dict[str, dict[str, float]]:
        """Calculate mean, std, and sem for y values (and optionally x values) within each group.
        
        Args:
            df_f: Filtered dataframe with group column and y values.
            group_col: Column name for grouping.
            ycol: Column name for y values.
            use_absolute: If True, apply abs() to y values before calculation.
            xcol: Column name for x values (required if include_x=True).
            include_x: If True, also calculate stats for x values (for scatter).
            
        Returns:
            Dictionary mapping group_value (as string) to stats dict with keys:
            - "mean", "std", "sem" for y-axis stats
            - "x_mean", "x_std", "x_sem" for x-axis stats (if include_x=True).
        """
        if not group_col:
            return {}
        
        y = self.get_y_values(df_f, ycol, use_absolute)
        g = df_f[group_col].astype(str)
        
        if include_x:
            if not xcol:
                raise ValueError("xcol is required when include_x=True")
            x = pd.to_numeric(df_f[xcol], errors="coerce")
            tmp = pd.DataFrame({"x": x, "y": y, "g": g}).dropna(subset=["y", "g", "x"])
        else:
            tmp = pd.DataFrame({"y": y, "g": g}).dropna(subset=["y", "g"])
        
        stats = {}
        for group_value, sub in tmp.groupby("g", sort=True):
            y_values = sub["y"].values
            if len(y_values) > 0:
                mean_val = float(np.mean(y_values))
                std_val = float(np.std(y_values, ddof=1))  # Sample std
                sem_val = std_val / np.sqrt(len(y_values)) if len(y_values) > 1 else 0.0
                
                group_stats = {
                    "mean": mean_val,
                    "std": std_val,
                    "sem": sem_val,
                }
                
                # Add x-axis stats if requested
                if include_x:
                    x_values = sub["x"].values
                    if len(x_values) > 0:
                        x_mean_val = float(np.mean(x_values))
                        x_std_val = float(np.std(x_values, ddof=1))
                        x_sem_val = x_std_val / np.sqrt(len(x_values)) if len(x_values) > 1 else 0.0
                        group_stats.update({
                            "x_mean": x_mean_val,
                            "x_std": x_std_val,
                            "x_sem": x_sem_val,
                        })
                
                stats[str(group_value)] = group_stats
        
        return stats
