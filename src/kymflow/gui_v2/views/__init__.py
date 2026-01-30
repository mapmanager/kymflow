# src/kymflow/gui_v2/views/__init__.py
"""Thin view wrappers around nicewidgets / v1 components."""

# Views
from kymflow.gui_v2.views.about_tab_view import AboutTabView
from kymflow.gui_v2.views.analysis_toolbar_view import AnalysisToolbarView
from kymflow.gui_v2.views.contrast_view import ContrastView
from kymflow.gui_v2.views.drawer_view import DrawerView
from kymflow.gui_v2.views.file_table_view import FileTableView
from kymflow.gui_v2.views.folder_selector_view import FolderSelectorView
from kymflow.gui_v2.views.image_line_viewer_view import ImageLineViewerView
from kymflow.gui_v2.views.kym_event_view import KymEventView
from kymflow.gui_v2.views.line_plot_controls_view import LinePlotControlsView
from kymflow.gui_v2.views.metadata_experimental_view import MetadataExperimentalView
from kymflow.gui_v2.views.metadata_header_view import MetadataHeaderView
from kymflow.gui_v2.views.metadata_tab_view import MetadataTabView
from kymflow.gui_v2.views.save_buttons_view import SaveButtonsView
# DEPRECATED: Stall analysis is deprecated
# from kymflow.gui_v2.views.stall_analysis_toolbar_view import StallAnalysisToolbarView
from kymflow.gui_v2.views.task_progress_view import TaskProgressView

# Bindings
from kymflow.gui_v2.views.analysis_toolbar_bindings import AnalysisToolbarBindings
from kymflow.gui_v2.views.contrast_bindings import ContrastBindings
from kymflow.gui_v2.views.file_table_bindings import FileTableBindings
from kymflow.gui_v2.views.folder_selector_bindings import FolderSelectorBindings
from kymflow.gui_v2.views.image_line_viewer_bindings import ImageLineViewerBindings
from kymflow.gui_v2.views.kym_event_bindings import KymEventBindings
from kymflow.gui_v2.views.line_plot_controls_bindings import LinePlotControlsBindings
from kymflow.gui_v2.views.metadata_experimental_bindings import MetadataExperimentalBindings
from kymflow.gui_v2.views.metadata_header_bindings import MetadataHeaderBindings
from kymflow.gui_v2.views.save_buttons_bindings import SaveButtonsBindings
# DEPRECATED: Stall analysis is deprecated
# from kymflow.gui_v2.views.stall_analysis_toolbar_bindings import StallAnalysisToolbarBindings
from kymflow.gui_v2.views.task_progress_bindings import TaskProgressBindings

__all__ = [
    # Views
    "AboutTabView",
    "AnalysisToolbarView",
    "ContrastView",
    "DrawerView",
    "FileTableView",
    "FolderSelectorView",
    "ImageLineViewerView",
    "KymEventView",
    "LinePlotControlsView",
    "MetadataExperimentalView",
    "MetadataHeaderView",
    "MetadataTabView",
    "SaveButtonsView",
    # DEPRECATED: Stall analysis is deprecated
    # "StallAnalysisToolbarView",
    "TaskProgressView",
    # Bindings
    "AnalysisToolbarBindings",
    "ContrastBindings",
    "FileTableBindings",
    "FolderSelectorBindings",
    "ImageLineViewerBindings",
    "KymEventBindings",
    "LinePlotControlsBindings",
    "MetadataExperimentalBindings",
    "MetadataHeaderBindings",
    "SaveButtonsBindings",
    # DEPRECATED: Stall analysis is deprecated
    # "StallAnalysisToolbarBindings",
    "TaskProgressBindings",
]
