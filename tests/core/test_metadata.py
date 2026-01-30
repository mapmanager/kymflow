"""Tests for metadata loading, saving, and field handling."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from kymflow.core.image_loaders.acq_image import AcqImage
from kymflow.core.image_loaders.metadata import AcqImgHeader, ExperimentMetadata


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


def test_update_header_method() -> None:
    """Test that AcqImage.update_header() method works correctly."""
    # Create a mock AcqImage with a header
    # AcqImage requires either path or img_data, so provide dummy image data
    dummy_img = np.zeros((10, 10), dtype=np.uint8)
    acq_image = AcqImage(path=None, img_data=dummy_img)
    acq_image._header = AcqImgHeader()
    acq_image._header.voxels = [1.0, 2.0]
    acq_image._header.voxels_units = ["um", "um"]

    # Update header fields
    acq_image.update_header(voxels=[1.5, 2.5], voxels_units=["px", "px"])

    assert acq_image._header.voxels == [1.5, 2.5]
    assert acq_image._header.voxels_units == ["px", "px"]

    # Test with unknown field (should log warning but not crash)
    acq_image.update_header(unknown_field="value")
    # Should not have set unknown field
    assert not hasattr(acq_image._header, "unknown_field")


def test_experiment_metadata_get_editable_values() -> None:
    """Test ExperimentMetadata.get_editable_values() method."""
    meta = ExperimentMetadata(
        species="mouse",
        region="cortex",
        depth=100.5,
        note="Test note",
    )
    
    editable_values = meta.get_editable_values()
    
    # Should include editable fields
    assert "species" in editable_values
    assert editable_values["species"] == "mouse"
    assert "region" in editable_values
    assert editable_values["region"] == "cortex"
    assert "note" in editable_values
    assert editable_values["note"] == "Test note"
    
    # Should include depth (editable)
    assert "depth" in editable_values
    assert editable_values["depth"] == "100.5"  # Converted to string
    
    # Should NOT include non-editable fields (acquisition_date, acquisition_time)
    assert "acquisition_date" not in editable_values
    assert "acquisition_time" not in editable_values
    
    # Test with None values (should be empty strings)
    meta2 = ExperimentMetadata()
    editable_values2 = meta2.get_editable_values()
    assert editable_values2["species"] == ""
    assert editable_values2["depth"] == ""  # None -> empty string


def test_acq_img_header_properties() -> None:
    """Test AcqImgHeader properties and initialization."""
    # Test default initialization
    header = AcqImgHeader()
    assert header.shape is None
    assert header.ndim is None
    assert header.voxels is None
    assert header.voxels_units is None
    assert header.labels is None
    assert header.physical_size is None
    
    # Test setting properties
    header.shape = (100, 200)
    header.ndim = 2
    header.voxels = [0.001, 0.284]
    header.voxels_units = ["s", "um"]
    header.labels = ["time (s)", "space (um)"]
    header.physical_size = [0.1, 56.8]
    
    assert header.shape == (100, 200)
    assert header.ndim == 2
    assert header.voxels == [0.001, 0.284]
    assert header.voxels_units == ["s", "um"]
    assert header.labels == ["time (s)", "space (um)"]
    assert header.physical_size == [0.1, 56.8]
    
    # Test 3D header
    header_3d = AcqImgHeader()
    header_3d.shape = (50, 100, 200)
    header_3d.ndim = 3
    assert header_3d.shape == (50, 100, 200)
    assert header_3d.ndim == 3

