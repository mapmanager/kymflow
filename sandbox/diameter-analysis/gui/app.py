from __future__ import annotations

import logging

from nicegui import ui

from .models import AppState
from .controllers import AppController
from .file_table_integration import build_kym_image_list
from .logging_setup import configure_logging
from .views import build_home_page

logger = logging.getLogger(__name__)


def _make_default_state() -> AppState:
    state = AppState()

    # Synthetic defaults (best effort)
    try:
        from synthetic_kymograph import SyntheticKymographParams
        state.synthetic_params = SyntheticKymographParams(
            n_time=10000,
            n_space=128,
            seconds_per_line=0.001,
            um_per_pixel=0.15,
            polarity="bright_on_dark",
            seed=1,
            output_dtype="uint16",
            effective_bits=11,
            baseline_counts=50.0,
            signal_peak_counts=100.0,
            clip=True,
            bg_gaussian_sigma_counts=0.0,
            bg_gaussian_sigma_frac=0.02,
            bg_drift_amp_counts=0.0,
            bg_drift_period_lines=120,
            fixed_pattern_col_sigma_counts=0.0,
            speckle_sigma_frac=0.34,
            wall_jitter_px=2.2,
            bright_band_enabled=False,
            bright_band_x_center_px=96,
            bright_band_width_px=6,
            bright_band_amplitude_counts=0.0,
            bright_band_saturate=False,
        )
    except Exception as e:
        logger.warning("Failed to import SyntheticKymographParams: %s", e)
        state.synthetic_params = None

    # Detection defaults (robust to param name changes)
    try:
        from diameter_analysis import DiameterDetectionParams, DiameterMethod

        kwargs = {}
        fields = getattr(DiameterDetectionParams, "__dataclass_fields__", {})
        if "diameter_method" in fields:
            kwargs["diameter_method"] = DiameterMethod.GRADIENT_EDGES
        elif "method" in fields:
            kwargs["method"] = DiameterMethod.GRADIENT_EDGES

        state.detection_params = DiameterDetectionParams(**kwargs)
    except Exception as e:
        logger.warning("Failed to build detection params: %s", e)
        state.detection_params = None

    # Post-filter defaults (best effort; try a few import locations)
    try:
        PostFilterParams = None
        for mod, name in [
            ("post_filter", "PostFilterParams"),
            ("diameter_analysis", "PostFilterParams"),
            ("diameter_post_filter", "PostFilterParams"),
        ]:
            try:
                m = __import__(mod, fromlist=[name])
                PostFilterParams = getattr(m, name)
                break
            except Exception:
                continue

        if PostFilterParams is None:
            raise ImportError("PostFilterParams not found in known modules")
        state.post_filter_params = PostFilterParams()  # type: ignore[call-arg]
    except Exception as e:
        logger.warning("Failed to build post_filter_params: %s", e)
        state.post_filter_params = None

    kym_image_list, warning = build_kym_image_list()
    state.kym_image_list = kym_image_list
    state.file_table_warning = warning
    if warning:
        logger.warning(warning)

    return state


@ui.page("/")
def home() -> None:
    state = _make_default_state()
    controller = AppController(state)
    controller._rebuild_figures()
    build_home_page(controller)


def main() -> None:
    configure_logging()
    ui.run(title="Diameter Explorer",
           reload=False,
           native=True,
           window_size=(1200, 1000),
    )


if __name__ in {"__main__", "__mp_main__"}:
    main()
