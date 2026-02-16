"""Tests for FileTableView."""

from __future__ import annotations

import numpy as np
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock

import pytest
import tifffile

from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.gui_v2.views.file_table_view import FileTableView


@pytest.fixture
def mock_app_context():
    """Create a mock AppContext for testing."""
    mock_context = MagicMock()
    mock_app_config = MagicMock()
    mock_app_config.get_blinded.return_value = False
    mock_context.app_config = mock_app_config
    return mock_context


@pytest.fixture
def sample_kym_files() -> list[KymImage]:
    """Create two sample KymImages for testing."""
    with TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        subdir = tmp_path / "a" / "b"
        subdir.mkdir(parents=True)
        f1 = subdir / "test1.tif"
        f2 = subdir / "test2.tif"
        img = np.zeros((100, 200), dtype=np.uint16)
        tifffile.imwrite(f1, img)
        tifffile.imwrite(f2, img)

        k1 = KymImage(f1, load_image=True)
        k2 = KymImage(f2, load_image=True)
        return [k1, k2]


def test_file_table_view_get_table_as_text_empty(mock_app_context) -> None:
    """Test get_table_as_text() with empty table returns empty string."""
    view = FileTableView(
        mock_app_context,
        on_selected=lambda x: None,
        selection_mode="single",
    )
    result = view.get_table_as_text()
    assert result == ""


def test_file_table_view_get_table_as_text_with_data(
    mock_app_context, sample_kym_files: list[KymImage]
) -> None:
    """Test get_table_as_text() formats data as TSV with all columns."""
    view = FileTableView(
        mock_app_context,
        on_selected=lambda x: None,
        selection_mode="single",
    )
    view.set_files(sample_kym_files)

    result = view.get_table_as_text()

    assert result != ""
    lines = result.split("\n")
    assert len(lines) >= 2  # header + at least one data row

    header_line = lines[0]
    assert "File Name" in header_line
    assert "User Event" in header_line
    assert "Events" in header_line  # short header for Total Num Velocity Events column

    assert "\t" in header_line

    header_cols = len(header_line.split("\t"))
    for line in lines[1:]:
        if line.strip():
            assert len(line.split("\t")) == header_cols
