"""Basic smoke tests for PlotController and plot generation.

These tests verify that different plot configurations can be generated
without runtime errors. They don't verify visual correctness, just that
the plotting functions execute successfully.
"""

import pytest
import pandas as pd
import numpy as np

from kymflow.core.plotting.pool.demo_pool_app import PlotController
from kymflow.core.plotting.pool.plot_state import PlotState, PlotType


@pytest.fixture
def sample_dataframe():
    """Create a sample dataframe for testing."""
    np.random.seed(42)
    n_rows = 100
    
    data = {
        "roi_id": np.random.choice([1, 2, 3], n_rows),
        "path": [f"path_{i}" for i in range(n_rows)],
        "grandparent_folder": np.random.choice(["A", "B", "C"], n_rows),
        "img_mean": np.random.randn(n_rows) * 10 + 50,
        "vel_mean": np.random.randn(n_rows) * 5 + 20,
        "other_numeric": np.random.randn(n_rows) * 3,
    }
    
    return pd.DataFrame(data)


@pytest.fixture
def plot_controller(sample_dataframe):
    """Create a PlotController instance for testing."""
    return PlotController(
        sample_dataframe,
        roi_id_col="roi_id",
        row_id_col="path",
    )


def test_scatter_plot_basic(plot_controller, sample_dataframe):
    """Test basic scatter plot generation."""
    state = PlotState(
        roi_id=0,
        xcol="img_mean",
        ycol="vel_mean",
        plot_type=PlotType.SCATTER,
    )
    plot_controller.plot_states[0] = state
    
    # Filter dataframe
    df_f = sample_dataframe.dropna(subset=[plot_controller.row_id_col])
    
    # Generate figure
    figure_dict = plot_controller.figure_generator.make_figure(df_f, state)
    
    assert "data" in figure_dict
    assert len(figure_dict["data"]) > 0


def test_scatter_plot_with_grouping(plot_controller, sample_dataframe):
    """Test scatter plot with group/color."""
    state = PlotState(
        roi_id=0,
        xcol="img_mean",
        ycol="vel_mean",
        plot_type=PlotType.SCATTER,
        group_col="grandparent_folder",
    )
    plot_controller.plot_states[0] = state
    
    df_f = sample_dataframe.dropna(subset=[plot_controller.row_id_col])
    figure_dict = plot_controller.figure_generator.make_figure(df_f, state)
    
    assert "data" in figure_dict
    assert len(figure_dict["data"]) > 0


def test_box_plot_basic(plot_controller, sample_dataframe):
    """Test basic box plot generation."""
    state = PlotState(
        roi_id=0,
        xcol="img_mean",  # Not used, but required
        ycol="vel_mean",
        plot_type=PlotType.BOX_PLOT,
        group_col="grandparent_folder",
    )
    plot_controller.plot_states[0] = state
    
    df_f = sample_dataframe.dropna(subset=[plot_controller.row_id_col])
    figure_dict = plot_controller.figure_generator.make_figure(df_f, state)
    
    assert "data" in figure_dict
    assert len(figure_dict["data"]) > 0


def test_box_plot_with_nesting(plot_controller, sample_dataframe):
    """Test box plot with nested grouping."""
    state = PlotState(
        roi_id=0,
        xcol="img_mean",
        ycol="vel_mean",
        plot_type=PlotType.BOX_PLOT,
        group_col="grandparent_folder",
        color_grouping="roi_id",
    )
    plot_controller.plot_states[0] = state
    
    df_f = sample_dataframe.dropna(subset=[plot_controller.row_id_col])
    figure_dict = plot_controller.figure_generator.make_figure(df_f, state)
    
    assert "data" in figure_dict
    assert len(figure_dict["data"]) > 0


def test_violin_plot_basic(plot_controller, sample_dataframe):
    """Test basic violin plot generation."""
    state = PlotState(
        roi_id=0,
        xcol="img_mean",
        ycol="vel_mean",
        plot_type=PlotType.VIOLIN,
        group_col="grandparent_folder",
    )
    plot_controller.plot_states[0] = state
    
    df_f = sample_dataframe.dropna(subset=[plot_controller.row_id_col])
    figure_dict = plot_controller.figure_generator.make_figure(df_f, state)
    
    assert "data" in figure_dict
    assert len(figure_dict["data"]) > 0


def test_violin_plot_with_nesting(plot_controller, sample_dataframe):
    """Test violin plot with nested grouping."""
    state = PlotState(
        roi_id=0,
        xcol="img_mean",
        ycol="vel_mean",
        plot_type=PlotType.VIOLIN,
        group_col="grandparent_folder",
        color_grouping="roi_id",
    )
    plot_controller.plot_states[0] = state
    
    df_f = sample_dataframe.dropna(subset=[plot_controller.row_id_col])
    figure_dict = plot_controller.figure_generator.make_figure(df_f, state)
    
    assert "data" in figure_dict
    assert len(figure_dict["data"]) > 0


def test_swarm_plot_basic(plot_controller, sample_dataframe):
    """Test basic swarm plot generation."""
    state = PlotState(
        roi_id=0,
        xcol="img_mean",
        ycol="vel_mean",
        plot_type=PlotType.SWARM,
        group_col="grandparent_folder",
    )
    plot_controller.plot_states[0] = state
    
    df_f = sample_dataframe.dropna(subset=[plot_controller.row_id_col])
    figure_dict = plot_controller.figure_generator.make_figure(df_f, state)
    
    assert "data" in figure_dict
    assert len(figure_dict["data"]) > 0


def test_swarm_plot_with_nesting(plot_controller, sample_dataframe):
    """Test swarm plot with nested grouping."""
    state = PlotState(
        roi_id=0,
        xcol="img_mean",
        ycol="vel_mean",
        plot_type=PlotType.SWARM,
        group_col="grandparent_folder",
        color_grouping="roi_id",
    )
    plot_controller.plot_states[0] = state
    
    df_f = sample_dataframe.dropna(subset=[plot_controller.row_id_col])
    figure_dict = plot_controller.figure_generator.make_figure(df_f, state)
    
    assert "data" in figure_dict
    assert len(figure_dict["data"]) > 0


def test_histogram_plot_basic(plot_controller, sample_dataframe):
    """Test basic histogram plot generation."""
    state = PlotState(
        roi_id=0,
        xcol="img_mean",
        ycol="vel_mean",
        plot_type=PlotType.HISTOGRAM,
    )
    plot_controller.plot_states[0] = state
    
    df_f = sample_dataframe.dropna(subset=[plot_controller.row_id_col])
    figure_dict = plot_controller.figure_generator.make_figure(df_f, state)
    
    assert "data" in figure_dict
    assert len(figure_dict["data"]) > 0


def test_cumulative_histogram_plot_basic(plot_controller, sample_dataframe):
    """Test basic cumulative histogram plot generation."""
    state = PlotState(
        roi_id=0,
        xcol="img_mean",
        ycol="vel_mean",
        plot_type=PlotType.CUMULATIVE_HISTOGRAM,
    )
    plot_controller.plot_states[0] = state
    
    df_f = sample_dataframe.dropna(subset=[plot_controller.row_id_col])
    figure_dict = plot_controller.figure_generator.make_figure(df_f, state)
    
    assert "data" in figure_dict
    assert len(figure_dict["data"]) > 0


def test_plot_with_prefilters(plot_controller, sample_dataframe):
    """Test plot generation with pre-filters enabled."""
    state = PlotState(
        roi_id=1,
        xcol="img_mean",
        ycol="vel_mean",
        plot_type=PlotType.SCATTER,
        use_absolute_value=True,
        use_remove_values=True,
        remove_values_threshold=100.0,
    )
    plot_controller.plot_states[0] = state
    
    df_f = sample_dataframe.dropna(subset=[plot_controller.row_id_col])
    figure_dict = plot_controller.figure_generator.make_figure(df_f, state)
    
    assert "data" in figure_dict
    assert len(figure_dict["data"]) > 0


def test_plot_with_mean_std(plot_controller, sample_dataframe):
    """Test plot generation with mean/std traces."""
    state = PlotState(
        roi_id=0,
        xcol="img_mean",
        ycol="vel_mean",
        plot_type=PlotType.SCATTER,
        group_col="grandparent_folder",
        show_mean=True,
        show_std_sem=True,
        std_sem_type="std",
    )
    plot_controller.plot_states[0] = state
    
    df_f = sample_dataframe.dropna(subset=[plot_controller.row_id_col])
    figure_dict = plot_controller.figure_generator.make_figure(df_f, state)
    
    assert "data" in figure_dict
    assert len(figure_dict["data"]) > 0
