from __future__ import annotations

import pytest

from kymflow.core.analysis.diameter_analysis import PostFilterParams, PostFilterType


def test_post_filter_params_roundtrip() -> None:
    obj = PostFilterParams(
        enabled=True,
        filter_type=PostFilterType.HAMPEL,
        kernel_size=5,
        hampel_n_sigma=4.5,
        hampel_scale="std",
    )
    payload = obj.to_dict()
    loaded = PostFilterParams.from_dict(payload)
    assert loaded == obj


def test_post_filter_params_from_dict_ignores_unknown_keys() -> None:
    payload = {
        "enabled": True,
        "filter_type": "median",
        "kernel_size": 7,
        "unknown_key": "ignore-me",
    }
    loaded = PostFilterParams.from_dict(payload)
    assert loaded.enabled is True
    assert loaded.filter_type == PostFilterType.MEDIAN
    assert loaded.kernel_size == 7
    assert loaded.hampel_n_sigma == 3.0
    assert loaded.hampel_scale == "mad"


def test_post_filter_params_invalid_enum_raises_clear_value_error() -> None:
    with pytest.raises(ValueError, match="Invalid enum value"):
        PostFilterParams.from_dict({"filter_type": "not-a-filter"})


def test_post_filter_params_defaults_apply_for_missing_keys() -> None:
    loaded = PostFilterParams.from_dict({"enabled": True})
    assert loaded == PostFilterParams(enabled=True)
