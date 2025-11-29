"""Tests for metadata loading, saving, and field handling."""

from __future__ import annotations

from pathlib import Path

import pytest

from kymflow_core.kym_file import ExperimentMetadata, OlympusHeader


def test_experiment_metadata_from_dict() -> None:
    """Test creating ExperimentMetadata from dictionary."""
    payload = {
        "species": "mouse",
        "region": "cortex",
        "cell_type": "neuron",
        "depth": 100.5,
        "branch_order": 2,
        "direction": "anterograde",
        "sex": "M",
        "genotype": "WT",
        "condition": "control",
        "note": "Test sample",
    }
    meta = ExperimentMetadata.from_dict(payload)
    assert meta.species == "mouse"
    assert meta.region == "cortex"
    assert meta.depth == 100.5
    assert meta.branch_order == 2
    assert meta.direction == "anterograde"


def test_experiment_metadata_unknown_fields_ignored() -> None:
    """Test that unknown fields are ignored when loading from dict."""
    payload = {
        "species": "mouse",
        "unknown_field": "should be ignored",
    }
    meta = ExperimentMetadata.from_dict(payload)
    assert meta.species == "mouse"
    # Unknown field should not cause error


def test_experiment_metadata_to_dict() -> None:
    """Test converting ExperimentMetadata to dictionary."""
    meta = ExperimentMetadata(
        species="mouse",
        region="cortex",
        note="Test",
    )
    d = meta.to_dict()
    assert d["species"] == "mouse"
    assert d["region"] == "cortex"
    assert d["note"] == "Test"
    # Check abbreviated keys
    assert "acq_date" in d
    assert "acq_time" in d


def test_olympus_header_from_tif_missing_file() -> None:
    """Test OlympusHeader when .txt file is missing."""
    # Use a non-existent file path
    fake_path = Path("/nonexistent/path/file.tif")
    header = OlympusHeader.from_tif(fake_path)
    # Should return header with default values
    assert header.um_per_pixel == 1.0
    assert header.seconds_per_line == 0.001


@pytest.mark.skipif(
    not (Path(__file__).parent / "data").exists(),
    reason="Test data directory not found",
)
def test_olympus_header_from_tif_with_file(sample_tif_file: Path | None) -> None:
    """Test OlympusHeader loading from existing .txt file."""
    if sample_tif_file is None:
        pytest.skip("No test data files available")
    
    # Check if corresponding .txt file exists
    txt_file = sample_tif_file.with_suffix(".txt")
    if not txt_file.exists():
        pytest.skip(f"No header file found: {txt_file}")
    
    header = OlympusHeader.from_tif(sample_tif_file)
    # Should have parsed values (exact values depend on test data)
    assert header is not None

