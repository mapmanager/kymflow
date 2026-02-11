"""Tests for VelocityEvent UUID lifecycle to ensure _uuid is never None during runtime."""

import numpy as np
from dataclasses import replace

from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.core.analysis.velocity_events.velocity_events import VelocityEvent
from kymflow.core.image_loaders.roi import RoiBounds


def test_velocity_event_uuid_after_detection() -> None:
    """Test that events have _uuid set after run_velocity_event_analysis()."""
    # Create test image
    test_image = np.zeros((100, 100), dtype=np.uint16)
    kym_image = KymImage(img_data=test_image, load_image=False)
    kym_image.update_header(shape=(100, 100), ndim=2, voxels=[0.001, 0.284])
    
    kym_analysis = kym_image.get_kym_analysis()
    
    # Add ROI
    bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
    roi = kym_image.rois.create_roi(bounds=bounds)
    
    # Run analysis to create some data
    kym_analysis.analyze_roi(roi.id, window_size=16, use_multiprocessing=False)
    
    # Run velocity event detection
    events = kym_analysis.run_velocity_event_analysis(roi.id)
    
    # Verify all returned events have UUIDs
    assert events is not None
    for event in events:
        assert hasattr(event, '_uuid'), f"Event missing _uuid attribute: {event}"
        assert event._uuid is not None, f"Event has _uuid=None: {event}"
        assert isinstance(event._uuid, str), f"Event._uuid is not a string: {type(event._uuid)}"
    
    # Also verify events retrieved via get_velocity_events() have UUIDs
    stored_events = kym_analysis.get_velocity_events(roi.id)
    assert stored_events is not None
    for event in stored_events:
        assert hasattr(event, '_uuid'), f"Stored event missing _uuid attribute: {event}"
        assert event._uuid is not None, f"Stored event has _uuid=None: {event}"


def test_velocity_event_uuid_after_get_velocity_events() -> None:
    """Test that events retrieved via get_velocity_events() have _uuid set."""
    test_image = np.zeros((100, 100), dtype=np.uint16)
    kym_image = KymImage(img_data=test_image, load_image=False)
    kym_image.update_header(shape=(100, 100), ndim=2, voxels=[0.001, 0.284])
    
    kym_analysis = kym_image.get_kym_analysis()
    
    bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
    roi = kym_image.rois.create_roi(bounds=bounds)
    
    kym_analysis.analyze_roi(roi.id, window_size=16, use_multiprocessing=False)
    kym_analysis.run_velocity_event_analysis(roi.id)
    
    # Retrieve events via get_velocity_events()
    events = kym_analysis.get_velocity_events(roi.id)
    
    assert events is not None
    for event in events:
        assert hasattr(event, '_uuid'), f"Event missing _uuid attribute: {event}"
        assert event._uuid is not None, f"Event has _uuid=None: {event}"


def test_velocity_event_uuid_after_find_event_by_uuid() -> None:
    """Test that events retrieved via find_event_by_uuid() have _uuid set."""
    test_image = np.zeros((100, 100), dtype=np.uint16)
    kym_image = KymImage(img_data=test_image, load_image=False)
    kym_image.update_header(shape=(100, 100), ndim=2, voxels=[0.001, 0.284])
    
    kym_analysis = kym_image.get_kym_analysis()
    
    bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
    roi = kym_image.rois.create_roi(bounds=bounds)
    
    # Add event directly (more reliable than detection for testing)
    event_id = kym_analysis.add_velocity_event(roi.id, t_start=0.5, t_end=1.0)
    assert event_id is not None
    
    # Get an event_id from the first event
    events = kym_analysis.get_velocity_events(roi.id)
    assert events is not None and len(events) > 0
    first_event = events[0]
    assert first_event._uuid is not None
    assert first_event._uuid == event_id
    
    # Find event by UUID
    result = kym_analysis.find_event_by_uuid(event_id)
    assert result is not None
    
    roi_id, index, event = result
    assert event._uuid is not None, f"Event from find_event_by_uuid() has _uuid=None: {event}"
    assert event._uuid == event_id, "UUID mismatch"


def test_velocity_event_uuid_after_add_velocity_event() -> None:
    """Test that events added via add_velocity_event() have _uuid set."""
    test_image = np.zeros((100, 100), dtype=np.uint16)
    kym_image = KymImage(img_data=test_image, load_image=False)
    kym_image.update_header(shape=(100, 100), ndim=2, voxels=[0.001, 0.284])
    
    kym_analysis = kym_image.get_kym_analysis()
    
    bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
    roi = kym_image.rois.create_roi(bounds=bounds)
    
    # Add event
    event_id = kym_analysis.add_velocity_event(roi.id, t_start=0.5, t_end=1.0)
    assert event_id is not None
    
    # Retrieve and verify UUID
    events = kym_analysis.get_velocity_events(roi.id)
    assert events is not None and len(events) > 0
    assert events[0]._uuid is not None
    assert events[0]._uuid == event_id


def test_velocity_event_uuid_after_update_velocity_event_field() -> None:
    """Test that events still have _uuid after update_velocity_event_field()."""
    test_image = np.zeros((100, 100), dtype=np.uint16)
    kym_image = KymImage(img_data=test_image, load_image=False)
    kym_image.update_header(shape=(100, 100), ndim=2, voxels=[0.001, 0.284])
    
    kym_analysis = kym_image.get_kym_analysis()
    
    bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
    roi = kym_image.rois.create_roi(bounds=bounds)
    
    # Add event
    event_id = kym_analysis.add_velocity_event(roi.id, t_start=0.5, t_end=1.0)
    
    # Update event field
    kym_analysis.update_velocity_event_field(event_id, "user_type", "true_stall")
    
    # Retrieve and verify UUID is preserved
    result = kym_analysis.find_event_by_uuid(event_id)
    assert result is not None
    roi_id, index, event = result
    assert event._uuid is not None, f"Event has _uuid=None after update: {event}"
    assert event._uuid == event_id, "UUID changed after update"


def test_velocity_event_uuid_after_replace_preserves_uuid() -> None:
    """Test that dataclasses.replace() preserves _uuid when explicitly passed."""
    # Create event with UUID
    event = VelocityEvent(
        event_type="baseline_drop",
        i_start=10,
        t_start=0.5,
    )
    object.__setattr__(event, '_uuid', "test-uuid-123")
    
    # Use replace() with _uuid explicitly passed
    new_event = replace(event, user_type="true_stall", _uuid=event._uuid)
    
    assert new_event._uuid is not None
    assert new_event._uuid == "test-uuid-123"
    assert new_event.user_type == "true_stall"


def test_velocity_event_uuid_after_replace_preserves_uuid_implicit() -> None:
    """Test that replace() preserves _uuid when set via object.__setattr__().
    
    Note: replace() on frozen dataclasses DOES preserve fields set via object.__setattr__().
    This is the expected behavior - we don't need to explicitly pass _uuid to replace().
    """
    # Create event with UUID
    event = VelocityEvent(
        event_type="baseline_drop",
        i_start=10,
        t_start=0.5,
    )
    object.__setattr__(event, '_uuid', "test-uuid-123")
    
    # Use replace() WITHOUT _uuid - it should preserve it
    new_event = replace(event, user_type="true_stall")
    
    # replace() preserves _uuid when set via object.__setattr__()
    assert new_event._uuid is not None
    assert new_event._uuid == "test-uuid-123"
    assert new_event.user_type == "true_stall"


def test_find_event_by_uuid_after_reorder() -> None:
    """Ensure find_event_by_uuid works correctly after events are reordered by t_start."""
    test_image = np.zeros((100, 100), dtype=np.uint16)
    kym_image = KymImage(img_data=test_image, load_image=False)
    kym_image.update_header(shape=(100, 100), ndim=2, voxels=[0.001, 0.284])

    kym_analysis = kym_image.get_kym_analysis()

    bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
    roi = kym_image.rois.create_roi(bounds=bounds)

    # Add two events with different t_start (order will be normalized by sort)
    event_id1 = kym_analysis.add_velocity_event(roi.id, t_start=5.0, t_end=6.0)
    event_id2 = kym_analysis.add_velocity_event(roi.id, t_start=1.0, t_end=2.0)

    # After sorting by t_start, event2 should come before event1 in the list,
    # but find_event_by_uuid must still find the correct event by UUID.
    result1 = kym_analysis.find_event_by_uuid(event_id1)
    result2 = kym_analysis.find_event_by_uuid(event_id2)

    assert result1 is not None
    assert result2 is not None

    roi_id1, idx1, ev1 = result1
    roi_id2, idx2, ev2 = result2

    assert roi_id1 == roi.id
    assert roi_id2 == roi.id
    assert ev1._uuid == event_id1
    assert ev2._uuid == event_id2

    # Ensure ordering by t_start is as expected
    events = kym_analysis.get_velocity_events(roi.id)
    assert events is not None
    assert [e.t_start for e in events] == sorted(e.t_start for e in events)


def test_velocity_event_uuid_after_load_analysis() -> None:
    """Test that events loaded from disk via load_analysis() have _uuid set correctly.
    
    This verifies that when events are loaded from JSON (which doesn't include _uuid),
    KymAnalysis assigns UUIDs and they are available via get_velocity_events().
    """
    import tempfile
    from pathlib import Path
    
    # Create test image with path (required for save/load)
    test_image = np.zeros((100, 100), dtype=np.uint16)
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir) / "test.tif"
        kym_image = KymImage(img_data=test_image, load_image=False, path=tmp_path)
        kym_image.update_header(shape=(100, 100), ndim=2, voxels=[0.001, 0.284])
        
        kym_analysis = kym_image.get_kym_analysis()
        
        # Add ROI
        bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
        roi = kym_image.rois.create_roi(bounds=bounds)
        
        # Run analysis and create events
        kym_analysis.analyze_roi(roi.id, window_size=16, use_multiprocessing=False)
        # Add event directly (more reliable than detection for testing)
        kym_analysis.add_velocity_event(roi.id, t_start=0.5, t_end=1.0)
        
        # Save metadata (ROIs) and analysis to disk
        kym_image.save_metadata()
        kym_analysis.save_analysis()
        
        # Create new KymImage and KymAnalysis (simulates loading from disk)
        kym_image2 = KymImage(img_data=test_image, load_image=False, path=tmp_path)
        kym_image2.update_header(shape=(100, 100), ndim=2, voxels=[0.001, 0.284])
        
        # Load metadata first (this loads ROIs)
        kym_image2.load_metadata()
        # Now access kymanalysis - it will auto-load analysis and reconcile to loaded ROIs
        kym_analysis2 = kym_image2.get_kym_analysis()
        
        # Get the loaded ROI (should have same ID as original)
        roi_ids = kym_image2.rois.get_roi_ids()
        assert len(roi_ids) == 1
        roi2_id = roi_ids[0]
        
        # Verify events loaded from disk have UUIDs
        events = kym_analysis2.get_velocity_events(roi2_id)
        assert events is not None and len(events) > 0
        for event in events:
            assert hasattr(event, '_uuid'), f"Loaded event missing _uuid attribute: {event}"
            assert event._uuid is not None, f"Loaded event has _uuid=None: {event}"
            assert isinstance(event._uuid, str), f"Loaded event._uuid is not a string: {type(event._uuid)}"
        
        # No separate UUID mapping anymore; event._uuid is the single source of truth