from __future__ import annotations

from typing import Optional, Callable

import numpy as np

from .models import AppState
from .plotting import (
    make_kymograph_figure_dict,
    overlay_edges_on_kymograph_dict,
    set_xrange,
    make_diameter_figure_dict,
)


class AppController:
    def __init__(
        self,
        state: AppState,
        *,
        on_state_change: Optional[Callable[[AppState], None]] = None,
    ) -> None:
        self.state = state
        self._on_state_change = on_state_change

        self.fig_img: Optional[dict] = None
        self.fig_line: Optional[dict] = None

    def _emit(self) -> None:
        if self._on_state_change:
            self._on_state_change(self.state)

    def set_img(
        self,
        img: np.ndarray,
        *,
        seconds_per_line: float,
        um_per_pixel: float,
        polarity: str = "bright_on_dark",
        source: str = "synthetic",
        path: str | None = None,
        loaded_shape: tuple[int, int] | None = None,
        loaded_dtype: str | None = None,
        loaded_min: float | None = None,
        loaded_max: float | None = None,
    ) -> None:
        self.state.img = img
        self.state.seconds_per_line = float(seconds_per_line)
        self.state.um_per_pixel = float(um_per_pixel)
        self.state.polarity = str(polarity)
        self.state.source = str(source)
        self.state.loaded_path = None if path is None else str(path)
        self.state.loaded_shape = loaded_shape
        self.state.loaded_dtype = loaded_dtype
        self.state.loaded_min = loaded_min
        self.state.loaded_max = loaded_max
        self.state.tiff_error = None
        self.state.results = None
        self._rebuild_figures()
        self._emit()

    def generate_synthetic(self) -> None:
        from synthetic_kymograph import generate_synthetic_kymograph

        if self.state.synthetic_params is None:
            raise RuntimeError("synthetic_params not set")

        payload = generate_synthetic_kymograph(synthetic_params=self.state.synthetic_params)
        img = payload["kymograph"]

        meta = payload.get("meta", {}) if isinstance(payload, dict) else {}
        seconds_per_line = float(meta.get("seconds_per_line", payload.get("seconds_per_line", self.state.seconds_per_line)))
        um_per_pixel = float(meta.get("um_per_pixel", payload.get("um_per_pixel", self.state.um_per_pixel)))

        self.set_img(
            img,
            seconds_per_line=seconds_per_line,
            um_per_pixel=um_per_pixel,
            polarity=str(payload.get("polarity", "bright_on_dark")),
            source="synthetic",
            path=None,
        )

    def load_tiff(self, path: str, *, seconds_per_line: float, um_per_pixel: float) -> None:
        from tiff_loader import load_tiff_kymograph

        payload = load_tiff_kymograph(
            path,
            seconds_per_line=seconds_per_line,
            um_per_pixel=um_per_pixel,
            polarity=self.state.polarity,
        )
        self.set_img(
            payload.kymograph,
            seconds_per_line=payload.seconds_per_line,
            um_per_pixel=payload.um_per_pixel,
            polarity=payload.polarity,
            source=payload.source,
            path=payload.path,
            loaded_shape=payload.loaded_shape,
            loaded_dtype=payload.loaded_dtype,
            loaded_min=payload.loaded_min,
            loaded_max=payload.loaded_max,
        )

    def detect(self) -> None:
        if self.state.img is None:
            raise RuntimeError("no image loaded")
        if self.state.detection_params is None:
            raise RuntimeError("detection_params not set")
        if self.state.is_busy:
            raise RuntimeError("busy")

        from diameter_analysis import DiameterAnalyzer

        self.state.is_busy = True
        self._emit()
        try:
            analyzer = DiameterAnalyzer(
                self.state.img,
                seconds_per_line=self.state.seconds_per_line,
                um_per_pixel=self.state.um_per_pixel,
                polarity=self.state.polarity,
            )

            res = analyzer.analyze(params=self.state.detection_params)
            self.state.results = res
            self._rebuild_figures()
        finally:
            self.state.is_busy = False
            self._emit()

    def apply_post_filter_only(self) -> None:
        # Rebuild figures using existing results and current post_filter_params
        self._rebuild_figures()
        self._emit()

    def _extract_overlays_um(self) -> tuple[np.ndarray, Optional[np.ndarray], Optional[np.ndarray], Optional[np.ndarray]]:
        img = self.state.img
        if img is None:
            raise RuntimeError("no img")
        n_time = img.shape[0]
        seconds = np.arange(n_time, dtype=float) * float(self.state.seconds_per_line)

        res = self.state.results
        if res is None:
            return seconds, None, None, None

        um_per_pixel = float(self.state.um_per_pixel)

        try:
            import pandas as pd  # type: ignore
            if isinstance(res, pd.DataFrame):
                df = res
                left = df.get("left_edge_um", None)
                right = df.get("right_edge_um", None)
                center = df.get("center_um", None)
                if left is None and "left_edge_px" in df.columns:
                    left = df["left_edge_px"] * um_per_pixel
                if right is None and "right_edge_px" in df.columns:
                    right = df["right_edge_px"] * um_per_pixel
                if center is None and left is not None and right is not None:
                    center = 0.5 * (left + right)
                return seconds, (
                    None if left is None else left.to_numpy(dtype=float, copy=False)
                ), (
                    None if right is None else right.to_numpy(dtype=float, copy=False)
                ), (
                    None if center is None else center.to_numpy(dtype=float, copy=False)
                )
        except Exception:
            pass

        if isinstance(res, list) and len(res) > 0:
            def _get(attr: str) -> Optional[np.ndarray]:
                vals = []
                ok = True
                for r in res:
                    if not hasattr(r, attr):
                        ok = False
                        break
                    v = getattr(r, attr)
                    vals.append(np.nan if v is None else float(v))
                if not ok:
                    return None
                return np.asarray(vals, dtype=float)

            left_px = _get("left_edge_px")
            right_px = _get("right_edge_px")
            center_px = _get("center_px")

            left_um = None if left_px is None else left_px * um_per_pixel
            right_um = None if right_px is None else right_px * um_per_pixel
            if center_px is not None:
                center_um = center_px * um_per_pixel
            elif left_um is not None and right_um is not None:
                center_um = 0.5 * (left_um + right_um)
            else:
                center_um = None

            return seconds, left_um, right_um, center_um

        return seconds, None, None, None

    def _rebuild_figures(self) -> None:
        if self.state.img is None:
            self.fig_img = None
            self.fig_line = None
            return

        seconds, left_um, right_um, center_um = self._extract_overlays_um()

        base = make_kymograph_figure_dict(
            self.state.img,
            seconds_per_line=self.state.seconds_per_line,
            um_per_pixel=self.state.um_per_pixel,
        )

        if not self.state.gui.show_center_overlay:
            center_um = None

        self.fig_img = overlay_edges_on_kymograph_dict(
            base, seconds=seconds, left_um=left_um, right_um=right_um, center_um=center_um
        )

        self.fig_line = make_diameter_figure_dict(
            self.state.results,
            seconds_per_line=self.state.seconds_per_line,
            um_per_pixel=self.state.um_per_pixel,
            post_filter_params=self.state.post_filter_params,
        )

        if self.state.x_range and self.fig_img and self.fig_line:
            x0, x1 = self.state.x_range
            self.fig_img = set_xrange(self.fig_img, x0, x1)
            self.fig_line = set_xrange(self.fig_line, x0, x1)

    def on_relayout(self, source: str, relayout: dict) -> None:
        if self.state._syncing_axes:
            return

        new_range: tuple[float, float] | None = None
        autorange_reset = False

        for axis_name in ("xaxis", "xaxis2"):
            auto_key = f"{axis_name}.autorange"
            if auto_key in relayout and bool(relayout[auto_key]):
                autorange_reset = True
                break

            k0 = f"{axis_name}.range[0]"
            k1 = f"{axis_name}.range[1]"
            if k0 in relayout and k1 in relayout:
                new_range = (float(relayout[k0]), float(relayout[k1]))
                break

            k_list = f"{axis_name}.range"
            if k_list in relayout:
                r = relayout[k_list]
                if isinstance(r, (list, tuple)) and len(r) == 2:
                    new_range = (float(r[0]), float(r[1]))
                    break

        if not autorange_reset and new_range is None:
            return
        if autorange_reset and self.state.x_range is None:
            return
        if new_range is not None and self.state.x_range == new_range:
            return

        self.state._syncing_axes = True
        try:
            self.state.x_range = None if autorange_reset else new_range
            self._rebuild_figures()
            self._emit()
        finally:
            self.state._syncing_axes = False
