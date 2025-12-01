# kymflow/gui/nicegui/image_widget.py

from __future__ import annotations

from dataclasses import asdict
from typing import Optional

import numpy as np
from nicegui import ui, events
from psygnal import Signal

from kymflow.v2.core.session import KymEngine
from kymflow.v2.core.roi import KymRoi, KymRoiSet, hit_test_rois
from kymflow.v2.core.viewport import KymViewport, view_to_full, full_to_view


class KymImageWidget:
    """NiceGUI-based image widget for viewing a kym + interactive ROIs.

    This widget is a thin frontend around the backend KymEngine. It handles:

    * Displaying the current viewport as an image.
    * Drawing / moving / resizing rectangular ROIs with the mouse.
    * Panning via Shift + drag.
    * Zooming via mouse wheel (centered on last mouse position).

    Signals are emitted for ROIs and viewport changes so other widgets
    (e.g. line plots, contrast controls) can stay in sync.

    Expected usage:

        engine = KymEngine(kym_array, display_size=(1000, 100))
        widget = KymImageWidget(engine)

        # Optionally connect signals:
        widget.viewport_changed.connect(on_viewport_changed)
        widget.roi_created.connect(on_roi_created)

        ui.run()
    """

    # ------------------------------------------------------------------
    # Signals
    # ------------------------------------------------------------------

    roi_created = Signal(KymRoi)
    """Emitted when a new ROI is created."""

    roi_updated = Signal(KymRoi)
    """Emitted when an existing ROI is modified (move/resize)."""

    roi_deleted = Signal(int)
    """Emitted when an ROI is deleted (argument is roi_id)."""

    roi_selected = Signal(Optional[int])
    """Emitted when the selected ROI changes (id or None)."""

    viewport_changed = Signal(KymViewport)
    """Emitted whenever the viewport (zoom/pan) changes."""

    mouse_moved_full = Signal(float, float)
    """Emitted on mouse move with coordinates in full-image space."""

    image_redrawn = Signal()
    """Emitted after the image + overlays are redrawn."""

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(
        self,
        engine: KymEngine,
        parent: Optional[ui.element] = None,
        edge_tolerance: float = 5.0,
        cmap: str = "gray",
    ) -> None:
        """Create a new KymImageWidget bound to a KymEngine.

        Args:
            engine: Backend KymEngine instance providing image, viewport, and
                ROI management.
            parent: Optional NiceGUI parent element to contain the widget.
                If None, the widget is created in the current context.
            edge_tolerance: Pixel tolerance for hit-testing ROI edges.
            cmap: Name of the Matplotlib colormap used for rendering.
        """
        self.engine = engine
        self.edge_tol = edge_tolerance
        self.cmap = cmap

        # State related to interaction
        self.selected_roi_id: Optional[int] = None
        self.mode: str = "idle"  # 'idle', 'drawing', 'moving', 'resizing_*', 'panning'
        self.start_x_full: Optional[float] = None
        self.start_y_full: Optional[float] = None
        self.last_pan_x_full: Optional[float] = None
        self.last_pan_y_full: Optional[float] = None
        self.last_mouse_x_full: Optional[float] = None
        self.last_mouse_y_full: Optional[float] = None
        self.last_image_update: float = 0.0  # simple throttle; set by caller if needed

        # For move operations we keep a copy of the ROI at drag start
        self._orig_roi_dict: Optional[dict] = None

        # Logical display size from the engine
        self.DISPLAY_W = self.engine.display_width
        self.DISPLAY_H = self.engine.display_height

        # Build UI elements
        with (parent or ui) as container:  # noqa: F841 - container unused, but keeps context
            # Initial rendering of the viewport
            pil_img = self.engine.render_view_pil(
                vmin=None,
                vmax=None,
                cmap=self.cmap,
                resize_to_display=True,
            )
            self.interactive = ui.interactive_image(
                pil_img,
                cross=True,
                events=["mousedown", "mousemove", "mouseup"],
            ).classes("w-full").style(
                f"aspect-ratio: {self.engine.image.width} / {self.engine.image.height}; "
                "object-fit: contain; border: 1px solid #666;"
            )
            # Use NiceGUI 3.3.1 pattern: on_mouse + generic "wheel" event
            self.interactive.on_mouse(self._on_mouse)
            self.interactive.on("wheel", self._on_wheel)

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def set_cmap(self, cmap: str) -> None:
        """Set the colormap used for rendering and redraw."""
        self.cmap = cmap
        self._update_image(force=True)

    def reset_view(self) -> None:
        """Reset the viewport to show the full image and redraw."""
        self.engine.zoom_reset()
        self.viewport_changed.emit(self.engine.viewport)
        self._update_image(force=True)

    # ------------------------------------------------------------------
    # Core drawing / update logic
    # ------------------------------------------------------------------

    def _update_image(self, force: bool = True) -> None:
        """Render the current viewport as a PIL image and update the widget.

        Args:
            force: Currently unused; reserved for future throttling logic.
        """
        pil_img = self.engine.render_view_pil(
            vmin=None,
            vmax=None,
            cmap=self.cmap,
            resize_to_display=True,
        )
        self.interactive.set_source(pil_img)
        self._redraw_overlays()
        self.image_redrawn.emit()

    def _redraw_overlays(self) -> None:
        """Draw ROI rectangles as an SVG overlay in display coordinates."""
        vp = self.engine.viewport
        rois: KymRoiSet = self.engine.rois

        svg_parts: list[str] = []
        for roi in rois:
            # Skip ROIs completely outside the viewport
            if (
                roi.right < vp.x_min
                or roi.left > vp.x_max
                or roi.bottom < vp.y_min
                or roi.top > vp.y_max
            ):
                continue

            # Intersect ROI with viewport
            left_full = max(roi.left, vp.x_min)
            right_full = min(roi.right, vp.x_max)
            top_full = max(roi.top, vp.y_min)
            bottom_full = min(roi.bottom, vp.y_max)

            # Convert to display coordinates
            left_local_x, top_local_y = full_to_view(
                left_full, top_full, vp, self.DISPLAY_W, self.DISPLAY_H
            )
            right_local_x, bottom_local_y = full_to_view(
                right_full, bottom_full, vp, self.DISPLAY_W, self.DISPLAY_H
            )

            w = right_local_x - left_local_x
            h = bottom_local_y - top_local_y

            stroke = "lime" if roi.id == self.selected_roi_id else "red"
            svg_parts.append(
                f'<rect x="{left_local_x}" y="{top_local_y}" '
                f'width="{w}" height="{h}" '
                f'stroke="{stroke}" stroke-width="2" '
                f'fill="red" fill-opacity="0.15" />'
            )

        self.interactive.content = "".join(svg_parts)
        self.interactive.update()

    # ------------------------------------------------------------------
    # Mouse interaction
    # ------------------------------------------------------------------

    def _on_mouse(self, e: events.MouseEventArguments) -> None:
        """Handle NiceGUI mouse events from the interactive_image.

        Converts display coordinates into full-image coordinates and then
        uses the backend engine + ROI helpers to apply edits.
        """
        vp: KymViewport = self.engine.viewport

        # Map from display-space to full-image coordinates
        vx = max(0.0, min(float(self.DISPLAY_W - 1), e.image_x))
        vy = max(0.0, min(float(self.DISPLAY_H - 1), e.image_y))
        x_full, y_full = view_to_full(vx, vy, vp, self.DISPLAY_W, self.DISPLAY_H)

        self.last_mouse_x_full = x_full
        self.last_mouse_y_full = y_full
        self.mouse_moved_full.emit(x_full, y_full)

        # Mousedown (left button)
        if e.type == "mousedown" and e.button == 0:
            if e.shift:
                # Start panning
                self.mode = "panning"
                self.start_x_full = x_full
                self.start_y_full = y_full
                self.last_pan_x_full = x_full
                self.last_pan_y_full = y_full
            else:
                # Hit-test existing ROIs
                roi, mode = hit_test_rois(self.engine.rois, x_full, y_full, self.edge_tol)
                if roi is not None and mode is not None:
                    self.selected_roi_id = roi.id
                    self.roi_selected.emit(roi.id)
                    self.mode = mode
                    self.start_x_full = x_full
                    self.start_y_full = y_full
                    # Keep a copy of the original ROI for move operations
                    self._orig_roi_dict = asdict(roi)
                else:
                    # Start a new ROI
                    new_roi = self.engine.start_drawing_roi(x_full, y_full)
                    self.selected_roi_id = new_roi.id
                    self.roi_selected.emit(new_roi.id)
                    self.roi_created.emit(new_roi)
                    self.mode = "drawing"
                    self.start_x_full = x_full
                    self.start_y_full = y_full
            self._redraw_overlays()
            return

        # Mousemove with left button held
        if e.type == "mousemove" and (e.buttons & 1):
            if self.mode == "panning":
                # Incremental pan based on last pan position
                if self.last_pan_x_full is not None and self.last_pan_y_full is not None:
                    dx = x_full - self.last_pan_x_full
                    dy = y_full - self.last_pan_y_full
                    self.engine.pan(dx_full=dx, dy_full=dy)
                    self.last_pan_x_full = x_full
                    self.last_pan_y_full = y_full
                    self.viewport_changed.emit(self.engine.viewport)
                    self._update_image(force=False)
                return

            # ROI operations
            sid = self.selected_roi_id
            if sid is None:
                return

            if self.mode == "drawing":
                # Rubber-band drawing from start point
                if self.start_x_full is None or self.start_y_full is None:
                    return
                self.engine.update_drawing_roi(
                    roi_id=sid,
                    x_full=x_full,
                    y_full=y_full,
                    x_start=self.start_x_full,
                    y_start=self.start_y_full,
                )
                roi = self.engine.rois.get(sid)
                if roi is not None:
                    self.roi_updated.emit(roi)
                self._redraw_overlays()
                return

            if self.mode == "moving":
                if self._orig_roi_dict is None or self.start_x_full is None or self.start_y_full is None:
                    return
                dx = x_full - self.start_x_full
                dy = y_full - self.start_y_full
                # Move based on original roi snapshot
                roi = self.engine.rois.get(sid)
                if roi is None:
                    return
                roi.left = self._orig_roi_dict["left"] + dx
                roi.top = self._orig_roi_dict["top"] + dy
                roi.right = self._orig_roi_dict["right"] + dx
                roi.bottom = self._orig_roi_dict["bottom"] + dy
                roi.clamp_to_image(self.engine.image)
                self.roi_updated.emit(roi)
                self._redraw_overlays()
                return

            if self.mode.startswith("resizing"):
                roi = self.engine.rois.get(sid)
                if roi is None:
                    return
                if self.mode == "resizing_left":
                    roi.left = x_full
                elif self.mode == "resizing_right":
                    roi.right = x_full
                elif self.mode == "resizing_top":
                    roi.top = y_full
                elif self.mode == "resizing_bottom":
                    roi.bottom = y_full
                roi.clamp_to_image(self.engine.image)
                self.roi_updated.emit(roi)
                self._redraw_overlays()
                return

        # Mouseup (left button)
        if e.type == "mouseup" and e.button == 0:
            if self.mode == "panning":
                self.mode = "idle"
                self.start_x_full = None
                self.start_y_full = None
                self.last_pan_x_full = None
                self.last_pan_y_full = None
                return

            sid = self.selected_roi_id
            if self.mode == "drawing" and sid is not None:
                # Remove zero-area ROIs
                roi = self.engine.rois.get(sid)
                if roi is not None:
                    if roi.left == roi.right or roi.top == roi.bottom:
                        self.engine.delete_roi(sid)
                        self.roi_deleted.emit(sid)
                        self.selected_roi_id = None
                        self.roi_selected.emit(None)

            # Reset interaction state
            self.mode = "idle"
            self.start_x_full = None
            self.start_y_full = None
            self._orig_roi_dict = None
            self._redraw_overlays()
            return

    # ------------------------------------------------------------------
    # Wheel zoom
    # ------------------------------------------------------------------

    def _on_wheel(self, e: events.GenericEventArguments) -> None:
        """Handle mouse wheel events for zooming.

        Wheel up/down zooms in/out. If shift is held, only the X-axis is zoomed;
        otherwise both X and Y are zoomed.
        """
        dy = e.args.get("deltaY", 0)
        if dy == 0:
            return

        # Wheel up (negative dy) => zoom in; wheel down => zoom out
        base_factor = 0.8 if dy < 0 else 1.25

        shift_pressed = bool(e.args.get("shiftKey", False))
        if shift_pressed:
            factor_x = base_factor
            factor_y = 1.0
        else:
            factor_x = base_factor
            factor_y = base_factor

        # Zoom around last mouse position, or viewport center if unknown
        cx = self.last_mouse_x_full
        cy = self.last_mouse_y_full
        vp = self.engine.viewport

        if cx is None or cy is None:
            cx = 0.5 * (vp.x_min + vp.x_max)
            cy = 0.5 * (vp.y_min + vp.y_max)

        self.engine.zoom_around(
            x_full=cx,
            y_full=cy,
            factor_x=factor_x,
            factor_y=factor_y,
        )
        self.viewport_changed.emit(self.engine.viewport)
        self._update_image(force=True)

    # ------------------------------------------------------------------
    # ROI utility helpers
    # ------------------------------------------------------------------

    def delete_selected_roi(self) -> None:
        """Delete the currently selected ROI, if any."""
        if self.selected_roi_id is None:
            return
        rid = self.selected_roi_id
        self.engine.delete_roi(rid)
        self.roi_deleted.emit(rid)
        self.selected_roi_id = None
        self.roi_selected.emit(None)
        self._redraw_overlays()
