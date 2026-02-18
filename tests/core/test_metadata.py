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
        "condition2": "stim",
        "treatment": "drug",
        "treatment2": "vehicle",
        "date": "2025-02-17",
        "note": "Test sample",
    }
    meta = ExperimentMetadata.from_dict(payload)
    assert meta.species == "mouse"
    assert meta.region == "cortex"
    assert meta.depth == 100.5
    assert meta.branch_order == 2
    assert meta.direction == "anterograde"
    assert meta.condition == "control"
    assert meta.condition2 == "stim"
    assert meta.treatment == "drug"
    assert meta.treatment2 == "vehicle"
    assert meta.date == "2025-02-17"


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
        condition2="stim",
        treatment="drug",
        date="2025-02-17",
        note="Test",
    )
    d = meta.to_dict()
    assert d["species"] == "mouse"
    assert d["region"] == "cortex"
    assert d["condition2"] == "stim"
    assert d["treatment"] == "drug"
    assert d["date"] == "2025-02-17"
    assert d["note"] == "Test"


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
    assert header.date_str is None
    assert header.time_str is None
    
    # Test setting properties
    header.shape = (100, 200)
    header.ndim = 2
    header.voxels = [0.001, 0.284]
    header.voxels_units = ["s", "um"]
    header.labels = ["time (s)", "space (um)"]
    header.physical_size = [0.1, 56.8]
    header.date_str = "11/02/2022"
    header.time_str = "12:54:17"
    
    assert header.shape == (100, 200)
    assert header.ndim == 2
    assert header.voxels == [0.001, 0.284]
    assert header.voxels_units == ["s", "um"]
    assert header.labels == ["time (s)", "space (um)"]
    assert header.physical_size == [0.1, 56.8]
    assert header.date_str == "11/02/2022"
    assert header.time_str == "12:54:17"
    
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
    header.date_str = "11/02/2022"
    header.time_str = "12:54:17"
    
    header_dict = header.to_dict()
    
    assert header_dict["shape"] == [100, 200]  # Converted to list
    assert header_dict["ndim"] == 2
    assert header_dict["voxels"] == [0.001, 0.284]
    assert header_dict["voxels_units"] == ["s", "um"]
    assert header_dict["labels"] == ["time (s)", "space (um)"]
    assert header_dict["physical_size"] == [0.1, 56.8]
    assert header_dict["date_str"] == "11/02/2022"
    assert header_dict["time_str"] == "12:54:17"
    
    # Test with None values (date_str/time_str should not be included)
    header2 = AcqImgHeader()
    header2_dict = header2.to_dict()
    assert header2_dict["shape"] is None
    assert header2_dict["ndim"] is None
    assert "date_str" not in header2_dict  # Should not be included when None
    assert "time_str" not in header2_dict  # Should not be included when None
    
    # Test with only date_str set
    header3 = AcqImgHeader()
    header3.date_str = "11/02/2022"
    header3_dict = header3.to_dict()
    assert header3_dict["date_str"] == "11/02/2022"
    assert "time_str" not in header3_dict  # Should not be included when None


def test_acq_img_header_from_dict() -> None:
    """Test AcqImgHeader.from_dict() method."""
    data = {
        "shape": [100, 200],
        "ndim": 2,
        "voxels": [0.001, 0.284],
        "voxels_units": ["s", "um"],
        "labels": ["time (s)", "space (um)"],
        "physical_size": [0.1, 56.8],
        "date_str": "11/02/2022",
        "time_str": "12:54:17",
    }
    
    header = AcqImgHeader.from_dict(data)
    
    assert header.shape == (100, 200)  # Converted to tuple
    assert header.ndim == 2
    assert header.voxels == [0.001, 0.284]
    assert header.voxels_units == ["s", "um"]
    assert header.labels == ["time (s)", "space (um)"]
    assert header.physical_size == [0.1, 56.8]
    assert header.date_str == "11/02/2022"
    assert header.time_str == "12:54:17"
    
    # Test with empty dict
    header2 = AcqImgHeader.from_dict({})
    assert header2.shape is None
    assert header2.ndim is None
    assert header2.date_str is None
    assert header2.time_str is None
    
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
    
    # Test with only date_str (time_str missing)
    data4 = {
        "shape": [100, 200],
        "ndim": 2,
        "date_str": "11/02/2022",
    }
    header4 = AcqImgHeader.from_dict(data4)
    assert header4.date_str == "11/02/2022"
    assert header4.time_str is None


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
    assert "date_str" in field_names
    assert "time_str" in field_names
    
    # Check schema structure
    for field in schema:
        assert "name" in field
        assert "label" in field
        assert "editable" in field
        assert "widget_type" in field
        assert "grid_span" in field
        assert "visible" in field
        assert "field_type" in field
    
    # Check that date_str and time_str are read-only
    date_str_field = next(f for f in schema if f["name"] == "date_str")
    time_str_field = next(f for f in schema if f["name"] == "time_str")
    assert date_str_field["editable"] is False
    assert time_str_field["editable"] is False


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
    assert "condition" in field_names
    assert "condition2" in field_names
    assert "treatment" in field_names
    assert "treatment2" in field_names
    assert "date" in field_names
    assert "note" in field_names
    
    # Check schema structure
    for field in schema:
        assert "name" in field
        assert "label" in field
        assert "editable" in field
        assert "widget_type" in field
        assert "grid_span" in field
        assert "visible" in field
        assert "field_type" in field


def test_experiment_metadata_backward_compatibility_old_keys() -> None:
    """Test that ExperimentMetadata.from_dict() ignores old acq_date/acq_time keys.
    
    This ensures backward compatibility with old JSON files that may contain
    acq_date/acq_time keys from the previous to_dict() implementation.
    """
    # Old JSON format with acq_date/acq_time (should be ignored)
    payload = {
        "species": "mouse",
        "condition": "control",
        "acq_date": "11/02/2022",  # Old key name
        "acq_time": "12:54:17",    # Old key name
    }
    
    meta = ExperimentMetadata.from_dict(payload)
    
    # Should load valid fields
    assert meta.species == "mouse"
    assert meta.condition == "control"
    
    # Old keys should be ignored (fields no longer exist)
    # This is expected behavior - from_dict() only loads fields that exist in the dataclass


def test_acq_img_header_serialization_round_trip() -> None:
    """Test that AcqImgHeader serialization round-trips correctly with date_str/time_str."""
    header = AcqImgHeader()
    header.shape = (100, 200)
    header.ndim = 2
    header.voxels = [0.001, 0.284]
    header.voxels_units = ["s", "um"]
    header.labels = ["time (s)", "space (um)"]
    header.physical_size = [0.1, 56.8]
    header.date_str = "11/02/2022"
    header.time_str = "12:54:17"
    
    # Serialize and deserialize
    header_dict = header.to_dict()
    header_restored = AcqImgHeader.from_dict(header_dict)
    
    # Verify all fields round-trip correctly
    assert header_restored.shape == header.shape
    assert header_restored.ndim == header.ndim
    assert header_restored.voxels == header.voxels
    assert header_restored.voxels_units == header.voxels_units
    assert header_restored.labels == header.labels
    assert header_restored.physical_size == header.physical_size
    assert header_restored.date_str == header.date_str
    assert header_restored.time_str == header.time_str


def test_acq_img_header_serialization_without_date_time() -> None:
    """Test that AcqImgHeader serialization works when date_str/time_str are None."""
    header = AcqImgHeader()
    header.shape = (100, 200)
    header.ndim = 2
    header.voxels = [0.001, 0.284]
    
    # Serialize (date_str/time_str are None, should not appear in dict)
    header_dict = header.to_dict()
    
    assert "shape" in header_dict
    assert "ndim" in header_dict
    assert "voxels" in header_dict
    assert "date_str" not in header_dict  # Should not be included when None
    assert "time_str" not in header_dict  # Should not be included when None
    
    # Deserialize should work fine
    header_restored = AcqImgHeader.from_dict(header_dict)
    assert header_restored.shape == header.shape
    assert header_restored.date_str is None
    assert header_restored.time_str is None

