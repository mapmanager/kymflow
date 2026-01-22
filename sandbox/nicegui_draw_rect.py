# sandbox/kymflow_rois_with_lut.py

from nicegui import ui, events
import numpy as np
from PIL import Image
import matplotlib.cm as cm

# ============================================================
# 1. kym data and image mapping (NumPy -> PIL with LUT)
# ============================================================

# Example kym-style array (replace with your real data)
H, W = 256, 256
kym = np.random.rand(H, W) ** 2  # some skewed intensities for fun

def array_to_pil(
    arr: np.ndarray,
    vmin: float | None = None,
    vmax: float | None = None,
    cmap: str = "gray",
) -> Image.Image:
    """Map a 2D array to an 8-bit RGB PIL image with a colormap."""
    arr = np.asarray(arr, dtype=float)

    if vmin is None:
        vmin = float(np.nanmin(arr))
    if vmax is None:
        vmax = float(np.nanmax(arr))

    if vmax == vmin:
        vmax = vmin + 1e-6

    norm = (arr - vmin) / (vmax - vmin)
    norm = np.clip(norm, 0.0, 1.0)

    cmap_fn = cm.get_cmap(cmap)
    rgba = cmap_fn(norm)           # (H, W, 4) in 0..1
    rgb = (rgba[..., :3] * 255).astype(np.uint8)
    return Image.fromarray(rgb)


# ============================================================
# 2. ROI state and helpers
#    rois[id] = {'left', 'top', 'right', 'bottom', 'note'}
# ============================================================

EDGE_TOL = 5  # px for edge hit test

state = {
    "rois": {},
    "next_id": 1,        # ROIs numbered 1, 2, 3, ...
    "selected_id": None,
    "mode": "idle",      # 'idle', 'drawing', 'moving', 'resizing_*'
    "start_x": None,
    "start_y": None,
    "orig_roi": None,
}

# will be assigned later
interactive = None       # type: ignore[assignment]


def snap_roi_to_bounds(roi: dict) -> None:
    """Clamp ROI coords to image bounds and ensure left<=right, top<=bottom."""
    roi["left"] = max(0, min(W, roi["left"]))
    roi["right"] = max(0, min(W, roi["right"]))
    roi["top"] = max(0, min(H, roi["top"]))
    roi["bottom"] = max(0, min(H, roi["bottom"]))

    if roi["left"] > roi["right"]:
        roi["left"], roi["right"] = roi["right"], roi["left"]
    if roi["top"] > roi["bottom"]:
        roi["top"], roi["bottom"] = roi["bottom"], roi["top"]


def point_in_roi(x: float, y: float, roi: dict) -> bool:
    return (
        roi["left"] <= x <= roi["right"]
        and roi["top"] <= y <= roi["bottom"]
    )


def hit_test_roi(x: float, y: float):
    """Return (roi_id, mode) for moving / resizing_* or (None, None)."""
    for roi_id in reversed(list(state["rois"].keys())):
        roi = state["rois"][roi_id]
        left, top, right, bottom = (
            roi["left"],
            roi["top"],
            roi["right"],
            roi["bottom"],
        )

        near_left = abs(x - left) <= EDGE_TOL and top <= y <= bottom
        near_right = abs(x - right) <= EDGE_TOL and top <= y <= bottom
        near_top = abs(y - top) <= EDGE_TOL and left <= x <= right
        near_bottom = abs(y - bottom) <= EDGE_TOL and left <= x <= right

        if near_left:
            return roi_id, "resizing_left"
        if near_right:
            return roi_id, "resizing_right"
        if near_top:
            return roi_id, "resizing_top"
        if near_bottom:
            return roi_id, "resizing_bottom"
        if point_in_roi(x, y, roi):
            return roi_id, "moving"

    return None, None


# ============================================================
# 3. UI layout: controls, interactive image, ROI buttons
# ============================================================

info = ui.label().classes("m-2")
note_input = ui.input("Note for selected ROI").classes("m-2 w-64")

# Contrast control: range over [0, 100], mapped into [data_min, data_max]
data_min = float(np.nanmin(kym))
data_max = float(np.nanmax(kym))

contrast_range = ui.range(
    min=0,
    max=100,
    value={"min": 5, "max": 95},
).props('label="Contrast %"').classes("m-2 w-64")

# LUT selection
lut_select = ui.select(
    ["gray", "magma", "viridis", "plasma"],
    value="gray",
    label="LUT",
).classes("m-2 w-40")


def compute_vmin_vmax() -> tuple[float, float]:
    """Map contrast_range (0–100%) into actual vmin/vmax for kym."""
    low_pct = contrast_range.value["min"] / 100.0
    high_pct = contrast_range.value["max"] / 100.0
    vmin = data_min + low_pct * (data_max - data_min)
    vmax = data_min + high_pct * (data_max - data_min)
    if vmax <= vmin:
        vmax = vmin + 1e-6
    return vmin, vmax


# initial image
vmin0, vmax0 = compute_vmin_vmax()
pil_img = array_to_pil(kym, vmin=vmin0, vmax=vmax0, cmap=lut_select.value)  # type: ignore[arg-type]


def update_info_label():
    parts = []
    for roi_id, roi in state["rois"].items():
        parts.append(
            f"{roi_id}: "
            f"L={roi['left']:.1f}, T={roi['top']:.1f}, "
            f"R={roi['right']:.1f}, B={roi['bottom']:.1f}, "
            f"note='{roi['note']}'"
        )
    sel = state["selected_id"]
    info.text = f"Selected: {sel} | ROIs: " + ";  ".join(parts)


def redraw_svg():
    """Render all ROIs as <rect> tags on the interactive image overlay."""
    if interactive is None:
        return
    svg_parts = []
    for roi_id, roi in state["rois"].items():
        left, top, right, bottom = (
            roi["left"],
            roi["top"],
            roi["right"],
            roi["bottom"],
        )
        w = right - left
        h = bottom - top

        stroke = "red"
        if roi_id == state["selected_id"]:
            stroke = "lime"

        svg_parts.append(
            f'<rect x="{left}" y="{top}" width="{w}" height="{h}" '
            f'stroke="{stroke}" stroke-width="2" '
            f'fill="red" fill-opacity="0.15" />'
        )

    interactive.content = "".join(svg_parts)
    interactive.update()
    update_info_label()


def update_image():
    """Recompute PIL image from kym + contrast + LUT and refresh view."""
    if interactive is None:
        return
    vmin, vmax = compute_vmin_vmax()
    lut = lut_select.value or "gray"
    new_pil = array_to_pil(kym, vmin=vmin, vmax=vmax, cmap=lut)
    interactive.set_source(new_pil)
    # re-apply ROI overlay (set_source may recreate the DOM)
    redraw_svg()


def handle_mouse(e: events.MouseEventArguments) -> None:
    """Mouse handler uses image coords from e.image_x, e.image_y."""
    x = max(0, min(W, e.image_x))
    y = max(0, min(H, e.image_y))

    # --- mouse down ---
    if e.type == "mousedown" and e.button == 0:
        roi_id, mode = hit_test_roi(x, y)
        if roi_id is not None:
            state["selected_id"] = roi_id
            state["mode"] = mode
            state["start_x"], state["start_y"] = x, y
            state["orig_roi"] = state["rois"][roi_id].copy()
        else:
            roi_id = state["next_id"]
            state["next_id"] += 1
            state["selected_id"] = roi_id
            state["mode"] = "drawing"
            state["start_x"], state["start_y"] = x, y
            state["rois"][roi_id] = {
                "left": x,
                "top": y,
                "right": x,
                "bottom": y,
                "note": "",
            }

        redraw_svg()
        return

    # --- mouse move: left button held ---
    if e.type == "mousemove" and (e.buttons & 1):
        sid = state["selected_id"]
        if sid is None:
            return
        roi = state["rois"][sid]

        if state["mode"] == "drawing":
            x0, y0 = state["start_x"], state["start_y"]
            roi["left"], roi["top"] = min(x0, x), min(y0, y)
            roi["right"], roi["bottom"] = max(x0, x), max(y0, y)
            snap_roi_to_bounds(roi)
            redraw_svg()

        elif state["mode"] == "moving":
            dx = x - state["start_x"]
            dy = y - state["start_y"]
            o = state["orig_roi"]
            w = o["right"] - o["left"]
            h = o["bottom"] - o["top"]
            new_left = o["left"] + dx
            new_top = o["top"] + dy
            roi["left"] = new_left
            roi["top"] = new_top
            roi["right"] = new_left + w
            roi["bottom"] = new_top + h
            snap_roi_to_bounds(roi)
            redraw_svg()

        elif state["mode"] == "resizing_left":
            roi["left"] = x
            snap_roi_to_bounds(roi)
            redraw_svg()

        elif state["mode"] == "resizing_right":
            roi["right"] = x
            snap_roi_to_bounds(roi)
            redraw_svg()

        elif state["mode"] == "resizing_top":
            roi["top"] = y
            snap_roi_to_bounds(roi)
            redraw_svg()

        elif state["mode"] == "resizing_bottom":
            roi["bottom"] = y
            snap_roi_to_bounds(roi)
            redraw_svg()

        return

    # --- mouse up ---
    if e.type == "mouseup" and e.button == 0:
        sid = state["selected_id"]
        if state["mode"] == "drawing" and sid is not None:
            roi = state["rois"][sid]
            if roi["left"] == roi["right"] or roi["top"] == roi["bottom"]:
                del state["rois"][sid]
                state["selected_id"] = None

        state["mode"] = "idle"
        state["start_x"] = state["start_y"] = None
        state["orig_roi"] = None
        redraw_svg()
        return


# interactive image: start with initial LUT + contrast
interactive = ui.interactive_image(
    pil_img,
    cross=True,
    events=["mousedown", "mousemove", "mouseup"],
)
interactive.on_mouse(handle_mouse)


# ============================================================
# 4. Buttons / helper actions
# ============================================================

def delete_selected():
    sid = state["selected_id"]
    if sid is not None and sid in state["rois"]:
        del state["rois"][sid]
        state["selected_id"] = None
        redraw_svg()


def save_note():
    sid = state["selected_id"]
    if sid is not None and sid in state["rois"]:
        state["rois"][sid]["note"] = note_input.value or ""
        redraw_svg()


def snap_selected_to_bounds():
    sid = state["selected_id"]
    if sid is not None and sid in state["rois"]:
        snap_roi_to_bounds(state["rois"][sid])
        redraw_svg()


def set_full_image_roi():
    sid = state["selected_id"]
    if sid is not None and sid in state["rois"]:
        roi = state["rois"][sid]
        roi["left"] = 0
        roi["top"] = 0
        roi["right"] = W
        roi["bottom"] = H
        redraw_svg()


with ui.row().classes("m-2"):
    ui.button("Delete selected ROI", on_click=delete_selected)
    ui.button("Save note for selected", on_click=save_note)
    ui.button("Snap selected to bounds", on_click=snap_selected_to_bounds)
    ui.button("Set selected to full image", on_click=set_full_image_roi)

# re-render image when contrast or LUT change
contrast_range.on_value_change(lambda e: update_image())
lut_select.on_value_change(lambda e: update_image())

update_info_label()
ui.run()
