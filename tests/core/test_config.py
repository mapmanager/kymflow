# tests/test_config.py
from __future__ import annotations

from pathlib import Path

import pytest

from kymflow.core.config import (
    list_configs,
    load_named,
    normalize_named,
    save_named,
)


def test_registry_has_expected_configs() -> None:
    names = list_configs()
    assert "roi_gui" in names
    assert "image_display" in names


def test_writes_scaffold_when_missing(tmp_path: Path) -> None:
    roi_path = tmp_path / "roi_gui.toml"
    res = load_named("roi_gui", path=roi_path)
    assert roi_path.exists()
    assert res.wrote_scaffold is True
    assert res.config.version >= 1


def test_autofill_missing_defaults_pattern_b(tmp_path: Path) -> None:
    img_path = tmp_path / "image_display.toml"
    img_path.write_text(
        """\
version = 1
x_axis = true
""",
        encoding="utf-8",
    )

    res = load_named("image_display", path=img_path)
    text = img_path.read_text(encoding="utf-8")

    assert "y_axis" in text
    assert "x_label" in text
    assert "color_lut" in text
    assert res.config.y_axis is True
    assert res.config.color_lut == "gray"


def test_unknown_keys_warn_but_do_not_crash(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    roi_path = tmp_path / "roi_gui.toml"
    roi_path.write_text(
        """\
version = 1
[roi]
line_color = "#00FF00"
line_width = 2.0
opactiy = 0.3  # typo: should warn, not crash
""",
        encoding="utf-8",
    )

    caplog.clear()
    res = load_named("roi_gui", path=roi_path)

    assert res.config.roi.opacity == pytest.approx(0.25)

    warnings = "\n".join([r.message for r in caplog.records])
    assert "Unknown config key ignored" in warnings
    assert "roi.opactiy" in warnings


@pytest.mark.skip(reason="no aliases implemented yet")
def test_aliases_allow_old_key_names(tmp_path: Path) -> None:
    roi_path = tmp_path / "roi_gui.toml"
    roi_path.write_text(
        """\
version = 1
[roi]
stroke_width = 5.0
fill_alpha = 0.6
""",
        encoding="utf-8",
    )

    res = load_named("roi_gui", path=roi_path, autofill_missing_defaults=False)
    assert res.config.roi.line_width == pytest.approx(5.0)
    assert res.config.roi.opacity == pytest.approx(0.6)


@pytest.mark.skip(reason="no aliases implemented yet -> no depreciated keys")
def test_normalize_removes_deprecated_keys(tmp_path: Path) -> None:
    roi_path = tmp_path / "roi_gui.toml"
    roi_path.write_text(
        """\
version = 1
[roi]
stroke_color = "#FF0000"
stroke_width = 3.0
fill_alpha = 0.5
line_color = "#00FF00"
line_width = 2.0
opacity = 0.25
""",
        encoding="utf-8",
    )

    normalize_named("roi_gui", path=roi_path, remove_deprecated_keys=True)
    text = roi_path.read_text(encoding="utf-8")

    assert "stroke_color" not in text
    assert "stroke_width" not in text
    assert "fill_alpha" not in text
    assert "line_color" in text
    assert "line_width" in text
    assert "opacity" in text


def test_save_can_drop_unknown_keys(tmp_path: Path) -> None:
    img_path = tmp_path / "image_display.toml"
    img_path.write_text(
        """\
version = 1
x_axis = true
y_axis = true
color_lut = "gray"
show_toolbar = true

# user custom key not in schema:
custom_note = "keep me"
""",
        encoding="utf-8",
    )

    cfg = load_named("image_display", path=img_path).config
    cfg.color_lut = "viridis"
    cfg.show_toolbar = False

    # Drop unknown keys when saving
    save_named("image_display", cfg, path=img_path, keep_unknown_keys=False)

    text = img_path.read_text(encoding="utf-8")
    assert 'color_lut = "viridis"' in text
    assert "show_toolbar = false" in text
    assert "custom_note" not in text
