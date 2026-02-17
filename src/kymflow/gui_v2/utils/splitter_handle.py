"""Utility for adding visible pill-style handles to NiceGUI splitter separators."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Literal, Optional

from nicegui import ui

if TYPE_CHECKING:
    from nicegui.elements.splitter import QSplitter

_SPLITTER_HANDLE_CSS_ADDED = False

Orientation = Literal["horizontal", "vertical"]
Offset = Literal["center", "before", "after"]


def add_splitter_handle(
    splitter: "QSplitter",
    *,
    on_dblclick: Optional[Callable[[], None]] = None,
    orientation: Orientation = "horizontal",
    offset: Offset = "center",
) -> None:
    """Add a visible pill-style handle to a splitter's separator for dragging.

    Optionally wire dblclick for collapse/expand. CSS is added once (idempotent).

    Args:
        splitter: NiceGUI splitter element.
        on_dblclick: Optional callback for double-click (e.g. min/max toggle).
        orientation: "horizontal" = pill is wide and short (26x5px), for top|bottom
            splitters. "vertical" = pill is tall and narrow (5x26px), for left|right.
        offset: "center" = centered. "after" = toward .after pane. "before" = toward
            .before pane. Use "after" when .before can collapse to 0 so the handle
            stays visible in .after.
    """
    global _SPLITTER_HANDLE_CSS_ADDED
    if not _SPLITTER_HANDLE_CSS_ADDED:
        ui.add_css("""
            .handle_wrap {
                height: 100%;
                width: 100%;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            .handle_wrap_offset_before { align-items: flex-start; justify-content: flex-start; }
            .handle_wrap_offset_after { align-items: flex-end; justify-content: flex-end; }
            .splitter_handle {
                width: 26px;
                height: 5px;
                border-radius: 4px;
                background: rgba(148, 163, 184, 0.8);
            }
            .splitter_handle_vertical {
                width: 5px;
                height: 26px;
                border-radius: 4px;
                background: rgba(148, 163, 184, 0.8);
            }
        """)
        _SPLITTER_HANDLE_CSS_ADDED = True

    wrap_classes = ["handle_wrap"]
    if offset == "before":
        wrap_classes.append("handle_wrap_offset_before")
    elif offset == "after":
        wrap_classes.append("handle_wrap_offset_after")

    handle_classes = ["splitter_handle_vertical" if orientation == "vertical" else "splitter_handle"]

    with splitter.separator:
        with ui.element("div").classes(" ".join(wrap_classes)):
            handle = ui.element("div").classes(" ".join(handle_classes))
            if on_dblclick is not None:
                handle.on("dblclick", lambda _e: on_dblclick())
