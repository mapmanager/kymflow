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


def test_field_metadata_class() -> None:
    """Test FieldMetadata class."""
    from kymflow.core.image_loaders.metadata import FieldMetadata
    
    # Create FieldMetadata instance
    meta = FieldMetadata(
        editable=True,
        label="Test Label",
        widget_type="number",
        grid_span=2,
        visible=True,
        description="Test description"
    )
    
    assert meta.editable is True
    assert meta.label == "Test Label"
    assert meta.widget_type == "number"
    assert meta.grid_span == 2
    assert meta.visible is True
    assert meta.description == "Test description"
    
    # Test to_dict()
    meta_dict = meta.to_dict()
    assert meta_dict["editable"] is True
    assert meta_dict["label"] == "Test Label"
    assert meta_dict["widget_type"] == "number"
    assert meta_dict["grid_span"] == 2
    assert meta_dict["visible"] is True
    assert meta_dict["description"] == "Test description"


def test_field_metadata_function() -> None:
    """Test field_metadata() convenience function."""
    from kymflow.core.image_loaders.metadata import field_metadata
    
    # Create metadata dict
    meta_dict = field_metadata(
        editable=False,
        label="Read-only Field",
        widget_type="text",
        grid_span=1,
        visible=True,
        description="This field cannot be edited"
    )
    
    assert isinstance(meta_dict, dict)
    assert meta_dict["editable"] is False
    assert meta_dict["label"] == "Read-only Field"
    assert meta_dict["widget_type"] == "text"
    assert meta_dict["grid_span"] == 1
    assert meta_dict["visible"] is True
    assert meta_dict["description"] == "This field cannot be edited"


def test_acq_img_header_validate_ndim() -> None:
    """Test AcqImgHeader.validate_ndim() method."""
    header = AcqImgHeader()
    
    # Test valid ndim
    header.shape = (100, 200)
    header.ndim = 2
    assert header.validate_ndim(2) is True
    
    # Test invalid ndim
    assert header.validate_ndim(4) is False  # Must be 2 or 3
    
    # Test consistency check
    header.shape = (100, 200)
    header.ndim = 2
    assert header.validate_ndim(3) is False  # Doesn't match existing shape
    
    # Test with voxels consistency
    header.voxels = [0.001, 0.284]
    assert header.validate_ndim(2) is True
    assert header.validate_ndim(3) is False  # voxels length doesn't match


def test_acq_img_header_validate_shape() -> None:
    """Test AcqImgHeader.validate_shape() method."""
    header = AcqImgHeader()
    
    # Test valid 2D shape
    header.ndim = 2
    assert header.validate_shape((100, 200)) is True
    
    # Test valid 3D shape
    header.ndim = 3
    assert header.validate_shape((10, 100, 200)) is True
    
    # Test invalid shape (wrong dimensions)
    assert header.validate_shape((100,)) is False  # Must be 2 or 3
    assert header.validate_shape((10, 100, 200, 50)) is False  # Must be 2 or 3
    
    # Test consistency with ndim
    header.ndim = 2
    assert header.validate_shape((10, 100, 200)) is False  # Doesn't match ndim
    
    # Test consistency with voxels
    header.voxels = [0.001, 0.284]
    assert header.validate_shape((100, 200)) is True
    assert header.validate_shape((10, 100, 200)) is False  # voxels length doesn't match


def test_acq_img_header_compute_physical_size() -> None:
    """Test AcqImgHeader.compute_physical_size() method."""
    header = AcqImgHeader()
    
    # Test with shape and voxels
    header.shape = (100, 200)
    header.voxels = [0.001, 0.284]
    physical_size = header.compute_physical_size()
    assert physical_size is not None
    assert len(physical_size) == 2
    assert physical_size[0] == pytest.approx(100 * 0.001)
    assert physical_size[1] == pytest.approx(200 * 0.284)
    
    # Test with None shape
    header.shape = None
    assert header.compute_physical_size() is None
    
    # Test with None voxels
    header.shape = (100, 200)
    header.voxels = None
    assert header.compute_physical_size() is None
    
    # Test with mismatched lengths
    header.shape = (100, 200)
    header.voxels = [0.001]  # Only one element
    assert header.compute_physical_size() is None


def test_acq_img_header_set_shape_ndim() -> None:
    """Test AcqImgHeader.set_shape_ndim() method."""
    header = AcqImgHeader()
    
    # Set shape and ndim
    header.set_shape_ndim((100, 200), 2)
    assert header.shape == (100, 200)
    assert header.ndim == 2
    
    # Set shape only (ndim inferred)
    header2 = AcqImgHeader()
    header2.set_shape_ndim((10, 100, 200), None)
    assert header2.shape == (10, 100, 200)
    assert header2.ndim == 3  # Inferred from shape length
    
    # Test validation (should raise if inconsistent)
    header3 = AcqImgHeader()
    header3.voxels = [0.001, 0.284]  # 2 elements
    # Setting 3D shape with 2D voxels should fail validation
    with pytest.raises(ValueError, match="voxels length"):
        header3.set_shape_ndim((10, 100, 200), 3)


def test_acq_img_header_init_defaults_from_shape() -> None:
    """Test AcqImgHeader.init_defaults_from_shape() method."""
    header = AcqImgHeader()
    
    # Set ndim and shape
    header.ndim = 2
    header.shape = (100, 200)
    header.init_defaults_from_shape()
    
    # Should initialize defaults
    assert header.voxels == [1.0, 1.0]
    assert header.voxels_units == ["px", "px"]
    assert header.labels == ["", ""]
    assert header.physical_size is not None
    
    # Test with 3D
    header2 = AcqImgHeader()
    header2.ndim = 3
    header2.shape = (10, 100, 200)
    header2.init_defaults_from_shape()
    
    assert len(header2.voxels) == 3
    assert len(header2.voxels_units) == 3
    assert len(header2.labels) == 3
    assert header2.physical_size is not None
    assert len(header2.physical_size) == 3
    
    # Test with None ndim (should do nothing)
    header3 = AcqImgHeader()
    header3.init_defaults_from_shape()
    assert header3.voxels is None
    assert header3.voxels_units is None


def test_acq_img_header_to_dict() -> None:
    """Test AcqImgHeader.to_dict() method."""
    header = AcqImgHeader()
    header.shape = (100, 200)
    header.ndim = 2
    header.voxels = [0.001, 0.284]
    header.voxels_units = ["s", "um"]
    header.labels = ["time (s)", "space (um)"]
    header.physical_size = [0.1, 56.8]
    
    header_dict = header.to_dict()
    
    assert header_dict["shape"] == [100, 200]  # Converted to list
    assert header_dict["ndim"] == 2
    assert header_dict["voxels"] == [0.001, 0.284]
    assert header_dict["voxels_units"] == ["s", "um"]
    assert header_dict["labels"] == ["time (s)", "space (um)"]
    assert header_dict["physical_size"] == [0.1, 56.8]
    
    # Test with None values
    header2 = AcqImgHeader()
    header2_dict = header2.to_dict()
    assert header2_dict["shape"] is None
    assert header2_dict["ndim"] is None


def test_acq_img_header_from_dict() -> None:
    """Test AcqImgHeader.from_dict() method."""
    data = {
        "shape": [100, 200],
        "ndim": 2,
        "voxels": [0.001, 0.284],
        "voxels_units": ["s", "um"],
        "labels": ["time (s)", "space (um)"],
        "physical_size": [0.1, 56.8],
    }
    
    header = AcqImgHeader.from_dict(data)
    
    assert header.shape == (100, 200)  # Converted to tuple
    assert header.ndim == 2
    assert header.voxels == [0.001, 0.284]
    assert header.voxels_units == ["s", "um"]
    assert header.labels == ["time (s)", "space (um)"]
    assert header.physical_size == [0.1, 56.8]
    
    # Test with empty dict
    header2 = AcqImgHeader.from_dict({})
    assert header2.shape is None
    assert header2.ndim is None
    
    # Test with missing physical_size (should compute)
    data3 = {
        "shape": [100, 200],
        "ndim": 2,
        "voxels": [0.001, 0.284],
    }
    header3 = AcqImgHeader.from_dict(data3)
    assert header3.physical_size is not None
    assert header3.physical_size[0] == pytest.approx(0.1)
    assert header3.physical_size[1] == pytest.approx(56.8)


def test_acq_img_header_form_schema() -> None:
    """Test AcqImgHeader.form_schema() method."""
    schema = AcqImgHeader.form_schema()
    
    assert isinstance(schema, list)
    assert len(schema) > 0
    
    # Check that schema contains expected fields
    field_names = [field["name"] for field in schema]
    assert "shape" in field_names
    assert "ndim" in field_names
    assert "voxels" in field_names
    assert "voxels_units" in field_names
    assert "labels" in field_names
    assert "physical_size" in field_names
    
    # Check schema structure
    for field in schema:
        assert "name" in field
        assert "label" in field
        assert "editable" in field
        assert "widget_type" in field
        assert "grid_span" in field
        assert "visible" in field
        assert "field_type" in field


def test_acq_img_header_from_data() -> None:
    """Test AcqImgHeader.from_data() classmethod."""
    header = AcqImgHeader.from_data((100, 200), 2)
    
    assert header.shape == (100, 200)
    assert header.ndim == 2
    assert header.voxels == [1.0, 1.0]
    assert header.voxels_units == ["px", "px"]
    assert header.labels == ["", ""]
    assert header.physical_size is not None
    assert len(header.physical_size) == 2
    
    # Test 3D
    header3d = AcqImgHeader.from_data((10, 100, 200), 3)
    assert header3d.shape == (10, 100, 200)
    assert header3d.ndim == 3
    assert len(header3d.voxels) == 3
    assert len(header3d.voxels_units) == 3
    assert len(header3d.labels) == 3
    assert len(header3d.physical_size) == 3


def test_experiment_metadata_form_schema() -> None:
    """Test ExperimentMetadata.form_schema() method."""
    schema = ExperimentMetadata.form_schema()
    
    assert isinstance(schema, list)
    assert len(schema) > 0
    
    # Check that schema contains expected fields
    field_names = [field["name"] for field in schema]
    assert "species" in field_names
    assert "region" in field_names
    assert "note" in field_names
    assert "acquisition_date" in field_names
    assert "acquisition_time" in field_names
    
    # Check schema structure
    for field in schema:
        assert "name" in field
        assert "label" in field
        assert "editable" in field
        assert "widget_type" in field
        assert "grid_span" in field
        assert "visible" in field
        assert "field_type" in field
    
    # Check that acquisition_date and acquisition_time are not editable
    acq_date_field = next(f for f in schema if f["name"] == "acquisition_date")
    acq_time_field = next(f for f in schema if f["name"] == "acquisition_time")
    assert acq_date_field["editable"] is False
    assert acq_time_field["editable"] is False

