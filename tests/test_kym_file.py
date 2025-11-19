"""
Integration-style tests for KymFile built around a known TIFF + Olympus header.

These tests use a path supplied by the project owner. They are skipped when the
data folder is unavailable (e.g., CI machines) so developers can still run the
suite without the proprietary dataset.
"""

from __future__ import annotations

import unittest
from pathlib import Path

import numpy as np

from kymflow_core.kym_file import (
    BiologyMetadata,
    KymFile,
    collect_metadata,
    iter_metadata,
)
from kymflow_core.utils.logging import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)
TEST_TIF = Path("/Users/cudmore/Dropbox/data/declan/data/20221102/Capillary1_0001.tif")


class BiologyMetadataTests(unittest.TestCase):
    def test_extra_fields_preserved(self) -> None:
        payload = {
            "species": "mouse",
            "region": "cortex",
            "favorite_color": "blue",
            "note": "Important sample",
        }
        meta = BiologyMetadata.from_dict(payload)
        self.assertEqual(meta.species, "mouse")
        self.assertEqual(meta.region, "cortex")
        self.assertEqual(meta.extra["favorite_color"], "blue")
        # Round trip should retain both known and unknown keys.
        merged = meta.to_dict()
        self.assertEqual(merged["species"], "mouse")
        self.assertEqual(merged["favorite_color"], "blue")


@unittest.skipUnless(TEST_TIF.exists(), f"Missing test data: {TEST_TIF}")
class RealFileTests(unittest.TestCase):
    def setUp(self) -> None:
        logger.info("Setting up KymFile for %s", TEST_TIF)
        self.kym = KymFile(TEST_TIF, load_image=False)

    def test_metadata_only_load(self) -> None:
        logger.info("Loading metadata for %s", TEST_TIF.name)
        metadata = self.kym.to_metadata_dict(include_analysis=False)
        self.assertEqual(metadata["filename"], TEST_TIF.name)
        # Olympus header keys should exist even if not populated.
        self.assertIn("um_per_pixel", metadata)
        self.assertIn("seconds_per_line", metadata)

    def test_lazy_image_loading(self) -> None:
        # Image should not be loaded until explicitly requested.
        self.assertIsNone(self.kym._image)  # type: ignore[attr-defined]
        image = self.kym.ensure_image_loaded()
        self.assertIsInstance(image, np.ndarray)
        self.assertGreaterEqual(image.ndim, 2)
        logger.info("Image shape loaded: %s", image.shape)

    def test_iter_and_collect_metadata(self) -> None:
        parent = TEST_TIF.parent
        logger.info("Iterating metadata under %s", parent)
        entries = list(iter_metadata(parent, glob=TEST_TIF.name))
        self.assertTrue(
            any(entry["path"] == str(TEST_TIF) for entry in entries),
            "iter_metadata should return the known TIFF",
        )
        collected = collect_metadata(parent, glob=TEST_TIF.name)
        self.assertEqual(len(entries), len(collected))
