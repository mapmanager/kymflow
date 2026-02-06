"""Unit tests for ROI functionality in AcqImage and RoiSet.

Tests ROI CRUD operations, channel/z filtering, bounds validation,
and metadata save/load functionality.
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pytest

from kymflow.core.image_loaders.acq_image import AcqImage
from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.core.image_loaders.roi import ROI, RoiSet, RoiBounds, ImageBounds, ImageSize
from kymflow.core.utils.logging import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)


def test_roi_with_channel_and_z() -> None:
    """Test ROI class with channel and z attributes."""
    logger.info("Testing ROI with channel and z attributes")
    
    # Create ROI with channel and z
    bounds = RoiBounds(dim0_start=20, dim0_stop=80, dim1_start=10, dim1_stop=50)
    roi = ROI(id=1, channel=2, z=5, bounds=bounds)
    
    assert roi.id == 1
    assert roi.channel == 2
    assert roi.z == 5
    assert roi.bounds.dim0_start == 20
    assert roi.bounds.dim0_stop == 80
    assert roi.bounds.dim1_start == 10
    assert roi.bounds.dim1_stop == 50
    
    # Test defaults
    bounds2 = RoiBounds(dim0_start=20, dim0_stop=80, dim1_start=10, dim1_stop=50)
    roi2 = ROI(id=2, bounds=bounds2)
    assert roi2.channel == 1  # Default
    assert roi2.z == 0  # Default
    
    logger.info("  - ROI channel and z attributes work correctly")


def test_roi_to_dict_from_dict() -> None:
    """Test ROI serialization with channel and z."""
    logger.info("Testing ROI to_dict/from_dict with channel and z")
    
    bounds = RoiBounds(dim0_start=20, dim0_stop=80, dim1_start=10, dim1_stop=50)
    roi = ROI(id=1, channel=2, z=5, bounds=bounds, name="test", note="note")
    
    # Serialize
    roi_dict = roi.to_dict()
    assert roi_dict["id"] == 1
    assert roi_dict["channel"] == 2
    assert roi_dict["z"] == 5
    assert roi_dict["dim1_start"] == 10
    
    # Deserialize
    roi2 = ROI.from_dict(roi_dict)
    assert roi2.id == 1
    assert roi2.channel == 2
    assert roi2.z == 5
    assert roi2.bounds.dim1_start == 10
    
    # Test defaults (missing channel/z)
    roi_dict_minimal = {"id": 1, "dim0_start": 20, "dim0_stop": 80, "dim1_start": 10, "dim1_stop": 50}
    roi3 = ROI.from_dict(roi_dict_minimal)
    assert roi3.channel == 1  # Default
    assert roi3.z == 0  # Default
    
    logger.info("  - ROI serialization works correctly")


def test_roiset_create_roi() -> None:
    """Test RoiSet.create_roi() with bounds validation."""
    logger.info("Testing RoiSet.create_roi()")
    
    # Create 2D test image
    test_image = np.zeros((100, 200), dtype=np.uint8)
    acq_image = AcqImage(path=None, img_data=test_image)
    
    # Create ROI
    bounds = RoiBounds(dim0_start=20, dim0_stop=80, dim1_start=10, dim1_stop=50)
    roi = acq_image.rois.create_roi(bounds=bounds, channel=1, z=0)
    
    assert roi.id == 1
    assert roi.channel == 1
    assert roi.z == 0
    assert roi.bounds.dim0_start == 20
    assert roi.bounds.dim0_stop == 80
    assert roi.bounds.dim1_start == 10
    assert roi.bounds.dim1_stop == 50
    
    # Test that coordinates are clamped
    bounds2 = RoiBounds(dim0_start=-5, dim0_stop=150, dim1_start=-10, dim1_stop=250)
    roi2 = acq_image.rois.create_roi(bounds=bounds2, channel=1)
    assert roi2.bounds.dim0_start >= 0
    assert roi2.bounds.dim0_stop <= 100
    assert roi2.bounds.dim1_start >= 0
    assert roi2.bounds.dim1_stop <= 200
    
    logger.info("  - RoiSet.create_roi() works correctly with bounds validation")


def test_roiset_create_roi_3d() -> None:
    """Test RoiSet.create_roi() with 3D image."""
    logger.info("Testing RoiSet.create_roi() with 3D image")
    
    # Create 3D test image (10 slices, 100 lines, 200 pixels)
    test_image = np.zeros((10, 100, 200), dtype=np.uint8)
    acq_image = AcqImage(path=None, img_data=test_image)
    
    # Create ROI on slice 5
    bounds = RoiBounds(dim0_start=20, dim0_stop=80, dim1_start=10, dim1_stop=50)
    roi = acq_image.rois.create_roi(bounds=bounds, channel=1, z=5)
    
    assert roi.z == 5
    
    # Test z clamping (z too high)
    roi2 = acq_image.rois.create_roi(bounds=bounds, channel=1, z=15)
    assert roi2.z == 9  # Clamped to num_slices-1
    
    # Test z clamping (z negative)
    roi3 = acq_image.rois.create_roi(bounds=bounds, channel=1, z=-1)
    assert roi3.z == 0  # Clamped to 0
    
    logger.info("  - RoiSet.create_roi() works correctly with 3D images")


def test_roiset_create_roi_2d_z_validation() -> None:
    """Test that z=0 is enforced for 2D images."""
    logger.info("Testing RoiSet.create_roi() z validation for 2D images")
    
    test_image = np.zeros((100, 200), dtype=np.uint8)
    acq_image = AcqImage(path=None, img_data=test_image)
    
    # Try to create ROI with z != 0 (should be clamped to 0)
    bounds = RoiBounds(dim0_start=20, dim0_stop=80, dim1_start=10, dim1_stop=50)
    roi = acq_image.rois.create_roi(bounds=bounds, channel=1, z=5)
    assert roi.z == 0  # Clamped to 0 for 2D
    
    logger.info("  - z coordinate correctly clamped to 0 for 2D images")


def test_roiset_edit_roi() -> None:
    """Test RoiSet.edit_roi() with bounds validation."""
    logger.info("Testing RoiSet.edit_roi()")
    
    test_image = np.zeros((100, 200), dtype=np.uint8)
    acq_image = AcqImage(path=None, img_data=test_image)
    
    # Create ROI
    bounds = RoiBounds(dim0_start=20, dim0_stop=80, dim1_start=10, dim1_stop=50)
    roi = acq_image.rois.create_roi(bounds=bounds, channel=1)
    
    # Edit coordinates
    new_bounds = RoiBounds(dim0_start=25, dim0_stop=80, dim1_start=15, dim1_stop=50)
    acq_image.rois.edit_roi(roi.id, bounds=new_bounds)
    assert roi.bounds.dim0_start == 25
    assert roi.bounds.dim1_start == 15
    
    # Edit with out-of-bounds coordinates (should be clamped)
    out_of_bounds = RoiBounds(dim0_start=20, dim0_stop=150, dim1_start=10, dim1_stop=250)
    acq_image.rois.edit_roi(roi.id, bounds=out_of_bounds)
    assert roi.bounds.dim0_stop <= 100
    assert roi.bounds.dim1_stop <= 200
    
    # Edit channel
    acq_image.rois.edit_roi(roi.id, channel=1)  # Same channel, should work
    
    # Edit name and note
    acq_image.rois.edit_roi(roi.id, name="updated", note="updated note")
    assert roi.name == "updated"
    assert roi.note == "updated note"
    
    logger.info("  - RoiSet.edit_roi() works correctly")


def test_roiset_delete_get() -> None:
    """Test RoiSet.delete() and get() methods."""
    logger.info("Testing RoiSet.delete() and get()")
    
    test_image = np.zeros((100, 200), dtype=np.uint8)
    acq_image = AcqImage(path=None, img_data=test_image)
    
    # Create multiple ROIs
    bounds1 = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
    roi1 = acq_image.rois.create_roi(bounds=bounds1, channel=1)
    bounds2 = RoiBounds(dim0_start=60, dim0_stop=90, dim1_start=60, dim1_stop=90)
    roi2 = acq_image.rois.create_roi(bounds=bounds2, channel=1)
    
    assert acq_image.rois.numRois() == 2
    
    # Get ROI
    retrieved = acq_image.rois.get(roi1.id)
    assert retrieved == roi1
    
    # Delete ROI
    acq_image.rois.delete(roi1.id)
    assert acq_image.rois.numRois() == 1
    assert acq_image.rois.get(roi1.id) is None
    assert acq_image.rois.get(roi2.id) is not None
    
    logger.info("  - RoiSet.delete() and get() work correctly")


def test_roiset_revalidate_all() -> None:
    """Test RoiSet.revalidate_all() utility method."""
    logger.info("Testing RoiSet.revalidate_all()")
    
    test_image = np.zeros((100, 200), dtype=np.uint8)
    acq_image = AcqImage(path=None, img_data=test_image)
    
    # Create ROIs (should be valid)
    bounds1 = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
    roi1 = acq_image.rois.create_roi(bounds=bounds1, channel=1)
    bounds2 = RoiBounds(dim0_start=60, dim0_stop=90, dim1_start=60, dim1_stop=90)
    roi2 = acq_image.rois.create_roi(bounds=bounds2, channel=1)
    
    # Manually set invalid coordinates (simulating corrupted data)
    roi1.bounds.dim1_start = -10
    roi1.bounds.dim1_stop = 250
    
    # Revalidate
    clamped_count = acq_image.rois.revalidate_all()
    assert clamped_count > 0
    assert roi1.bounds.dim1_start >= 0
    assert roi1.bounds.dim1_stop <= 200
    
    logger.info("  - RoiSet.revalidate_all() works correctly")


def test_roiset_invalid_channel() -> None:
    """Test that creating ROI with invalid channel raises error."""
    logger.info("Testing RoiSet with invalid channel")
    
    test_image = np.zeros((100, 200), dtype=np.uint8)
    acq_image = AcqImage(path=None, img_data=test_image)
    
    # Try to create ROI with non-existent channel
    bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
    with pytest.raises(ValueError, match="Channel.*does not exist"):
        acq_image.rois.create_roi(bounds=bounds, channel=99)
    
    logger.info("  - Invalid channel correctly raises ValueError")


def test_roiset_no_bounds() -> None:
    """Test that creating ROI without bounds raises error."""
    logger.info("Testing RoiSet without image bounds")
    
    # Create AcqImage without data or header (path only, no loading)
    # This should have shape=None
    with TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.tif"
        test_file.touch()
        
        acq_image = AcqImage(path=test_file)
        
        # Try to create ROI (should fail because shape is None)
        bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
        with pytest.raises(ValueError, match="Cannot determine image bounds"):
            acq_image.rois.create_roi(bounds=bounds, channel=1)
    
    logger.info("  - Missing bounds correctly raises ValueError")


def test_acqimage_save_metadata() -> None:
    """Test AcqImage.save_metadata() method."""
    logger.info("Testing AcqImage.save_metadata()")
    
    with TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.tif"
        test_image = np.zeros((100, 200), dtype=np.uint8)
        acq_image = AcqImage(path=test_file, img_data=test_image)
        
        # Set some metadata
        acq_image.header.voxels = [0.001, 0.284]
        acq_image.header.voxels_units = ["s", "um"]
        acq_image.header.labels = ["time (s)", "space (um)"]
        acq_image.experiment_metadata.species = "mouse"
        acq_image.experiment_metadata.region = "cortex"
        
        # Create some ROIs
        bounds1 = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
        acq_image.rois.create_roi(bounds=bounds1, channel=1, name="ROI1")
        bounds2 = RoiBounds(dim0_start=60, dim0_stop=90, dim1_start=60, dim1_stop=90)
        acq_image.rois.create_roi(bounds=bounds2, channel=1, name="ROI2")
        
        # Save metadata
        saved = acq_image.save_metadata()
        assert saved is True
        
        # Check file exists
        metadata_file = test_file.with_suffix('.json')
        assert metadata_file.exists()
        
        # Verify file structure
        import json
        with open(metadata_file, 'r') as f:
            data = json.load(f)
        
        assert "version" in data
        assert data["version"] == "1.0"
        assert "header" in data
        assert "experiment_metadata" in data
        assert "rois" in data
        assert len(data["rois"]) == 2
        
        logger.info("  - AcqImage.save_metadata() works correctly")


def test_acqimage_load_metadata() -> None:
    """Test AcqImage.load_metadata() method."""
    logger.info("Testing AcqImage.load_metadata()")
    
    with TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.tif"
        test_image = np.zeros((100, 200), dtype=np.uint8)
        acq_image = AcqImage(path=test_file, img_data=test_image)
        
        # Set metadata and create ROIs
        acq_image.header.voxels = [0.001, 0.284]
        acq_image.experiment_metadata.species = "mouse"
        bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
        acq_image.rois.create_roi(bounds=bounds, channel=1, name="ROI1")
        
        # Save
        acq_image.save_metadata()
        
        # Create new AcqImage and load
        acq_image2 = AcqImage(path=test_file, img_data=test_image)
        loaded = acq_image2.load_metadata()
        assert loaded is True
        
        # Verify loaded data
        assert acq_image2.header.voxels == [0.001, 0.284]
        assert acq_image2.experiment_metadata.species == "mouse"
        assert acq_image2.rois.numRois() == 1
        loaded_roi = acq_image2.rois.get(1)
        assert loaded_roi is not None
        assert loaded_roi.name == "ROI1"
        assert loaded_roi.bounds.dim1_start == 10
        
        logger.info("  - AcqImage.load_metadata() works correctly")


def test_acqimage_load_metadata_clamps_rois() -> None:
    """Test that load_metadata() clamps out-of-bounds ROIs."""
    logger.info("Testing AcqImage.load_metadata() ROI clamping")
    
    with TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.tif"
        test_image = np.zeros((100, 200), dtype=np.uint8)
        
        # Create metadata file with out-of-bounds ROI
        import json
        metadata_file = test_file.with_suffix('.json')
        metadata = {
            "version": "1.0",
            "header": {
                "shape": [100, 200],
                "ndim": 2,
            },
            "experiment_metadata": {},
            "rois": [
                {
                    "id": 1,
                    "channel": 1,
                    "z": 0,
                    "name": "",
                    "note": "",
                    "dim0_start": -5,   # Out of bounds
                    "dim0_stop": 150,   # Out of bounds
                    "dim1_start": -10,  # Out of bounds
                    "dim1_stop": 250,   # Out of bounds
                }
            ]
        }
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f)
        
        # Load metadata
        acq_image = AcqImage(path=test_file, img_data=test_image)
        loaded = acq_image.load_metadata()
        assert loaded is True
        
        # Verify ROI was clamped
        roi = acq_image.rois.get(1)
        assert roi is not None
        assert roi.bounds.dim1_start >= 0
        assert roi.bounds.dim0_start >= 0
        assert roi.bounds.dim1_stop <= 200
        assert roi.bounds.dim0_stop <= 100
        
        logger.info("  - load_metadata() correctly clamps out-of-bounds ROIs")


def test_acqimage_metadata_round_trip() -> None:
    """Test round-trip save/load of metadata."""
    logger.info("Testing metadata round-trip")
    
    with TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.tif"
        test_image = np.zeros((100, 200), dtype=np.uint8)
        acq_image = AcqImage(path=test_file, img_data=test_image)
        
        # Set comprehensive metadata
        acq_image.header.shape = (100, 200)
        acq_image.header.ndim = 2
        acq_image.header.voxels = [0.001, 0.284]
        acq_image.header.voxels_units = ["s", "um"]
        acq_image.header.labels = ["time (s)", "space (um)"]
        acq_image.header.physical_size = [0.1, 56.8]
        
        acq_image.experiment_metadata.species = "mouse"
        acq_image.experiment_metadata.region = "cortex"
        acq_image.experiment_metadata.depth = 150.0
        
        # Create ROIs with different channels and z
        acq_image.addColorChannel(2, np.zeros((100, 200), dtype=np.uint8))
        bounds1 = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
        acq_image.rois.create_roi(bounds=bounds1, channel=1, z=0, name="ROI1", note="note1")
        bounds2 = RoiBounds(dim0_start=60, dim0_stop=90, dim1_start=60, dim1_stop=90)
        acq_image.rois.create_roi(bounds=bounds2, channel=2, z=0, name="ROI2", note="note2")
        
        # Save
        acq_image.save_metadata()
        
        # Load into new AcqImage
        acq_image2 = AcqImage(path=test_file, img_data=test_image)
        acq_image2.addColorChannel(2, np.zeros((100, 200), dtype=np.uint8))
        acq_image2.load_metadata()
        
        # Verify all data
        assert acq_image2.header.shape == (100, 200)
        assert acq_image2.header.voxels == [0.001, 0.284]
        assert acq_image2.experiment_metadata.species == "mouse"
        assert acq_image2.experiment_metadata.depth == 150.0
        
        assert acq_image2.rois.numRois() == 2
        roi1 = acq_image2.rois.get(1)
        assert roi1 is not None
        assert roi1.channel == 1
        assert roi1.z == 0
        assert roi1.name == "ROI1"
        
        roi2 = acq_image2.rois.get(2)
        assert roi2 is not None
        assert roi2.channel == 2
        
        logger.info("  - Metadata round-trip works correctly")


def test_acqimage_rois_property_lazy_init() -> None:
    """Test that rois property lazy-initializes RoiSet."""
    logger.info("Testing AcqImage.rois lazy initialization")
    
    test_image = np.zeros((100, 200), dtype=np.uint8)
    acq_image = AcqImage(path=None, img_data=test_image)
    
    # Initially _roi_set should be None
    assert acq_image._roi_set is None
    
    # Accessing rois property should create RoiSet
    rois = acq_image.rois
    assert acq_image._roi_set is not None
    assert isinstance(rois, RoiSet)
    
    # Subsequent accesses should return same instance
    rois2 = acq_image.rois
    assert rois2 is rois
    
    logger.info("  - rois property lazy initialization works correctly")


def test_roiset_iteration() -> None:
    """Test that RoiSet is iterable."""
    logger.info("Testing RoiSet iteration")
    
    test_image = np.zeros((100, 200), dtype=np.uint8)
    acq_image = AcqImage(path=None, img_data=test_image)
    
    # Create multiple ROIs
    bounds1 = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
    roi1 = acq_image.rois.create_roi(bounds=bounds1, channel=1)
    bounds2 = RoiBounds(dim0_start=60, dim0_stop=90, dim1_start=60, dim1_stop=90)
    roi2 = acq_image.rois.create_roi(bounds=bounds2, channel=1)
    bounds3 = RoiBounds(dim0_start=20, dim0_stop=40, dim1_start=20, dim1_stop=40)
    roi3 = acq_image.rois.create_roi(bounds=bounds3, channel=1)
    
    # Iterate
    rois_list = acq_image.rois.as_list()
    assert len(rois_list) == 3
    assert roi1 in rois_list
    assert roi2 in rois_list
    assert roi3 in rois_list
    
    logger.info("  - RoiSet iteration works correctly")


def test_image_bounds_dataclass() -> None:
    """Test ImageBounds dataclass."""
    logger.info("Testing ImageBounds dataclass")
    
    from kymflow.core.image_loaders.roi import ImageBounds
    
    # Create ImageBounds
    bounds = ImageBounds(width=200, height=100, num_slices=1)
    assert bounds.width == 200
    assert bounds.height == 100
    assert bounds.num_slices == 1
    
    # Test 3D
    bounds_3d = ImageBounds(width=200, height=100, num_slices=10)
    assert bounds_3d.num_slices == 10
    
    logger.info("  - ImageBounds dataclass works correctly")


def test_image_size_dataclass() -> None:
    """Test ImageSize dataclass."""
    logger.info("Testing ImageSize dataclass")
    
    from kymflow.core.image_loaders.roi import ImageSize
    
    # Create ImageSize
    size = ImageSize(width=200, height=100)
    assert size.width == 200
    assert size.height == 100
    
    logger.info("  - ImageSize dataclass works correctly")


def test_acqimage_get_image_bounds() -> None:
    """Test AcqImage.get_image_bounds() method."""
    logger.info("Testing AcqImage.get_image_bounds()")
    
    from kymflow.core.image_loaders.roi import ImageBounds
    
    # Test 2D image
    test_image = np.zeros((100, 200), dtype=np.uint8)
    acq_image = AcqImage(path=None, img_data=test_image)
    
    bounds = acq_image.get_image_bounds()
    assert isinstance(bounds, ImageBounds)
    assert bounds.width == 200
    assert bounds.height == 100
    assert bounds.num_slices == 1
    
    # Test 3D image
    test_image_3d = np.zeros((10, 100, 200), dtype=np.uint8)
    acq_image_3d = AcqImage(path=None, img_data=test_image_3d)
    
    bounds_3d = acq_image_3d.get_image_bounds()
    assert bounds_3d.width == 200
    assert bounds_3d.height == 100
    assert bounds_3d.num_slices == 10
    
    logger.info("  - AcqImage.get_image_bounds() works correctly")


def test_clamp_coordinates_to_size_with_imagesize() -> None:
    """Test clamp_coordinates_to_size() with ImageSize parameter."""
    logger.info("Testing clamp_coordinates_to_size() with ImageSize")
    
    from kymflow.core.image_loaders.roi import clamp_coordinates_to_size, ImageSize, RoiBounds
    
    # Create ImageSize
    size = ImageSize(width=200, height=100)
    
    # Test clamping
    bounds = RoiBounds(dim0_start=-10, dim0_stop=150, dim1_start=-5, dim1_stop=250)
    clamped = clamp_coordinates_to_size(bounds, size)
    
    assert clamped.dim0_start >= 0
    assert clamped.dim0_stop <= 100
    assert clamped.dim1_start >= 0
    assert clamped.dim1_stop <= 200
    
    logger.info("  - clamp_coordinates_to_size() with ImageSize works correctly")


def test_roi_bounds_from_image_bounds() -> None:
    """Test RoiBounds.from_image_bounds() classmethod."""
    logger.info("Testing RoiBounds.from_image_bounds()")
    
    # Test 2D image bounds
    image_bounds = ImageBounds(width=200, height=100, num_slices=1)
    roi_bounds = RoiBounds.from_image_bounds(image_bounds)
    
    assert roi_bounds.dim0_start == 0
    assert roi_bounds.dim0_stop == 100  # height
    assert roi_bounds.dim1_start == 0
    assert roi_bounds.dim1_stop == 200  # width
    
    # Test 3D image bounds
    image_bounds_3d = ImageBounds(width=50, height=10000, num_slices=10)
    roi_bounds_3d = RoiBounds.from_image_bounds(image_bounds_3d)
    
    assert roi_bounds_3d.dim0_start == 0
    assert roi_bounds_3d.dim0_stop == 10000  # height
    assert roi_bounds_3d.dim1_start == 0
    assert roi_bounds_3d.dim1_stop == 50  # width
    
    logger.info("  - RoiBounds.from_image_bounds() works correctly")


def test_roi_bounds_from_image_size() -> None:
    """Test RoiBounds.from_image_size() classmethod."""
    logger.info("Testing RoiBounds.from_image_size()")
    
    # Test with ImageSize
    size = ImageSize(width=200, height=100)
    roi_bounds = RoiBounds.from_image_size(size)
    
    assert roi_bounds.dim0_start == 0
    assert roi_bounds.dim0_stop == 100  # height
    assert roi_bounds.dim1_start == 0
    assert roi_bounds.dim1_stop == 200  # width
    
    # Test with different dimensions
    size2 = ImageSize(width=50, height=10000)
    roi_bounds2 = RoiBounds.from_image_size(size2)
    
    assert roi_bounds2.dim0_start == 0
    assert roi_bounds2.dim0_stop == 10000  # height
    assert roi_bounds2.dim1_start == 0
    assert roi_bounds2.dim1_stop == 50  # width
    
    logger.info("  - RoiBounds.from_image_size() works correctly")


def test_roiset_create_roi_with_none_bounds() -> None:
    """Test RoiSet.create_roi() with bounds=None creates full-image ROI."""
    logger.info("Testing RoiSet.create_roi() with bounds=None")
    
    # Test 2D image
    test_image = np.zeros((100, 200), dtype=np.uint8)
    acq_image = AcqImage(path=None, img_data=test_image)
    
    # Create ROI with bounds=None (should create full-image bounds)
    roi = acq_image.rois.create_roi(bounds=None, channel=1, z=0)
    
    assert roi.id == 1
    assert roi.channel == 1
    assert roi.z == 0
    # Should encompass entire image
    assert roi.bounds.dim0_start == 0
    assert roi.bounds.dim0_stop == 100  # height
    assert roi.bounds.dim1_start == 0
    assert roi.bounds.dim1_stop == 200  # width
    
    # Test with explicit None (same as omitting)
    roi2 = acq_image.rois.create_roi(bounds=None, name="Full Image ROI")
    assert roi2.id == 2
    assert roi2.bounds.dim0_stop == 100
    assert roi2.bounds.dim1_stop == 200
    assert roi2.name == "Full Image ROI"
    
    logger.info("  - RoiSet.create_roi() with bounds=None works correctly")


def test_roiset_create_roi_with_none_bounds_3d() -> None:
    """Test RoiSet.create_roi() with bounds=None for 3D image."""
    logger.info("Testing RoiSet.create_roi() with bounds=None for 3D image")
    
    # Test 3D image (shape: num_slices, height, width)
    test_image_3d = np.zeros((10, 10000, 50), dtype=np.uint8)
    acq_image_3d = AcqImage(path=None, img_data=test_image_3d)
    
    # Create ROI with bounds=None (should create full-image bounds)
    roi = acq_image_3d.rois.create_roi(bounds=None, channel=1, z=0)
    
    assert roi.id == 1
    assert roi.channel == 1
    assert roi.z == 0
    # Should encompass entire image
    assert roi.bounds.dim0_start == 0
    assert roi.bounds.dim0_stop == 10000  # height
    assert roi.bounds.dim1_start == 0
    assert roi.bounds.dim1_stop == 50  # width
    
    # Test with different z slice
    roi2 = acq_image_3d.rois.create_roi(bounds=None, channel=1, z=5)
    assert roi2.id == 2
    assert roi2.z == 5
    assert roi2.bounds.dim0_stop == 10000
    assert roi2.bounds.dim1_stop == 50
    
    logger.info("  - RoiSet.create_roi() with bounds=None for 3D image works correctly")


def test_roiset_create_roi_marks_dirty() -> None:
    """Test that create_roi() marks AcqImage as dirty."""
    logger.info("Testing RoiSet.create_roi() marks dirty")
    
    test_image = np.zeros((100, 200), dtype=np.uint8)
    acq_image = AcqImage(path=None, img_data=test_image)
    
    # Initially should not be dirty
    assert acq_image.is_metadata_dirty is False
    
    # Create ROI - should mark as dirty
    bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
    acq_image.rois.create_roi(bounds=bounds, channel=1)
    
    assert acq_image.is_metadata_dirty is True
    
    logger.info("  - create_roi() marks dirty correctly")


def test_roiset_delete_marks_dirty() -> None:
    """Test that delete() marks AcqImage as dirty."""
    logger.info("Testing RoiSet.delete() marks dirty")
    
    test_image = np.zeros((100, 200), dtype=np.uint8)
    acq_image = AcqImage(path=None, img_data=test_image)
    
    # Create ROI
    bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
    roi = acq_image.rois.create_roi(bounds=bounds, channel=1)
    
    # Clear dirty flag
    acq_image.clear_metadata_dirty()
    assert acq_image.is_metadata_dirty is False
    
    # Delete ROI - should mark as dirty
    acq_image.rois.delete(roi.id)
    assert acq_image.is_metadata_dirty is True
    
    logger.info("  - delete() marks dirty correctly")


def test_roiset_clear_marks_dirty() -> None:
    """Test that clear() marks AcqImage as dirty."""
    logger.info("Testing RoiSet.clear() marks dirty")
    
    test_image = np.zeros((100, 200), dtype=np.uint8)
    acq_image = AcqImage(path=None, img_data=test_image)
    
    # Create multiple ROIs
    bounds1 = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
    acq_image.rois.create_roi(bounds=bounds1, channel=1)
    bounds2 = RoiBounds(dim0_start=60, dim0_stop=90, dim1_start=60, dim1_stop=90)
    acq_image.rois.create_roi(bounds=bounds2, channel=1)
    
    # Clear dirty flag
    acq_image.clear_metadata_dirty()
    assert acq_image.is_metadata_dirty is False
    
    # Clear all ROIs - should mark as dirty
    acq_image.rois.clear()
    assert acq_image.is_metadata_dirty is True
    assert acq_image.rois.numRois() == 0
    
    logger.info("  - clear() marks dirty correctly")


def test_roiset_create_roi_bounds_none_vs_explicit() -> None:
    """Test that create_roi(bounds=None) and explicit full-image bounds are equivalent."""
    logger.info("Testing create_roi(bounds=None) vs explicit full-image bounds")
    
    test_image = np.zeros((100, 200), dtype=np.uint8)
    acq_image = AcqImage(path=None, img_data=test_image)
    
    # Create ROI with bounds=None
    roi_none = acq_image.rois.create_roi(bounds=None, channel=1, z=0)
    
    # Create ROI with explicit full-image bounds
    image_bounds = acq_image.get_image_bounds()
    full_bounds = RoiBounds.from_image_bounds(image_bounds)
    roi_explicit = acq_image.rois.create_roi(bounds=full_bounds, channel=1, z=0)
    
    # Both should have the same bounds
    assert roi_none.bounds.dim0_start == roi_explicit.bounds.dim0_start
    assert roi_none.bounds.dim0_stop == roi_explicit.bounds.dim0_stop
    assert roi_none.bounds.dim1_start == roi_explicit.bounds.dim1_start
    assert roi_none.bounds.dim1_stop == roi_explicit.bounds.dim1_stop
    
    logger.info("  - create_roi(bounds=None) and explicit full-image bounds are equivalent")


def test_roiset_get_roi_ids() -> None:
    """Test RoiSet.get_roi_ids() method."""
    logger.info("Testing RoiSet.get_roi_ids()")
    
    test_image = np.zeros((100, 200), dtype=np.uint8)
    acq_image = AcqImage(path=None, img_data=test_image)
    
    # Create multiple ROIs
    bounds1 = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
    roi1 = acq_image.rois.create_roi(bounds=bounds1, channel=1)
    bounds2 = RoiBounds(dim0_start=60, dim0_stop=90, dim1_start=60, dim1_stop=90)
    roi2 = acq_image.rois.create_roi(bounds=bounds2, channel=1)
    bounds3 = RoiBounds(dim0_start=20, dim0_stop=40, dim1_start=20, dim1_stop=40)
    roi3 = acq_image.rois.create_roi(bounds=bounds3, channel=1)
    
    # Get ROI IDs
    roi_ids = acq_image.rois.get_roi_ids()
    assert len(roi_ids) == 3
    assert roi_ids == [1, 2, 3]  # Should be in creation order
    
    # Delete one ROI
    acq_image.rois.delete(roi2.id)
    roi_ids_after = acq_image.rois.get_roi_ids()
    assert len(roi_ids_after) == 2
    assert roi_ids_after == [1, 3]  # Should maintain order
    
    # Test empty set
    acq_image.rois.clear()
    assert acq_image.rois.get_roi_ids() == []
    
    logger.info("  - RoiSet.get_roi_ids() works correctly")


def test_roiset_as_list() -> None:
    """Test RoiSet.as_list() method."""
    logger.info("Testing RoiSet.as_list()")
    
    test_image = np.zeros((100, 200), dtype=np.uint8)
    acq_image = AcqImage(path=None, img_data=test_image)
    
    # Create multiple ROIs
    bounds1 = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
    roi1 = acq_image.rois.create_roi(bounds=bounds1, channel=1, name="ROI1")
    bounds2 = RoiBounds(dim0_start=60, dim0_stop=90, dim1_start=60, dim1_stop=90)
    roi2 = acq_image.rois.create_roi(bounds=bounds2, channel=1, name="ROI2")
    
    # Get as list
    rois_list = acq_image.rois.as_list()
    assert len(rois_list) == 2
    assert isinstance(rois_list, list)
    assert rois_list[0] == roi1
    assert rois_list[1] == roi2
    
    # Verify order is preserved
    assert rois_list[0].id == 1
    assert rois_list[1].id == 2
    
    # Test empty set
    acq_image.rois.clear()
    assert acq_image.rois.as_list() == []
    
    logger.info("  - RoiSet.as_list() works correctly")


def test_roiset_clear_functionality() -> None:
    """Test RoiSet.clear() method functionality."""
    logger.info("Testing RoiSet.clear() functionality")
    
    test_image = np.zeros((100, 200), dtype=np.uint8)
    acq_image = AcqImage(path=None, img_data=test_image)
    
    # Create multiple ROIs
    bounds1 = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
    acq_image.rois.create_roi(bounds=bounds1, channel=1)
    bounds2 = RoiBounds(dim0_start=60, dim0_stop=90, dim1_start=60, dim1_stop=90)
    acq_image.rois.create_roi(bounds=bounds2, channel=1)
    bounds3 = RoiBounds(dim0_start=20, dim0_stop=40, dim1_start=20, dim1_stop=40)
    acq_image.rois.create_roi(bounds=bounds3, channel=1)
    
    assert acq_image.rois.numRois() == 3
    
    # Clear all ROIs
    deleted_count = acq_image.rois.clear()
    assert deleted_count == 3
    assert acq_image.rois.numRois() == 0
    assert acq_image.rois.get_roi_ids() == []
    assert acq_image.rois.as_list() == []
    
    # Verify next_id is reset
    new_roi = acq_image.rois.create_roi(bounds=bounds1, channel=1)
    assert new_roi.id == 1  # Should start from 1 again
    
    # Test clearing empty set
    acq_image.rois.clear()
    assert acq_image.rois.clear() == 0
    
    logger.info("  - RoiSet.clear() works correctly")


def test_roi_bounds_float() -> None:
    """Test RoiBoundsFloat dataclass."""
    logger.info("Testing RoiBoundsFloat dataclass")
    
    from kymflow.core.image_loaders.roi import RoiBoundsFloat
    
    # Create RoiBoundsFloat with float coordinates
    bounds_float = RoiBoundsFloat(
        dim0_start=10.5,
        dim0_stop=80.3,
        dim1_start=20.7,
        dim1_stop=50.9
    )
    
    assert bounds_float.dim0_start == 10.5
    assert bounds_float.dim0_stop == 80.3
    assert bounds_float.dim1_start == 20.7
    assert bounds_float.dim1_stop == 50.9
    
    logger.info("  - RoiBoundsFloat dataclass works correctly")


def test_clamp_coordinates() -> None:
    """Test clamp_coordinates() function."""
    logger.info("Testing clamp_coordinates() function")
    
    import numpy as np
    from kymflow.core.image_loaders.roi import clamp_coordinates, RoiBounds
    
    # Create bounds with out-of-range coordinates
    bounds = RoiBounds(dim0_start=-10, dim0_stop=150, dim1_start=-5, dim1_stop=250)
    
    # Clamp to image size (height=100, width=200)
    test_image = np.zeros((100, 200), dtype=np.uint8)
    clamped = clamp_coordinates(bounds, test_image)
    
    assert clamped.dim0_start >= 0
    assert clamped.dim0_stop <= 100
    assert clamped.dim1_start >= 0
    assert clamped.dim1_stop <= 200
    
    # Test with valid coordinates (should remain unchanged)
    bounds_valid = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=20, dim1_stop=80)
    clamped_valid = clamp_coordinates(bounds_valid, test_image)
    assert clamped_valid.dim0_start == 10
    assert clamped_valid.dim0_stop == 50
    assert clamped_valid.dim1_start == 20
    assert clamped_valid.dim1_stop == 80
    
    logger.info("  - clamp_coordinates() works correctly")


def test_roi_rect_is_equal() -> None:
    """Test roi_rect_is_equal() function."""
    logger.info("Testing roi_rect_is_equal() function")
    
    from kymflow.core.image_loaders.roi import roi_rect_is_equal, RoiBounds
    
    # Test equal bounds
    bounds1 = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=20, dim1_stop=80)
    bounds2 = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=20, dim1_stop=80)
    assert roi_rect_is_equal(bounds1, bounds2) is True
    
    # Test different bounds
    bounds3 = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=20, dim1_stop=81)
    assert roi_rect_is_equal(bounds1, bounds3) is False
    
    # Test different dim0_start
    bounds4 = RoiBounds(dim0_start=11, dim0_stop=50, dim1_start=20, dim1_stop=80)
    assert roi_rect_is_equal(bounds1, bounds4) is False
    
    logger.info("  - roi_rect_is_equal() works correctly")


def test_point_in_roi() -> None:
    """Test point_in_roi() function."""
    logger.info("Testing point_in_roi() function")
    
    from kymflow.core.image_loaders.roi import point_in_roi, RoiBounds
    
    bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=20, dim1_stop=80)
    
    # Test point inside bounds
    assert point_in_roi(bounds, 30, 50) is True
    
    # Test point on boundary (start)
    assert point_in_roi(bounds, 10, 20) is True
    
    # Test point on boundary (stop)
    assert point_in_roi(bounds, 50, 80) is True
    
    # Test point outside bounds (before start)
    assert point_in_roi(bounds, 5, 15) is False
    
    # Test point outside bounds (after stop)
    assert point_in_roi(bounds, 60, 90) is False
    
    # Test point outside bounds (between but outside one dimension)
    assert point_in_roi(bounds, 30, 10) is False  # dim1_coord too small
    assert point_in_roi(bounds, 5, 50) is False   # dim0_coord too small
    
    logger.info("  - point_in_roi() works correctly")


def test_hit_test_rois() -> None:
    """Test hit_test_rois() function."""
    logger.info("Testing hit_test_rois() function")
    
    from kymflow.core.image_loaders.roi import hit_test_rois, RoiBounds
    
    test_image = np.zeros((100, 200), dtype=np.uint8)
    acq_image = AcqImage(path=None, img_data=test_image)
    
    # Create multiple ROIs
    bounds1 = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
    roi1 = acq_image.rois.create_roi(bounds=bounds1, channel=1, name="ROI1")
    bounds2 = RoiBounds(dim0_start=60, dim0_stop=90, dim1_start=60, dim1_stop=90)
    roi2 = acq_image.rois.create_roi(bounds=bounds2, channel=1, name="ROI2")
    
    # Test hit in interior of ROI2 (most recent, should be hit first)
    hit_roi, mode = hit_test_rois(acq_image.rois, 75, 75, edge_tol=5)
    assert hit_roi == roi2
    assert mode == "moving"
    
    # Test hit on edge of ROI2
    hit_roi, mode = hit_test_rois(acq_image.rois, 60, 75, edge_tol=5)  # On dim0_start edge (row 60)
    assert hit_roi == roi2
    assert mode == "resizing_dim0_start"
    
    # Test hit on dim1_stop edge
    hit_roi, mode = hit_test_rois(acq_image.rois, 75, 90, edge_tol=5)
    assert hit_roi == roi2
    assert mode == "resizing_dim1_stop"
    
    # Test hit on dim0_start edge
    hit_roi, mode = hit_test_rois(acq_image.rois, 60, 75, edge_tol=5)
    assert hit_roi == roi2
    # Could be either dim1_start or dim0_start depending on which edge is closer
    assert mode in ("resizing_dim1_start", "resizing_dim0_start")
    
    # Test hit in ROI1 (should not be hit if ROI2 overlaps, but ROI2 is checked first)
    # Since ROI2 is more recent, it's checked first
    hit_roi, mode = hit_test_rois(acq_image.rois, 30, 30, edge_tol=5)
    assert hit_roi == roi1
    assert mode == "moving"
    
    # Test hit outside all ROIs
    hit_roi, mode = hit_test_rois(acq_image.rois, 5, 5, edge_tol=5)
    assert hit_roi is None
    assert mode is None
    
    # Test with edge tolerance
    # Point just outside edge but within tolerance
    hit_roi, mode = hit_test_rois(acq_image.rois, 10, 5, edge_tol=5)  # 5 pixels from dim1_start
    assert hit_roi == roi1
    assert mode == "resizing_dim1_start"
    
    logger.info("  - hit_test_rois() works correctly")


def test_roi_calculate_image_stats() -> None:
    """Test ROI.calculate_image_stats() method."""
    logger.info("Testing ROI.calculate_image_stats()")
    
    # Create test image with known values
    test_image = np.array([
        [10, 20, 30, 40],
        [50, 60, 70, 80],
        [90, 100, 110, 120],
        [130, 140, 150, 160]
    ], dtype=np.uint8)
    acq_image = AcqImage(path=None, img_data=test_image)
    
    # Create ROI covering region [1:3, 1:3] = [[60, 70], [100, 110]]
    bounds = RoiBounds(dim0_start=1, dim0_stop=3, dim1_start=1, dim1_stop=3)
    roi = ROI(id=1, channel=1, z=0, bounds=bounds)
    
    # Calculate stats
    roi.calculate_image_stats(acq_image)
    
    # Verify stats
    # ROI region [1:3, 1:3] = [[60, 70], [100, 110]]
    # Values: 60, 70, 100, 110
    assert roi.img_min == 60
    assert roi.img_max == 110
    assert roi.img_mean == pytest.approx(85.0, abs=0.01)  # (60+70+100+110)/4 = 85.0
    # Std: sqrt(((60-85)^2 + (70-85)^2 + (100-85)^2 + (110-85)^2)/4) ≈ 20.6155
    assert roi.img_std == pytest.approx(20.6155, abs=0.1)
    
    logger.info("  - ROI.calculate_image_stats() works correctly")


def test_roi_calculate_image_stats_full_image() -> None:
    """Test ROI.calculate_image_stats() with full-image ROI."""
    logger.info("Testing ROI.calculate_image_stats() with full-image ROI")
    
    # Create test image
    test_image = np.array([
        [0, 50, 100],
        [150, 200, 255]
    ], dtype=np.uint8)
    acq_image = AcqImage(path=None, img_data=test_image)
    
    # Create full-image ROI
    bounds = RoiBounds(dim0_start=0, dim0_stop=2, dim1_start=0, dim1_stop=3)
    roi = ROI(id=1, channel=1, z=0, bounds=bounds)
    
    # Calculate stats
    roi.calculate_image_stats(acq_image)
    
    # Verify stats for full image
    # Image: [[0, 50, 100], [150, 200, 255]]
    # All values: 0, 50, 100, 150, 200, 255
    assert roi.img_min == 0
    assert roi.img_max == 255
    # Mean: (0+50+100+150+200+255)/6 = 755/6 ≈ 125.833
    assert roi.img_mean == pytest.approx(125.833, abs=0.1)
    
    logger.info("  - ROI.calculate_image_stats() works correctly for full-image ROI")


def test_roi_calculate_image_stats_single_pixel() -> None:
    """Test ROI.calculate_image_stats() with single-pixel ROI."""
    logger.info("Testing ROI.calculate_image_stats() with single-pixel ROI")
    
    test_image = np.array([[10, 20, 30], [40, 50, 60]], dtype=np.uint8)
    acq_image = AcqImage(path=None, img_data=test_image)
    
    # Single pixel ROI
    bounds = RoiBounds(dim0_start=1, dim0_stop=2, dim1_start=1, dim1_stop=2)
    roi = ROI(id=1, channel=1, z=0, bounds=bounds)
    
    roi.calculate_image_stats(acq_image)
    
    # For single pixel, min=max=mean, std=0
    assert roi.img_min == 50
    assert roi.img_max == 50
    assert roi.img_mean == 50.0
    assert roi.img_std == 0.0
    
    logger.info("  - ROI.calculate_image_stats() works correctly for single-pixel ROI")


def test_roi_calculate_image_stats_3d() -> None:
    """Test ROI.calculate_image_stats() with 3D image."""
    logger.info("Testing ROI.calculate_image_stats() with 3D image")
    
    # Create 3D test image (3 slices, 4 rows, 5 cols)
    test_image = np.zeros((3, 4, 5), dtype=np.uint8)
    # Set slice 1 to have specific values
    test_image[1, :, :] = np.arange(20).reshape(4, 5)
    acq_image = AcqImage(path=None, img_data=test_image)
    
    # Create ROI on slice 1
    bounds = RoiBounds(dim0_start=1, dim0_stop=3, dim1_start=1, dim1_stop=4)
    roi = ROI(id=1, channel=1, z=1, bounds=bounds)
    
    roi.calculate_image_stats(acq_image)
    
    # Verify stats are calculated from slice 1, not slice 0
    assert roi.img_min >= 5  # Should be from slice 1 region
    assert roi.img_max <= 19
    
    logger.info("  - ROI.calculate_image_stats() works correctly for 3D image")


def test_roi_calculate_image_stats_missing_data() -> None:
    """Test ROI.calculate_image_stats() raises error when image data missing."""
    logger.info("Testing ROI.calculate_image_stats() with missing image data")
    
    # Create AcqImage without image data
    with TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.tif"
        test_file.touch()
        acq_image = AcqImage(path=test_file)  # No img_data, not loaded
    
    bounds = RoiBounds(dim0_start=0, dim0_stop=10, dim1_start=0, dim1_stop=10)
    roi = ROI(id=1, channel=1, z=0, bounds=bounds)
    
    # Should raise ValueError
    with pytest.raises(ValueError, match="Image data not available"):
        roi.calculate_image_stats(acq_image)
    
    logger.info("  - ROI.calculate_image_stats() correctly raises error for missing data")


def test_roi_calculate_image_stats_invalid_channel() -> None:
    """Test ROI.calculate_image_stats() with invalid channel."""
    logger.info("Testing ROI.calculate_image_stats() with invalid channel")
    
    test_image = np.zeros((10, 10), dtype=np.uint8)
    acq_image = AcqImage(path=None, img_data=test_image)
    
    bounds = RoiBounds(dim0_start=0, dim0_stop=10, dim1_start=0, dim1_stop=10)
    roi = ROI(id=1, channel=99, z=0, bounds=bounds)  # Invalid channel
    
    # Should raise ValueError (invalid channel means get_img_slice returns None)
    with pytest.raises(ValueError, match="Image data not available"):
        roi.calculate_image_stats(acq_image)
    
    logger.info("  - ROI.calculate_image_stats() correctly raises error for invalid channel")


def test_roiset_create_roi_calculates_stats() -> None:
    """Test that RoiSet.create_roi() calculates image stats."""
    logger.info("Testing RoiSet.create_roi() calculates image stats")
    
    # Create test image with known values
    test_image = np.array([
        [10, 20, 30],
        [40, 50, 60],
        [70, 80, 90]
    ], dtype=np.uint8)
    acq_image = AcqImage(path=None, img_data=test_image)
    
    # Create ROI
    bounds = RoiBounds(dim0_start=1, dim0_stop=3, dim1_start=1, dim1_stop=3)
    roi = acq_image.rois.create_roi(bounds=bounds, channel=1, z=0)
    
    # Verify stats were calculated
    assert roi.img_min is not None
    assert roi.img_max is not None
    assert roi.img_mean is not None
    assert roi.img_std is not None
    
    # Verify correct values for region [1:3, 1:3] = [[50, 60], [80, 90]]
    assert roi.img_min == 50
    assert roi.img_max == 90
    
    logger.info("  - RoiSet.create_roi() calculates image stats correctly")


def test_roiset_create_roi_stats_when_data_unavailable() -> None:
    """Test that RoiSet.create_roi() handles missing image data gracefully."""
    logger.info("Testing RoiSet.create_roi() with missing image data")
    
    # Create AcqImage without loaded image data
    with TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.tif"
        test_file.touch()
        acq_image = AcqImage(path=test_file)  # No img_data
    
    # Set header so bounds validation works
    acq_image.header.shape = (100, 200)
    acq_image.header.ndim = 2
    
    bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
    roi = acq_image.rois.create_roi(bounds=bounds, channel=1, z=0)
    
    # Stats should be None (calculation failed but didn't crash)
    assert roi.img_min is None
    assert roi.img_max is None
    assert roi.img_mean is None
    assert roi.img_std is None
    
    logger.info("  - RoiSet.create_roi() handles missing image data gracefully")


def test_roiset_edit_roi_recalculates_stats() -> None:
    """Test that RoiSet.edit_roi() recalculates stats when geometry changes."""
    logger.info("Testing RoiSet.edit_roi() recalculates stats")
    
    # Create test image
    test_image = np.array([
        [10, 20, 30, 40],
        [50, 60, 70, 80],
        [90, 100, 110, 120],
        [130, 140, 150, 160]
    ], dtype=np.uint8)
    acq_image = AcqImage(path=None, img_data=test_image)
    
    # Create ROI
    bounds1 = RoiBounds(dim0_start=0, dim0_stop=2, dim1_start=0, dim1_stop=2)
    roi = acq_image.rois.create_roi(bounds=bounds1, channel=1, z=0)
    original_min = roi.img_min
    original_max = roi.img_max
    
    # Edit bounds (should recalculate stats)
    bounds2 = RoiBounds(dim0_start=2, dim0_stop=4, dim1_start=2, dim1_stop=4)
    acq_image.rois.edit_roi(roi.id, bounds=bounds2)
    
    # Stats should be different (new region)
    assert roi.img_min != original_min
    assert roi.img_max != original_max
    assert roi.img_min == 110  # New region min
    assert roi.img_max == 160  # New region max
    
    logger.info("  - RoiSet.edit_roi() recalculates stats when bounds change")


def test_roiset_edit_roi_recalculates_stats_on_channel_change() -> None:
    """Test that RoiSet.edit_roi() recalculates stats when channel changes."""
    logger.info("Testing RoiSet.edit_roi() recalculates stats on channel change")
    
    # Create multi-channel image
    # Use uint16 for channel 2 to allow larger values, or use smaller values for uint8
    test_image_ch1 = np.array([[10, 20], [30, 40]], dtype=np.uint8)
    test_image_ch2 = np.array([[100, 200], [250, 255]], dtype=np.uint8)  # Changed to fit uint8 range
    acq_image = AcqImage(path=None, img_data=test_image_ch1)
    acq_image.addColorChannel(2, test_image_ch2)
    
    # Create ROI on channel 1
    bounds = RoiBounds(dim0_start=0, dim0_stop=2, dim1_start=0, dim1_stop=2)
    roi = acq_image.rois.create_roi(bounds=bounds, channel=1, z=0)
    assert roi.img_max == 40  # Channel 1 max
    
    # Change to channel 2 (should recalculate)
    acq_image.rois.edit_roi(roi.id, channel=2)
    assert roi.img_max == 255  # Channel 2 max (updated from 400 to 255)
    
    logger.info("  - RoiSet.edit_roi() recalculates stats when channel changes")


def test_roiset_edit_roi_no_recalc_when_name_changes() -> None:
    """Test that RoiSet.edit_roi() doesn't recalculate stats when only name changes."""
    logger.info("Testing RoiSet.edit_roi() doesn't recalc stats for name change")
    
    test_image = np.array([[10, 20], [30, 40]], dtype=np.uint8)
    acq_image = AcqImage(path=None, img_data=test_image)
    
    bounds = RoiBounds(dim0_start=0, dim0_stop=2, dim1_start=0, dim1_stop=2)
    roi = acq_image.rois.create_roi(bounds=bounds, channel=1, z=0)
    original_min = roi.img_min
    original_max = roi.img_max
    
    # Edit only name (not geometry)
    acq_image.rois.edit_roi(roi.id, name="New Name")
    
    # Stats should be unchanged
    assert roi.img_min == original_min
    assert roi.img_max == original_max
    
    logger.info("  - RoiSet.edit_roi() doesn't recalculate stats for non-geometry changes")


def test_roi_image_stats_serialization() -> None:
    """Test that ROI image stats are serialized to/from JSON."""
    logger.info("Testing ROI image stats serialization")
    
    test_image = np.array([[10, 20], [30, 40]], dtype=np.uint8)
    acq_image = AcqImage(path=None, img_data=test_image)
    
    # Create ROI and calculate stats
    bounds = RoiBounds(dim0_start=0, dim0_stop=2, dim1_start=0, dim1_stop=2)
    roi = acq_image.rois.create_roi(bounds=bounds, channel=1, z=0)
    
    # Serialize
    roi_dict = roi.to_dict()
    assert "img_min" in roi_dict
    assert "img_max" in roi_dict
    assert "img_mean" in roi_dict
    assert "img_std" in roi_dict
    assert roi_dict["img_min"] == 10
    assert roi_dict["img_max"] == 40
    
    # Deserialize
    roi2 = ROI.from_dict(roi_dict)
    assert roi2.img_min == 10
    assert roi2.img_max == 40
    assert roi2.img_mean == pytest.approx(25.0, abs=0.1)
    
    logger.info("  - ROI image stats serialize correctly")


def test_roi_image_stats_backward_compatibility() -> None:
    """Test that old JSON files without image stats load correctly."""
    logger.info("Testing ROI image stats backward compatibility")
    
    # Simulate old JSON format (no image stats fields)
    old_roi_dict = {
        "id": 1,
        "channel": 1,
        "z": 0,
        "name": "",
        "note": "",
        "revision": 0,
        "dim0_start": 0,
        "dim0_stop": 10,
        "dim1_start": 0,
        "dim1_stop": 10
    }
    
    # Should load successfully with None stats
    roi = ROI.from_dict(old_roi_dict)
    assert roi.id == 1
    assert roi.img_min is None
    assert roi.img_max is None
    assert roi.img_mean is None
    assert roi.img_std is None
    
    logger.info("  - ROI backward compatibility works correctly")


def test_roi_image_stats_round_trip() -> None:
    """Test round-trip save/load of ROI with image stats."""
    logger.info("Testing ROI image stats round-trip")
    
    with TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.tif"
        test_image = np.array([[10, 20], [30, 40]], dtype=np.uint8)
        acq_image = AcqImage(path=test_file, img_data=test_image)
        
        # Create ROI (stats calculated on creation)
        bounds = RoiBounds(dim0_start=0, dim0_stop=2, dim1_start=0, dim1_stop=2)
        roi = acq_image.rois.create_roi(bounds=bounds, channel=1, z=0)
        original_min = roi.img_min
        original_max = roi.img_max
        
        # Save metadata
        acq_image.save_metadata()
        
        # Load into new AcqImage
        acq_image2 = AcqImage(path=test_file, img_data=test_image)
        acq_image2.load_metadata()
        
        # Verify stats were preserved
        loaded_roi = acq_image2.rois.get(1)
        assert loaded_roi is not None
        assert loaded_roi.img_min == original_min
        assert loaded_roi.img_max == original_max
        assert loaded_roi.img_mean == pytest.approx(roi.img_mean, abs=0.01)
        assert loaded_roi.img_std == pytest.approx(roi.img_std, abs=0.01)
        
        logger.info("  - ROI image stats round-trip works correctly")

