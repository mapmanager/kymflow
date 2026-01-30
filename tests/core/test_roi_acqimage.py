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

