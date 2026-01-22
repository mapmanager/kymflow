# nicewidgets/sample_config_use.py
"""
Sample usage of the reusable TOML config system (named registry API).
"""

from __future__ import annotations

import logging
from pathlib import Path

from nicewidgets.config import (
    list_configs,
    load_named,
    save_named,
    normalize_named,
)

logging.basicConfig(level=logging.INFO)


def main() -> None:
    """Demonstrate loading/saving two different config types."""
    log = logging.getLogger("sample")

    log.info("Registered configs: %s", list_configs())

    tmp_dir = Path("config_demo")
    tmp_dir.mkdir(exist_ok=True)

    roi_path = tmp_dir / "roi_gui.toml"
    img_path = tmp_dir / "image_display.toml"

    # Load ROI GUI config (writes scaffold if missing; autofills missing keys)
    roi_cfg = load_named("roi_gui", path=roi_path).config
    log.info("ROI opacity: %s", roi_cfg.roi.opacity)
    roi_cfg.roi.opacity = 0.4

    # Save, dropping unknown keys (rebuild from scaffold)
    save_named("roi_gui", roi_cfg, path=roi_path, keep_unknown_keys=False)

    # Normalize: remove deprecated keys + optionally drop unknown keys
    normalize_named("roi_gui", path=roi_path, remove_deprecated_keys=True, drop_unknown_keys=True)

    # Load image display config
    img_cfg = load_named("image_display", path=img_path).config
    log.info("Image LUT: %s", img_cfg.color_lut)
    img_cfg.color_lut = "viridis"
    img_cfg.show_toolbar = False

    # Save, dropping unknown keys
    save_named("image_display", img_cfg, path=img_path, keep_unknown_keys=False)

    log.info("Wrote configs into %s", tmp_dir.resolve())
    log.info("Done.")


if __name__ == "__main__":
    main()
