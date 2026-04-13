"""Diameter Explorer v2: Uses ImageRoiWidget and LinePlotWidget from nicewidgets."""

from __future__ import annotations

import logging

from nicegui import ui

from kymflow.core.analysis.diameter_analysis import PostFilterParams
from kymflow.core.analysis.diameter_analysis import DiameterDetectionParams, DiameterMethod, PostFilterParams, SyntheticKymographParams
from kymflow.core.analysis.diameter_analysis.logging_setup import configure_logging

from kymflow.core.analysis.diameter_analysis.gui.models import AppState
from kymflow.core.analysis.diameter_analysis.gui.controllers_v2 import AppControllerV2
from kymflow.core.analysis.diameter_analysis.gui.views_v2 import build_home_page_v2
from kymflow.core.analysis.diameter_analysis.gui.config import SEED_FOLDER

logger = logging.getLogger(__name__)


def _make_default_state() -> AppState:
    state = AppState()

    # Synthetic defaults (best effort)
    SYNTH_PRESET_HARD_JITTER = {
        "n_time": 10000,
        "n_space": 128,
        "seconds_per_line": 0.001,
        "um_per_pixel": 0.15,
        "output_dtype": "uint16",
        "effective_bits": 11,
        "baseline_counts": 50.0,
        "signal_peak_counts": 100.0,
        "bg_gaussian_sigma_frac": 0.02,
        "speckle_sigma_frac": 0.34,
        "wall_jitter_px": 2.2,
        "clip": True,
        "bright_band_enabled": False,
    }

    state.synthetic_params = SyntheticKymographParams(**SYNTH_PRESET_HARD_JITTER)

    # Detection defaults (robust to param name changes)
    kwargs = {}
    fields = getattr(DiameterDetectionParams, "__dataclass_fields__", {})
    if "diameter_method" in fields:
        kwargs["diameter_method"] = DiameterMethod.GRADIENT_EDGES
    elif "method" in fields:
        kwargs["method"] = DiameterMethod.GRADIENT_EDGES

    state.detection_params = DiameterDetectionParams(**kwargs)

    # Post-filter defaults (best effort; try a few import locations)
    # PostFilterParams = None
    # for mod, name in [
    #     ("post_filter", "PostFilterParams"),
    #     ("diameter_analysis", "PostFilterParams"),
    #     ("diameter_post_filter", "PostFilterParams"),
    # ]:
    #     try:
    #         m = __import__(mod, fromlist=[name])
    #         PostFilterParams = getattr(m, name)
    #         break
    #     except Exception:
    #         continue

    # if PostFilterParams is None:
    #     raise ImportError("PostFilterParams not found in known modules")
    state.post_filter_params = PostFilterParams()  # type: ignore[call-arg]

    return state


@ui.page("/")
def home_v2() -> None:
    state = _make_default_state()
    controller = AppControllerV2(state)
    controller.initialize_kym_list(SEED_FOLDER)
    controller._rebuild_figures()
    build_home_page_v2(controller)


def main() -> None:
    configure_logging()
    ui.run(
        title="Diameter Explorer v2",
        reload=False,
        native=True,
        window_size=(2000, 1400),
    )


if __name__ in {"__main__", "__mp_main__"}:
    main()
