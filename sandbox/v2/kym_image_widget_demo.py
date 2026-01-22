# sandbox/kym_image_widget_demo.py

from __future__ import annotations

import numpy as np
from nicegui import ui

from kymflow.v2.core.session import KymEngine
from kymflow.v2.gui.nicegui.image_widget import KymImageWidget


def create_demo_kym(height: int = 100, width: int = 2000) -> np.ndarray:
    """Create a simple traveling sine-wave kym for testing the widget."""
    x = np.linspace(0, 4 * np.pi, width)
    kym = np.zeros((height, width), dtype=float)
    for y in range(height):
        phase = 2 * np.pi * (y / height)
        kym[y, :] = 0.5 + 0.5 * np.sin(x + phase)
    kym += 0.05 * np.random.randn(height, width)
    kym = np.clip(kym, 0.0, 1.0)
    return kym


if __name__ in {"__main__", "__mp_main__"}:    # Create backend engine
    kym = create_demo_kym()
    display_size = (1000, 50)  # logical display resolution
    engine = KymEngine(kym, display_size=display_size)

    # with ui.column().classes("items-start w-full") as col:
    with ui.column().classes("items-start w-full"):
        ui.label("KymImageWidget demo: draw/move/resize ROIs, pan (Shift+drag), zoom (wheel)").classes("m-2")

        widget = KymImageWidget(engine)
        # or to be explicit
        # widget = KymImageWidget(engine, parent=col)

        # Optional: some debug output when signals fire
        def on_viewport_changed(vp):
            ui.notify(f"Viewport: x=[{vp.x_min:.1f},{vp.x_max:.1f}], y=[{vp.y_min:.1f},{vp.y_max:.1f}]")

        def on_roi_created(roi):
            ui.notify(f"ROI created: id={roi.id}")

        widget.viewport_changed.connect(on_viewport_changed)
        widget.roi_created.connect(on_roi_created)

        # Simple button to reset view and delete selected ROI
        with ui.row().classes("m-2"):
            ui.button("Reset view", on_click=widget.reset_view)
            ui.button("Delete selected ROI", on_click=widget.delete_selected_roi)

    ui.run()
