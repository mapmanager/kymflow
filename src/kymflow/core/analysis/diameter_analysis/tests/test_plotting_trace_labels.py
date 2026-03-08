from __future__ import annotations

from dataclasses import dataclass

from diameter_analysis import PostFilterParams
from gui.plotting import make_diameter_figure_dict


@dataclass(frozen=True)
class _Row:
    diameter_um: float
    roi_id: int
    channel_id: int


def test_diameter_trace_name_includes_roi_and_channel() -> None:
    results = [
        _Row(diameter_um=5.0, roi_id=7, channel_id=3),
        _Row(diameter_um=5.5, roi_id=7, channel_id=3),
    ]

    fig = make_diameter_figure_dict(
        results,
        seconds_per_line=0.01,
        um_per_pixel=0.5,
    )

    assert fig["data"][0]["name"] == "Diameter (roi 7, ch 3)"


def test_filtered_trace_name_includes_roi_and_channel() -> None:
    results = [
        _Row(diameter_um=5.0, roi_id=2, channel_id=4),
        _Row(diameter_um=10.0, roi_id=2, channel_id=4),
        _Row(diameter_um=5.1, roi_id=2, channel_id=4),
    ]

    fig = make_diameter_figure_dict(
        results,
        seconds_per_line=0.01,
        um_per_pixel=0.5,
        post_filter_params=PostFilterParams(enabled=True),
    )

    assert len(fig["data"]) == 2
    assert fig["data"][1]["name"] == "Diameter filtered (roi 2, ch 4)"
