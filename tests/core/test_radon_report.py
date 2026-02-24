"""Tests for RadonReport dataclass."""

from __future__ import annotations

import pytest

from kymflow.core.image_loaders.radon_report import RadonReport


def test_radon_report_rel_path_field() -> None:
    """Test that RadonReport has rel_path field and it serializes."""
    r = RadonReport(roi_id=1, path="/a/b/c/file.tif", rel_path="c/file.tif")
    assert r.rel_path == "c/file.tif"
    d = r.to_dict()
    assert "rel_path" in d
    assert d["rel_path"] == "c/file.tif"


def test_radon_report_from_dict_with_rel_path() -> None:
    """Test RadonReport.from_dict with rel_path."""
    data = {
        "roi_id": 1,
        "vel_mean": 1.5,
        "path": "/a/b/file.tif",
        "rel_path": "b/file.tif",
    }
    r = RadonReport.from_dict(data)
    assert r.roi_id == 1
    assert r.vel_mean == 1.5
    assert r.path == "/a/b/file.tif"
    assert r.rel_path == "b/file.tif"


def test_radon_report_from_dict_ignores_unknown_keys() -> None:
    """Test that from_dict ignores unknown keys."""
    data = {"roi_id": 1, "unknown_field": "ignored", "other_extra": 999}
    r = RadonReport.from_dict(data)
    assert r.roi_id == 1
    assert not hasattr(r, "unknown_field")


def test_radon_report_from_dict_requires_roi_id() -> None:
    """Test that from_dict raises if roi_id is missing."""
    with pytest.raises(ValueError, match="roi_id is required"):
        RadonReport.from_dict({"path": "/a.tif"})


def test_radon_report_from_dict_handles_nan() -> None:
    """Test that from_dict treats float NaN as None."""
    data = {"roi_id": 1, "vel_mean": float("nan"), "path": "/a.tif"}
    r = RadonReport.from_dict(data)
    assert r.roi_id == 1
    assert r.vel_mean is None
    assert r.path == "/a.tif"


def test_radon_report_channel_field() -> None:
    """Test that RadonReport has channel field and it serializes."""
    r = RadonReport(roi_id=1, channel=2, path="/a/b/file.tif")
    assert r.channel == 2
    d = r.to_dict()
    assert "channel" in d
    assert d["channel"] == 2


def test_radon_report_from_dict_with_channel() -> None:
    """Test RadonReport.from_dict with channel."""
    data = {"roi_id": 1, "channel": 2, "path": "/a/b/file.tif"}
    r = RadonReport.from_dict(data)
    assert r.roi_id == 1
    assert r.channel == 2


def test_radon_report_from_dict_without_channel() -> None:
    """Test RadonReport.from_dict without channel (backward compatibility)."""
    data = {"roi_id": 1, "path": "/a.tif"}
    r = RadonReport.from_dict(data)
    assert r.roi_id == 1
    assert r.channel is None


def test_radon_report_vel_cv_field() -> None:
    """Test that RadonReport has vel_cv field (coefficient of variation)."""
    r = RadonReport(roi_id=1, vel_mean=1.0, vel_std=0.2, vel_cv=0.2)
    assert r.vel_cv == 0.2
    d = r.to_dict()
    assert "vel_cv" in d
    assert d["vel_cv"] == 0.2


def test_radon_report_from_dict_with_vel_cv() -> None:
    """Test RadonReport.from_dict with vel_cv."""
    data = {"roi_id": 1, "vel_mean": 2.0, "vel_std": 0.5, "vel_cv": 0.25}
    r = RadonReport.from_dict(data)
    assert r.vel_cv == 0.25


def test_radon_report_to_dict_roundtrip() -> None:
    """Test to_dict -> from_dict roundtrip."""
    r = RadonReport(
        roi_id=2,
        channel=1,
        vel_min=0.1,
        vel_max=2.0,
        vel_mean=1.0,
        vel_cv=0.3,
        path="/x/y/z.tif",
        rel_path="y/z.tif",
        parent_folder="y",
        grandparent_folder="x",
    )
    d = r.to_dict()
    r2 = RadonReport.from_dict(d)
    assert r2.roi_id == r.roi_id
    assert r2.channel == r.channel
    assert r2.vel_mean == r.vel_mean
    assert r2.vel_cv == r.vel_cv
    assert r2.path == r.path
    assert r2.rel_path == r.rel_path
    assert r2.parent_folder == r.parent_folder
    assert r2.grandparent_folder == r.grandparent_folder
