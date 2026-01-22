# plotly_movie_v2_sandbox.py
"""
NiceGUI + Plotly sandbox that matches the *style* of `plot_image_line_plotly_v2()`:
- Top subplot: heatmap (kymograph-like image)
- Bottom subplot: one line plot (time series)
- Shared x-axis (time in seconds)
- "Movie" playback pans the viewport by updating x-axis ranges (keeps zoom width fixed)

Run:
    uv run python plotly_movie_v2_sandbox.py
or:
    python plotly_movie_v2_sandbox.py
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from nicegui import ui


# ----------------------------
# Synthetic data + figure
# ----------------------------

@dataclass
class SandboxConfig:
    """Configuration for the sandbox data + playback.

    Attributes:
        n_time: Number of time samples.
        n_space: Number of spatial samples (heatmap y dimension).
        samples_per_second: Sampling rate (Hz). Time axis is derived from this.
        fps: Target frames-per-second for viewport updates.
        step_seconds: Pan amount per frame (seconds).
        loop: If True, wrap back to start when reaching the end.
        initial_window_seconds: Default playback window if user hasn't zoomed yet.
    """
    n_time: int = 10_000
    n_space: int = 50
    samples_per_second: float = 200.0

    fps: float = 30.0
    step_seconds: float = 0.05
    loop: bool = True
    initial_window_seconds: float = 2.0


class SyntheticKymo:
    """Generate a synthetic kymograph-like heatmap + a derived time-series."""

    def __init__(self, cfg: SandboxConfig) -> None:
        self.cfg = cfg
        self.t_s: np.ndarray
        self.y_space: np.ndarray
        self.z: np.ndarray  # shape: (n_space, n_time) => heatmap z
        self.line_y: np.ndarray  # shape: (n_time,)
        self._make()

    def _make(self) -> None:
        cfg = self.cfg
        t = np.arange(cfg.n_time, dtype=np.float64) / float(cfg.samples_per_second)
        y = np.arange(cfg.n_space, dtype=np.float64)

        # Create moving bands + noise, so the heatmap "looks alive"
        # z[y, t]
        Y = y[:, None]
        T = t[None, :]

        rng = np.random.default_rng(0)

        # Two moving gaussian ridges
        center1 = (cfg.n_space * 0.25) + (cfg.n_space * 0.10) * np.sin(2 * np.pi * 0.12 * T)
        center2 = (cfg.n_space * 0.70) + (cfg.n_space * 0.12) * np.sin(2 * np.pi * 0.07 * T + 1.2)

        ridge1 = np.exp(-0.5 * ((Y - center1) / 2.0) ** 2)
        ridge2 = 0.8 * np.exp(-0.5 * ((Y - center2) / 3.0) ** 2)

        # Slow drift + pixel noise
        drift = 0.15 * np.sin(2 * np.pi * 0.02 * T)
        noise = 0.08 * rng.standard_normal(size=(cfg.n_space, cfg.n_time))

        z = ridge1 + ridge2 + drift + noise
        z = np.clip(z, -0.5, 2.0)

        # A time-series derived from the kymograph: mean over a band
        band = z[int(cfg.n_space * 0.30) : int(cfg.n_space * 0.45), :]
        line = band.mean(axis=0)

        self.t_s = t
        self.y_space = y
        self.z = z
        self.line_y = line

    @property
    def t_min(self) -> float:
        return float(self.t_s[0])

    @property
    def t_max(self) -> float:
        return float(self.t_s[-1])


def plot_image_line_plotly_v2_sandbox(
    data: SyntheticKymo,
    colorscale: str = "Gray",
    zmin: Optional[float] = None,
    zmax: Optional[float] = None,
) -> go.Figure:
    """Create a Plotly figure in the same spirit as `plot_image_line_plotly_v2()`.

    Args:
        data: SyntheticKymo with time axis, space axis, heatmap z, and line series.
        colorscale: Plotly colorscale name.
        zmin: Optional heatmap min clamp.
        zmax: Optional heatmap max clamp.

    Returns:
        Plotly Figure with (row1) heatmap and (row2) line plot, shared x-axis.
    """
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.55, 0.45],
    )

    # Heatmap (top)
    heatmap_kwargs: dict = {
        "z": data.z,
        "x": data.t_s,       # time on x
        "y": data.y_space,   # space on y
        "colorscale": colorscale,
        "showscale": False,
    }
    if zmin is not None:
        heatmap_kwargs["zmin"] = zmin
    if zmax is not None:
        heatmap_kwargs["zmax"] = zmax

    fig.add_trace(go.Heatmap(**heatmap_kwargs), row=1, col=1)

    # Line plot (bottom)
    fig.add_trace(
        go.Scatter(
            x=data.t_s,
            y=data.line_y,
            mode="lines",
        ),
        row=2,
        col=1,
    )

    # Axis labels
    fig.update_xaxes(title_text="Time (s)", row=2, col=1, showgrid=True)
    fig.update_yaxes(title_text="Space (a.u.)", row=1, col=1, showgrid=False)
    fig.update_yaxes(title_text="Mean intensity (a.u.)", row=2, col=1, showgrid=True)

    # Match your pattern: zoom + some modebar extras
    fig.update_layout(
        height=650,
        margin=dict(l=10, r=10, t=10, b=10),
        dragmode="zoom",
        modebar_add=["zoomInX", "zoomOutX", "zoomInY", "zoomOutY"],
        uirevision="kymflow-plot",
        showlegend=False,
    )
    fig.update_xaxes(constrain="range")
    fig.update_yaxes(constrain="range")

    return fig


# ----------------------------
# Viewport movie player
# ----------------------------

@dataclass
class ViewWindow:
    """A fixed-width view window over time.

    Attributes:
        start_s: Left edge of window in seconds.
        width_s: Window width in seconds.
    """
    start_s: float
    width_s: float


class PlotlyViewportMovie:
    """Pan a fixed-width time window across a Plotly figure embedded in NiceGUI.

    This updates both x axes (xaxis + xaxis2) so it behaves robustly with subplots.
    """

    def __init__(self, plot_div_id: str, data: SyntheticKymo, cfg: SandboxConfig) -> None:
        self._plot_div_id = plot_div_id
        self._data = data
        self._cfg = cfg

        self._playing: bool = False
        self._window: Optional[ViewWindow] = None

        # UI-bound state
        self.fps: float = cfg.fps
        self.step_seconds: float = cfg.step_seconds
        self.loop: bool = cfg.loop

    async def _js_get_current_xrange(self) -> Optional[Tuple[float, float]]:
        """Read current x range from the browser Plotly graph.

        Returns:
            (x0, x1) as floats if available, otherwise None.
        """
        js = f"""
        (() => {{
          const gd = document.getElementById({self._plot_div_id!r});
          if (!gd || !gd.layout) return null;

          // Prefer xaxis2 (bottom) if present; otherwise xaxis.
          const ax = (gd.layout.xaxis2 && gd.layout.xaxis2.range) ? gd.layout.xaxis2 : gd.layout.xaxis;
          if (!ax || !ax.range || ax.range.length !== 2) return null;

          const x0 = Number(ax.range[0]);
          const x1 = Number(ax.range[1]);
          if (!Number.isFinite(x0) || !Number.isFinite(x1)) return null;
          return [x0, x1];
        }})()
        """
        res = await ui.run_javascript(js)
        if not res:
            return None
        return float(res[0]), float(res[1])

    async def _js_set_xrange(self, x0: float, x1: float) -> None:
        """Set x range on both subplots."""
        js = f"""
        (() => {{
          const gd = document.getElementById({self._plot_div_id!r});
          if (!gd) return;
          Plotly.relayout(gd, {{
            'xaxis.range': [{x0}, {x1}],
            'xaxis2.range': [{x0}, {x1}],
          }});
        }})()
        """
        await ui.run_javascript(js)

    async def use_current_zoom_as_window(self) -> None:
        """Capture the user's current zoom window and store it as playback window.

        If the plot does not have an explicit range (no zoom yet), uses a default window.
        """
        xr = await self._js_get_current_xrange()
        if xr is None:
            start = self._data.t_min
            width = max(float(self._cfg.initial_window_seconds), 1e-6)
            self._window = ViewWindow(start_s=start, width_s=width)
            await self._js_set_xrange(start, start + width)
            return

        x0, x1 = xr
        start = min(x0, x1)
        width = max(abs(x1 - x0), 1e-9)
        self._window = ViewWindow(start_s=start, width_s=width)

    async def reset_full(self) -> None:
        """Reset to full time range and clear playback window."""
        self._window = None
        await self._js_set_xrange(self._data.t_min, self._data.t_max)

    async def play(self) -> None:
        """Start playback (panning)."""
        if self._playing:
            return
        if self._window is None:
            await self.use_current_zoom_as_window()
        self._playing = True

    def pause(self) -> None:
        """Pause playback."""
        self._playing = False

    async def tick(self) -> None:
        """Advance one playback step if playing."""
        if not self._playing or self._window is None:
            return

        start = self._window.start_s + float(self.step_seconds)
        width = self._window.width_s
        end = start + width

        t_min = self._data.t_min
        t_max = self._data.t_max

        if end > t_max:
            if self.loop:
                start = t_min
                end = start + width
            else:
                start = max(t_max - width, t_min)
                end = start + width
                self._playing = False

        self._window = ViewWindow(start_s=start, width_s=width)
        await self._js_set_xrange(start, end)


# ----------------------------
# NiceGUI app
# ----------------------------

def main() -> None:
    cfg = SandboxConfig(
        n_time=10_000,
        n_space=50,
        samples_per_second=200.0,  # <-- set this to your acquisition rate
        fps=30.0,
        step_seconds=0.05,
        loop=True,
        initial_window_seconds=2.0,
    )
    data = SyntheticKymo(cfg)
    fig = plot_image_line_plotly_v2_sandbox(data, colorscale="Gray")

    PLOT_DIV_ID = "plotly_kym_movie"

    ui.label("plot_image_line_plotly_v2-style sandbox: heatmap + line plot + x-axis movie").classes(
        "text-lg font-medium"
    )

    with ui.row().classes("w-full gap-6 items-start"):
        with ui.column().classes("w-full"):
            plot = ui.plotly(fig).classes("w-full")
            # Deterministic DOM id for Plotly relayout JS
            plot.props(f"id={PLOT_DIV_ID}")

        with ui.column().classes("w-96 gap-3"):
            ui.label("Controls").classes("font-semibold")

            player = PlotlyViewportMovie(PLOT_DIV_ID, data, cfg)

            with ui.row().classes("gap-2"):
                ui.button("Use current zoom as window", on_click=player.use_current_zoom_as_window)
                ui.button("Reset full", on_click=player.reset_full)

            with ui.row().classes("gap-2"):
                ui.button("Play", on_click=player.play)
                ui.button("Pause", on_click=player.pause)

            fps_slider = ui.slider(min=1, max=60, value=cfg.fps).props("label-always")
            fps_slider.bind_value(player, "fps")
            ui.label().bind_text_from(fps_slider, "value", backward=lambda v: f"FPS: {float(v):.1f}")

            step_slider = ui.slider(min=0.001, max=1.0, value=cfg.step_seconds).props("label-always")
            step_slider.bind_value(player, "step_seconds")
            ui.label().bind_text_from(
                step_slider, "value", backward=lambda v: f"Step: {float(v):.3f} s / frame"
            )

            loop_switch = ui.switch("Loop at end", value=cfg.loop)
            loop_switch.bind_value(player, "loop")

            ui.separator()
            ui.markdown(
                "- Zoom to a time window (drag zoom).\n"
                "- Click **Use current zoom as window**.\n"
                "- Click **Play** to pan through time while keeping that zoom width fixed.\n"
            ).classes("text-sm")

    # Timer strategy: tick frequently and throttle to requested FPS without recreating timers.
    state = {"accum": 0.0}
    base_dt = 0.02  # 50 Hz timer

    async def on_timer() -> None:
        state["accum"] += base_dt
        target_dt = 1.0 / max(float(player.fps), 1.0)
        if state["accum"] >= target_dt:
            state["accum"] = 0.0
            await player.tick()

    ui.timer(base_dt, on_timer)

    ui.run(title="Plotly Movie v2 Sandbox")


if __name__ in {"__main__", "__mp_main__"}:
    main()