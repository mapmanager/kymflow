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
from kymflow.core.roi import ROI, RoiSet
from kymflow.core.utils.logging import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)


def test_roi_with_channel_and_z() -> None:
    """Test ROI class with channel and z attributes."""
    logger.info("Testing ROI with channel and z attributes")
    
    # Create ROI with channel and z
    roi = ROI(id=1, channel=2, z=5, left=10, top=20, right=50, bottom=80)
    
    assert roi.id == 1
    assert roi.channel == 2
    assert roi.z == 5
    assert roi.left == 10
    assert roi.top == 20
    assert roi.right == 50
    assert roi.bottom == 80
    
    # Test backward compatibility (defaults)
    roi2 = ROI(id=2, left=10, top=20, right=50, bottom=80)
    assert roi2.channel == 1  # Default
    assert roi2.z == 0  # Default
    
    logger.info("  - ROI channel and z attributes work correctly")


def test_roi_to_dict_from_dict() -> None:
    """Test ROI serialization with channel and z."""
    logger.info("Testing ROI to_dict/from_dict with channel and z")
    
    roi = ROI(id=1, channel=2, z=5, left=10, top=20, right=50, bottom=80, name="test", note="note")
    
    # Serialize
    roi_dict = roi.to_dict()
    assert roi_dict["id"] == 1
    assert roi_dict["channel"] == 2
    assert roi_dict["z"] == 5
    assert roi_dict["left"] == 10
    
    # Deserialize
    roi2 = ROI.from_dict(roi_dict)
    assert roi2.id == 1
    assert roi2.channel == 2
    assert roi2.z == 5
    assert roi2.left == 10
    
    # Test backward compatibility (missing channel/z)
    roi_dict_old = {"id": 1, "left": 10, "top": 20, "right": 50, "bottom": 80}
    roi3 = ROI.from_dict(roi_dict_old)
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
    roi = acq_image.rois.create_roi(left=10, top=20, right=50, bottom=80, channel=1, z=0)
    
    assert roi.id == 1
    assert roi.channel == 1
    assert roi.z == 0
    assert roi.left == 10
    assert roi.top == 20
    assert roi.right == 50
    assert roi.bottom == 80
    
    # Test that coordinates are clamped
    roi2 = acq_image.rois.create_roi(left=-10, top=-5, right=250, bottom=150, channel=1)
    assert roi2.left >= 0
    assert roi2.top >= 0
    assert roi2.right <= 200
    assert roi2.bottom <= 100
    
    logger.info("  - RoiSet.create_roi() works correctly with bounds validation")


def test_roiset_create_roi_3d() -> None:
    """Test RoiSet.create_roi() with 3D image."""
    logger.info("Testing RoiSet.create_roi() with 3D image")
    
    # Create 3D test image (10 slices, 100 lines, 200 pixels)
    test_image = np.zeros((10, 100, 200), dtype=np.uint8)
    acq_image = AcqImage(path=None, img_data=test_image)
    
    # Create ROI on slice 5
    roi = acq_image.rois.create_roi(left=10, top=20, right=50, bottom=80, channel=1, z=5)
    
    assert roi.z == 5
    
    # Test z clamping (z too high)
    roi2 = acq_image.rois.create_roi(left=10, top=20, right=50, bottom=80, channel=1, z=15)
    assert roi2.z == 9  # Clamped to num_slices-1
    
    # Test z clamping (z negative)
    roi3 = acq_image.rois.create_roi(left=10, top=20, right=50, bottom=80, channel=1, z=-1)
    assert roi3.z == 0  # Clamped to 0
    
    logger.info("  - RoiSet.create_roi() works correctly with 3D images")


def test_roiset_create_roi_2d_z_validation() -> None:
    """Test that z=0 is enforced for 2D images."""
    logger.info("Testing RoiSet.create_roi() z validation for 2D images")
    
    test_image = np.zeros((100, 200), dtype=np.uint8)
    acq_image = AcqImage(path=None, img_data=test_image)
    
    # Try to create ROI with z != 0 (should be clamped to 0)
    roi = acq_image.rois.create_roi(left=10, top=20, right=50, bottom=80, channel=1, z=5)
    assert roi.z == 0  # Clamped to 0 for 2D
    
    logger.info("  - z coordinate correctly clamped to 0 for 2D images")


def test_roiset_edit_roi() -> None:
    """Test RoiSet.edit_roi() with bounds validation."""
    logger.info("Testing RoiSet.edit_roi()")
    
    test_image = np.zeros((100, 200), dtype=np.uint8)
    acq_image = AcqImage(path=None, img_data=test_image)
    
    # Create ROI
    roi = acq_image.rois.create_roi(left=10, top=20, right=50, bottom=80, channel=1)
    
    # Edit coordinates
    acq_image.rois.edit_roi(roi.id, left=15, top=25)
    assert roi.left == 15
    assert roi.top == 25
    
    # Edit with out-of-bounds coordinates (should be clamped)
    acq_image.rois.edit_roi(roi.id, right=250, bottom=150)
    assert roi.right <= 200
    assert roi.bottom <= 100
    
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
    roi1 = acq_image.rois.create_roi(10, 10, 50, 50, channel=1)
    roi2 = acq_image.rois.create_roi(60, 60, 90, 90, channel=1)
    
    assert len(acq_image.rois) == 2
    
    # Get ROI
    retrieved = acq_image.rois.get(roi1.id)
    assert retrieved == roi1
    
    # Delete ROI
    acq_image.rois.delete(roi1.id)
    assert len(acq_image.rois) == 1
    assert acq_image.rois.get(roi1.id) is None
    assert acq_image.rois.get(roi2.id) is not None
    
    logger.info("  - RoiSet.delete() and get() work correctly")


def test_roiset_get_by_channel() -> None:
    """Test RoiSet.get_by_channel() filtering."""
    logger.info("Testing RoiSet.get_by_channel()")
    
    test_image = np.zeros((100, 200), dtype=np.uint8)
    acq_image = AcqImage(path=None, img_data=test_image)
    
    # Add channel 2
    acq_image.addColorChannel(2, np.zeros((100, 200), dtype=np.uint8))
    
    # Create ROIs in different channels
    roi1 = acq_image.rois.create_roi(10, 10, 50, 50, channel=1)
    roi2 = acq_image.rois.create_roi(60, 60, 90, 90, channel=1)
    roi3 = acq_image.rois.create_roi(20, 20, 40, 40, channel=2)
    
    # Filter by channel
    channel1_rois = acq_image.rois.get_by_channel(1)
    assert len(channel1_rois) == 2
    assert roi1 in channel1_rois
    assert roi2 in channel1_rois
    
    channel2_rois = acq_image.rois.get_by_channel(2)
    assert len(channel2_rois) == 1
    assert roi3 in channel2_rois
    
    logger.info("  - RoiSet.get_by_channel() works correctly")


def test_roiset_get_by_z() -> None:
    """Test RoiSet.get_by_z() filtering."""
    logger.info("Testing RoiSet.get_by_z()")
    
    # Create 3D test image
    test_image = np.zeros((10, 100, 200), dtype=np.uint8)
    acq_image = AcqImage(path=None, img_data=test_image)
    
    # Create ROIs on different z planes
    roi1 = acq_image.rois.create_roi(10, 10, 50, 50, channel=1, z=0)
    roi2 = acq_image.rois.create_roi(60, 60, 90, 90, channel=1, z=0)
    roi3 = acq_image.rois.create_roi(20, 20, 40, 40, channel=1, z=5)
    
    # Filter by z
    z0_rois = acq_image.rois.get_by_z(0)
    assert len(z0_rois) == 2
    assert roi1 in z0_rois
    assert roi2 in z0_rois
    
    z5_rois = acq_image.rois.get_by_z(5)
    assert len(z5_rois) == 1
    assert roi3 in z5_rois
    
    logger.info("  - RoiSet.get_by_z() works correctly")


def test_roiset_revalidate_all() -> None:
    """Test RoiSet.revalidate_all() utility method."""
    logger.info("Testing RoiSet.revalidate_all()")
    
    test_image = np.zeros((100, 200), dtype=np.uint8)
    acq_image = AcqImage(path=None, img_data=test_image)
    
    # Create ROIs (should be valid)
    roi1 = acq_image.rois.create_roi(10, 10, 50, 50, channel=1)
    roi2 = acq_image.rois.create_roi(60, 60, 90, 90, channel=1)
    
    # Manually set invalid coordinates (simulating corrupted data)
    roi1.left = -10
    roi1.right = 250
    
    # Revalidate
    clamped_count = acq_image.rois.revalidate_all()
    assert clamped_count > 0
    assert roi1.left >= 0
    assert roi1.right <= 200
    
    logger.info("  - RoiSet.revalidate_all() works correctly")


def test_roiset_invalid_channel() -> None:
    """Test that creating ROI with invalid channel raises error."""
    logger.info("Testing RoiSet with invalid channel")
    
    test_image = np.zeros((100, 200), dtype=np.uint8)
    acq_image = AcqImage(path=None, img_data=test_image)
    
    # Try to create ROI with non-existent channel
    with pytest.raises(ValueError, match="Channel.*does not exist"):
        acq_image.rois.create_roi(10, 10, 50, 50, channel=99)
    
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
        with pytest.raises(ValueError, match="Cannot determine image bounds"):
            acq_image.rois.create_roi(10, 10, 50, 50, channel=1)
    
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
        acq_image.rois.create_roi(10, 10, 50, 50, channel=1, name="ROI1")
        acq_image.rois.create_roi(60, 60, 90, 90, channel=1, name="ROI2")
        
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
        acq_image.rois.create_roi(10, 10, 50, 50, channel=1, name="ROI1")
        
        # Save
        acq_image.save_metadata()
        
        # Create new AcqImage and load
        acq_image2 = AcqImage(path=test_file, img_data=test_image)
        loaded = acq_image2.load_metadata()
        assert loaded is True
        
        # Verify loaded data
        assert acq_image2.header.voxels == [0.001, 0.284]
        assert acq_image2.experiment_metadata.species == "mouse"
        assert len(acq_image2.rois) == 1
        loaded_roi = acq_image2.rois.get(1)
        assert loaded_roi is not None
        assert loaded_roi.name == "ROI1"
        assert loaded_roi.left == 10
        
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
                    "left": -10,  # Out of bounds
                    "top": -5,   # Out of bounds
                    "right": 250,  # Out of bounds
                    "bottom": 150,  # Out of bounds
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
        assert roi.left >= 0
        assert roi.top >= 0
        assert roi.right <= 200
        assert roi.bottom <= 100
        
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
        acq_image.rois.create_roi(10, 10, 50, 50, channel=1, z=0, name="ROI1", note="note1")
        acq_image.rois.create_roi(60, 60, 90, 90, channel=2, z=0, name="ROI2", note="note2")
        
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
        
        assert len(acq_image2.rois) == 2
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
    roi1 = acq_image.rois.create_roi(10, 10, 50, 50, channel=1)
    roi2 = acq_image.rois.create_roi(60, 60, 90, 90, channel=1)
    roi3 = acq_image.rois.create_roi(20, 20, 40, 40, channel=1)
    
    # Iterate
    rois_list = list(acq_image.rois)
    assert len(rois_list) == 3
    assert roi1 in rois_list
    assert roi2 in rois_list
    assert roi3 in rois_list
    
    logger.info("  - RoiSet iteration works correctly")

