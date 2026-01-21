"""Metadata tab view component.

This module provides a view component that displays both experimental and header
metadata views in a tab. This component encapsulates the layout and organization
of metadata editing widgets.
"""

from __future__ import annotations

from typing import Optional

from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.gui_v2.views.metadata_experimental_view import MetadataExperimentalView
from kymflow.gui_v2.views.metadata_header_view import MetadataHeaderView
from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)


class MetadataTabView:
    """Metadata tab view component.

    This view displays both experimental and header metadata forms together.
    It acts as a container that organizes the two metadata views and delegates
    operations to them.

    Lifecycle:
        - UI elements are created in render() (not __init__) to ensure correct
          DOM placement within NiceGUI's client context
        - Data updates via setter methods (called by bindings or parent)
        - Child views handle their own event emission

    Attributes:
        _experimental_view: Experimental metadata view instance.
        _header_view: Header metadata view instance.
    """

    def __init__(
        self,
        experimental_view: MetadataExperimentalView,
        header_view: MetadataHeaderView,
    ) -> None:
        """Initialize metadata tab view.

        Args:
            experimental_view: Experimental metadata view instance.
            header_view: Header metadata view instance.
        """
        self._experimental_view = experimental_view
        self._header_view = header_view

    def render(self) -> None:
        """Create the metadata tab UI inside the current container.

        Always creates fresh UI elements because NiceGUI creates a new container
        context on each page navigation. Old UI elements are automatically cleaned
        up by NiceGUI when navigating away.
        """
        # Render experimental metadata view
        self._experimental_view.render()

        # Render header metadata view
        self._header_view.render()

    def set_selected_file(self, file: Optional[KymImage]) -> None:
        """Populate metadata forms from file.

        Called by bindings or parent when FileSelection(phase="state") or
        MetadataUpdate(phase="state") events are received. Delegates to both
        child views.

        Args:
            file: Selected KymImage instance, or None if selection cleared.
        """
        self._experimental_view.set_selected_file(file)
        self._header_view.set_selected_file(file)
