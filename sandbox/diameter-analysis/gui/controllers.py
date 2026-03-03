from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Callable

import numpy as np

from .models import AppState
from .plotting import (
    make_kymograph_figure_dict,
    overlay_edges_on_kymograph_dict,
    set_xrange,
    make_diameter_figure_dict,
)


class _ManualUnitSelection:
    def __init__(self, path: str, seconds_per_line: float, um_per_pixel: float) -> None:
        self.path = path
        self.seconds_per_line = float(seconds_per_line)
        self.um_per_pixel = float(um_per_pixel)


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
        polarity: str = "bright_on_dark",
        source: str = "synthetic",
        path: str | None = None,
        loaded_shape: tuple[int, int] | None = None,
        loaded_dtype: str | None = None,
        loaded_min: float | None = None,
        loaded_max: float | None = None,
        selected_kym_image: Any | None = None,
    ) -> None:
        self.state.img = img
        self.state.polarity = str(polarity)
        self.state.source = str(source)
        self.state.selected_kym_image = selected_kym_image
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

        self.set_img(
            img,
            polarity=str(payload.get("polarity", "bright_on_dark")),
            source="synthetic",
            path=None,
            selected_kym_image=None,
        )

    @staticmethod
    def _coerce_positive_float(value: Any) -> float | None:
        try:
            out = float(value)
        except Exception:
            return None
        if not np.isfinite(out) or out <= 0:
            return None
        return out

    def resolve_units(
        self,
        *,
        selected_kym_image: Any | None = None,
        source: str | None = None,
    ) -> tuple[float, float]:
        selected = selected_kym_image if selected_kym_image is not None else self.state.selected_kym_image
        if selected is not None:
            kym_seconds = self._coerce_positive_float(getattr(selected, "seconds_per_line", None))
            kym_um = self._coerce_positive_float(getattr(selected, "um_per_pixel", None))
            if kym_seconds is not None and kym_um is not None:
                return kym_seconds, kym_um
            raise RuntimeError("selected_kym_image is missing valid units")

        active_source = str(source if source is not None else self.state.source)
        if active_source == "synthetic":
            params = self.state.synthetic_params
            if params is None:
                raise RuntimeError("synthetic_params not set")
            syn_seconds = self._coerce_positive_float(getattr(params, "seconds_per_line", None))
            syn_um = self._coerce_positive_float(getattr(params, "um_per_pixel", None))
            if syn_seconds is None or syn_um is None:
                raise RuntimeError("synthetic_params missing valid units")
            return syn_seconds, syn_um
        raise RuntimeError("No canonical units available for non-synthetic source without selected_kym_image")

    def load_tiff(
        self,
        path: str,
        *,
        seconds_per_line: float | None = None,
        um_per_pixel: float | None = None,
        selected_kym_image: Any | None = None,
    ) -> None:
        from tiff_loader import load_tiff_kymograph

        resolved_seconds: float
        resolved_um: float
        if selected_kym_image is not None:
            resolved_seconds, resolved_um = self.resolve_units(selected_kym_image=selected_kym_image)
        else:
            resolved_seconds = self._coerce_positive_float(seconds_per_line) or 0.0
            resolved_um = self._coerce_positive_float(um_per_pixel) or 0.0
            if resolved_seconds <= 0.0 or resolved_um <= 0.0:
                raise RuntimeError(
                    "load_tiff requires selected_kym_image with units, or explicit positive seconds_per_line and um_per_pixel"
                )
            selected_kym_image = _ManualUnitSelection(
                path=path,
                seconds_per_line=resolved_seconds,
                um_per_pixel=resolved_um,
            )
        payload = load_tiff_kymograph(
            path,
            seconds_per_line=resolved_seconds,
            um_per_pixel=resolved_um,
            polarity=self.state.polarity,
        )
        self.set_img(
            payload.kymograph,
            polarity=payload.polarity,
            source=payload.source,
            path=payload.path,
            loaded_shape=payload.loaded_shape,
            loaded_dtype=payload.loaded_dtype,
            loaded_min=payload.loaded_min,
            loaded_max=payload.loaded_max,
            selected_kym_image=selected_kym_image,
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
            seconds_per_line, um_per_pixel = self.resolve_units(source=self.state.source)
            analyzer = DiameterAnalyzer(
                self.state.img,
                seconds_per_line=seconds_per_line,
                um_per_pixel=um_per_pixel,
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
        seconds_per_line, um_per_pixel = self.resolve_units(source=self.state.source)
        seconds = np.arange(n_time, dtype=float) * float(seconds_per_line)

        res = self.state.results
        if res is None:
            return seconds, None, None, None

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

        seconds_per_line, um_per_pixel = self.resolve_units(source=self.state.source)
        seconds, left_um, right_um, center_um = self._extract_overlays_um()

        base = make_kymograph_figure_dict(
            self.state.img,
            seconds_per_line=seconds_per_line,
            um_per_pixel=um_per_pixel,
            title=self.kymograph_title(),
        )

        if not self.state.gui.show_center_overlay:
            center_um = None

        self.fig_img = overlay_edges_on_kymograph_dict(
            base, seconds=seconds, left_um=left_um, right_um=right_um, center_um=center_um
        )

        self.fig_line = make_diameter_figure_dict(
            self.state.results,
            seconds_per_line=seconds_per_line,
            um_per_pixel=um_per_pixel,
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

    def kymograph_title(self) -> str:
        selected = self.state.selected_kym_image
        selected_path = getattr(selected, "path", None) if selected is not None else None
        if selected_path is not None:
            return Path(str(selected_path)).name
        if self.state.source == "synthetic":
            return "synthetic"
        if self.state.loaded_path:
            return Path(self.state.loaded_path).name
        return "kymograph"
