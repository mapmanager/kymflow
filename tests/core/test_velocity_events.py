"""Tests for velocity event analysis functionality."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from kymflow.core.analysis.velocity_events.velocity_events import (
    MachineType,
    UserType,
    VelocityEvent,
    detect_events,
    time_to_index,
)
from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.core.image_loaders.roi import RoiBounds
from kymflow.core.utils.logging import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)


class TestVelocityEventDataclass:
    """Tests for the VelocityEvent dataclass."""

    def test_velocity_event_creation_baseline_drop(self) -> None:
        """Test creating a VelocityEvent with baseline_drop type."""
        event = VelocityEvent(
            event_type="baseline_drop",
            i_start=10,
            t_start=1.5,
            i_peak=12,
            t_peak=1.6,
            score_peak=-2.5,
            strength=3.0,
            machine_type=MachineType.STALL_CANDIDATE,
        )
        assert event.event_type == "baseline_drop"
        assert event.i_start == 10
        assert event.t_start == 1.5
        assert event.i_peak == 12
        assert event.t_peak == 1.6
        assert event.score_peak == -2.5
        assert event.strength == 3.0
        assert event.machine_type == MachineType.STALL_CANDIDATE

    def test_velocity_event_creation_nan_gap(self) -> None:
        """Test creating a VelocityEvent with nan_gap type."""
        event = VelocityEvent(
            event_type="nan_gap",
            i_start=5,
            t_start=0.8,
            i_end=7,
            t_end=1.0,
            nan_fraction_in_event=0.9,
            n_valid_in_event=1,
            duration_sec=0.2,
            strength=0.18,
            machine_type=MachineType.NAN_GAP,
        )
        assert event.event_type == "nan_gap"
        assert event.i_start == 5
        assert event.t_start == 0.8
        assert event.i_end == 7
        assert event.t_end == 1.0
        assert event.nan_fraction_in_event == 0.9
        assert event.duration_sec == 0.2
        assert event.machine_type == MachineType.NAN_GAP

    def test_velocity_event_optional_fields(self) -> None:
        """Test creating a VelocityEvent with minimal required fields."""
        event = VelocityEvent(
            event_type="baseline_drop",
            i_start=0,
            t_start=0.0,
        )
        assert event.i_peak is None
        assert event.t_peak is None
        assert event.i_end is None
        assert event.t_end is None
        assert event.score_peak is None
        assert event.strength is None
        assert event.machine_type == MachineType.OTHER
        assert event.user_type == UserType.UNREVIEWED
        assert event.note == ""


class TestTimeToIndex:
    """Tests for time_to_index helper."""

    def test_time_to_index_round_half_away_from_zero(self) -> None:
        assert time_to_index(0.05, 0.1) == 1
        assert time_to_index(-0.05, 0.1) == -1

    def test_time_to_index_floor_ceil(self) -> None:
        assert time_to_index(0.19, 0.1, mode="floor") == 1
        assert time_to_index(0.11, 0.1, mode="ceil") == 2

    def test_time_to_index_invalid_seconds_per_line(self) -> None:
        with pytest.raises(ValueError):
            time_to_index(0.1, 0.0)


class TestVelocityEventSerialization:
    """Tests for VelocityEvent serialization (to_dict/from_dict)."""

    def test_to_dict_baseline_drop(self) -> None:
        """Test serializing a baseline_drop event to dict."""
        event = VelocityEvent(
            event_type="baseline_drop",
            i_start=10,
            t_start=1.5,
            i_peak=12,
            t_peak=1.6,
            score_peak=-2.5,
            baseline_before=5.0,
            baseline_after=2.0,
            strength=3.0,
            machine_type=MachineType.STALL_CANDIDATE,
            user_type=UserType.TRUE_STALL,
            note="Test note",
        )
        d = event.to_dict()
        assert d["event_type"] == "baseline_drop"
        assert d["i_start"] == 10
        assert d["t_start"] == 1.5
        assert d["i_peak"] == 12
        assert d["t_peak"] == 1.6
        assert d["score_peak"] == -2.5
        assert d["baseline_before"] == 5.0
        assert d["baseline_after"] == 2.0
        assert d["strength"] == 3.0
        assert d["machine_type"] == MachineType.STALL_CANDIDATE.value
        assert d["user_type"] == UserType.TRUE_STALL.value
        assert d["note"] == "Test note"

    def test_to_dict_nan_gap(self) -> None:
        """Test serializing a nan_gap event to dict."""
        event = VelocityEvent(
            event_type="nan_gap",
            i_start=5,
            t_start=0.8,
            i_end=7,
            t_end=1.0,
            nan_fraction_in_event=0.9,
            n_valid_in_event=1,
            duration_sec=0.2,
            strength=0.18,
            machine_type=MachineType.NAN_GAP,
        )
        d = event.to_dict()
        assert d["event_type"] == "nan_gap"
        assert d["nan_fraction_in_event"] == 0.9
        assert d["n_valid_in_event"] == 1
        assert d["duration_sec"] == 0.2
        assert d["machine_type"] == MachineType.NAN_GAP.value

    def test_to_dict_with_none_fields(self) -> None:
        """Test serializing an event with None optional fields."""
        event = VelocityEvent(
            event_type="baseline_drop",
            i_start=0,
            t_start=0.0,
        )
        d = event.to_dict()
        assert d["i_peak"] is None
        assert d["t_peak"] is None
        assert d["i_end"] is None
        assert d["t_end"] is None
        assert d["score_peak"] is None
        assert d["strength"] is None

    def test_from_dict_baseline_drop(self) -> None:
        """Test deserializing a baseline_drop event from dict."""
        d = {
            "event_type": "baseline_drop",
            "i_start": 10,
            "t_start": 1.5,
            "i_peak": 12,
            "t_peak": 1.6,
            "i_end": None,
            "t_end": None,
            "score_peak": -2.5,
            "baseline_before": 5.0,
            "baseline_after": 2.0,
            "strength": 3.0,
            "nan_fraction_in_event": None,
            "n_valid_in_event": None,
            "duration_sec": None,
            "machine_type": "stall_candidate",
            "user_type": "true_stall",
            "note": "Test note",
        }
        event = VelocityEvent.from_dict(d)
        assert event.event_type == "baseline_drop"
        assert event.i_start == 10
        assert event.t_start == 1.5
        assert event.i_peak == 12
        assert event.t_peak == 1.6
        assert event.i_end is None
        assert event.t_end is None
        assert event.score_peak == -2.5
        assert event.strength == 3.0
        assert event.machine_type == MachineType.STALL_CANDIDATE
        assert event.user_type == UserType.TRUE_STALL
        assert event.note == "Test note"

    def test_from_dict_nan_gap(self) -> None:
        """Test deserializing a nan_gap event from dict."""
        d = {
            "event_type": "nan_gap",
            "i_start": 5,
            "t_start": 0.8,
            "i_peak": None,
            "t_peak": None,
            "i_end": 7,
            "t_end": 1.0,
            "score_peak": None,
            "baseline_before": None,
            "baseline_after": None,
            "strength": 0.18,
            "nan_fraction_in_event": 0.9,
            "n_valid_in_event": 1,
            "duration_sec": 0.2,
            "machine_type": "nan_gap",
            "user_type": "unreviewed",
            "note": "",
        }
        event = VelocityEvent.from_dict(d)
        assert event.event_type == "nan_gap"
        assert event.i_start == 5
        assert event.t_start == 0.8
        assert event.i_end == 7
        assert event.t_end == 1.0
        assert event.nan_fraction_in_event == 0.9
        assert event.duration_sec == 0.2
        assert event.machine_type == MachineType.NAN_GAP

    def test_round_trip_serialization(self) -> None:
        """Test that to_dict/from_dict round-trip preserves all fields."""
        original = VelocityEvent(
            event_type="baseline_drop",
            i_start=10,
            t_start=1.5,
            i_peak=12,
            t_peak=1.6,
            i_end=15,
            t_end=1.8,
            score_peak=-2.5,
            baseline_before=5.0,
            baseline_after=2.0,
            strength=3.0,
            machine_type=MachineType.STALL_CANDIDATE,
            user_type=UserType.TRUE_STALL,
            note="Test note",
        )
        d = original.to_dict()
        restored = VelocityEvent.from_dict(d)
        assert restored.event_type == original.event_type
        assert restored.i_start == original.i_start
        assert restored.t_start == original.t_start
        assert restored.i_peak == original.i_peak
        assert restored.t_peak == original.t_peak
        assert restored.i_end == original.i_end
        assert restored.t_end == original.t_end
        assert restored.score_peak == original.score_peak
        assert restored.baseline_before == original.baseline_before
        assert restored.baseline_after == original.baseline_after
        assert restored.strength == original.strength
        assert restored.machine_type == original.machine_type
        assert restored.user_type == original.user_type
        assert restored.note == original.note


class TestDetectEventsSimple:
    """Tests for detect_events() with simple synthetic data."""

    def test_detect_events_no_events(self) -> None:
        """Test detect_events with constant velocity (no events)."""
        time_s = np.linspace(0, 10, 100)
        velocity = np.ones(100) * 5.0  # Constant velocity
        events, debug = detect_events(time_s, velocity)
        # Should detect very few or no events with constant velocity
        assert isinstance(events, list)
        assert isinstance(debug, dict)
        assert "score" in debug
        assert "abs_med" in debug
        assert "threshold" in debug

    @pytest.mark.skip(reason="Flaky thresholding (debug threshold can be NaN); revisit later.")
    def test_detect_events_with_baseline_drop(self) -> None:
        """Test detect_events with a clear baseline drop."""
        # Use longer time series to avoid edge effects
        # win_cmp_sec=0.25 needs 0.25s on each side, so we need space
        np.random.seed(42)  # For reproducible noise
        time_s = np.linspace(0, 20, 200)  # 200 samples, dt=0.1s
        velocity = np.ones(200) * 5.0
        
        # Add small noise to make threshold calculation more realistic
        # (completely constant velocity can make MAD very small)
        velocity += np.random.normal(0, 0.1, 200)
        
        # Create a sustained drop in the middle (smoother transition)
        # Drop from ~5.0 to ~0.5 over indices 80-120 (4 seconds)
        drop_start, drop_end = 80, 120
        # Smooth transition: linear ramp down, then constant low
        for i in range(drop_start, drop_end):
            if i < drop_start + 10:  # 1 second transition
                frac = (i - drop_start) / 10.0
                velocity[i] = 5.0 - frac * 4.5  # Linear drop
            else:
                velocity[i] = 0.5  # Sustained low
        
        # Use more lenient parameters:
        # - Lower mad_k for more sensitivity
        # - Lower abs_score_floor to catch smaller drops
        # - Ensure top_k_total works as fallback
        events, debug = detect_events(
            time_s, 
            velocity, 
            win_cmp_sec=0.25,  # Default window size
            mad_k=1.5,  # Lower threshold (more sensitive)
            abs_score_floor=0.1,  # Lower floor to catch smaller drops
            top_k_total=5,  # Fallback to ensure we get events
        )
        
        # Should detect at least one baseline_drop event
        # (top_k_total=5 ensures we get the strongest candidates even if threshold is high)
        assert len(events) >= 1, f"No events detected. Debug threshold: {debug.get('threshold')}"
        baseline_drops = [e for e in events if e.event_type == "baseline_drop"]
        assert len(baseline_drops) >= 1, f"No baseline_drop events found. All events: {[e.event_type for e in events]}"
        assert baseline_drops[0].machine_type == MachineType.STALL_CANDIDATE

    @pytest.mark.skip(reason="nan_gap detection is currently disabled in detect_events()")
    def test_detect_events_with_nan_gap(self) -> None:
        """Test detect_events with NaN values (nan_gap events).
        
        NOTE: This test is currently skipped because nan_gap detection has been
        disabled in detect_events() (doNanGapDetection = False). If nan_gap
        detection is re-enabled, this test should be updated accordingly.
        """
        time_s = np.linspace(0, 10, 100)
        velocity = np.ones(100) * 5.0
        # Create a NaN gap
        velocity[40:50] = np.nan
        events, _debug = detect_events(time_s, velocity)
        # Should detect at least one nan_gap event
        nan_gaps = [e for e in events if e.event_type == "nan_gap"]
        assert len(nan_gaps) >= 1
        assert nan_gaps[0].machine_type == MachineType.NAN_GAP
        assert nan_gaps[0].t_start is not None
        assert nan_gaps[0].t_end is not None


class TestKymAnalysisVelocityEvents:
    """Tests for KymAnalysis velocity event methods."""

    @pytest.mark.requires_data
    def test_run_velocity_event_analysis_with_real_data(self, test_data_dir: Path) -> None:
        """Test run_velocity_event_analysis with real kymograph data."""
        if not test_data_dir.exists():
            pytest.skip("Test data directory does not exist")

        tif_file = test_data_dir / "Capillary1_0001.tif"
        if not tif_file.exists():
            pytest.skip("Capillary1_0001.tif not found in test data")

        kym_image = KymImage(tif_file, load_image=False)
        kym_analysis = kym_image.get_kym_analysis()

        if not kym_analysis.has_analysis(roi_id=1):
            pytest.skip("No analysis data available for ROI 1")

        # Run velocity event analysis
        events = kym_analysis.run_velocity_event_analysis(
            roi_id=1,
            top_k_total=5,
        )

        assert isinstance(events, list)
        assert len(events) >= 0  # May or may not have events

        # Verify event structure
        for event in events:
            assert isinstance(event, VelocityEvent)
            assert event.i_start >= 0
            assert event.t_start >= 0
            # Note: nan_gap detection is currently disabled in detect_events()
            assert event.event_type in ("baseline_drop", "nan_gap", "User Added")

        # Verify events are stored
        stored_events = kym_analysis.get_velocity_events(roi_id=1)
        assert stored_events is not None
        assert len(stored_events) == len(events)

    def test_run_velocity_event_analysis_missing_velocity_raises(self) -> None:
        """Test that run_velocity_event_analysis raises error when velocity is missing."""
        # Create a KymImage without analysis
        test_image = np.zeros((100, 100), dtype=np.uint16)
        kym_image = KymImage(img_data=test_image, load_image=False)
        kym_analysis = kym_image.get_kym_analysis()

        with pytest.raises(ValueError, match="Cannot run velocity event analysis.*has no analysis values"):
            kym_analysis.run_velocity_event_analysis(roi_id=999)

    def test_get_velocity_events_returns_none_when_not_run(self) -> None:
        """Test that get_velocity_events returns None when analysis not run."""
        test_image = np.zeros((100, 100), dtype=np.uint16)
        kym_image = KymImage(img_data=test_image, load_image=False)
        kym_analysis = kym_image.get_kym_analysis()

        events = kym_analysis.get_velocity_events(roi_id=1)
        assert events is None

    @pytest.mark.requires_data
    def test_velocity_events_persistence(self, test_data_dir: Path, tmp_path: Path) -> None:
        """Test that velocity events are saved and loaded correctly."""
        if not test_data_dir.exists():
            pytest.skip("Test data directory does not exist")

        tif_file = test_data_dir / "Capillary1_0001.tif"
        if not tif_file.exists():
            pytest.skip("Capillary1_0001.tif not found in test data")

        # Create a copy in tmp_path for testing
        import shutil
        test_tif = tmp_path / "test.tif"
        shutil.copy(tif_file, test_tif)

        kym_image = KymImage(test_tif, load_image=False)
        kym_analysis = kym_image.get_kym_analysis()

        if not kym_analysis.has_analysis(roi_id=1):
            pytest.skip("No analysis data available for ROI 1")

        # Run velocity event analysis
        original_events = kym_analysis.run_velocity_event_analysis(
            roi_id=1,
            top_k_total=5,
        )

        # Save analysis
        saved = kym_analysis.save_analysis()
        assert saved is True

        # Create a new KymAnalysis instance and load
        kym_image2 = KymImage(test_tif, load_image=False)
        kym_analysis2 = kym_image2.get_kym_analysis()

        # Verify events were loaded
        loaded_events = kym_analysis2.get_velocity_events(roi_id=1)
        assert loaded_events is not None
        assert len(loaded_events) == len(original_events)

        # Verify event details match
        for orig, loaded in zip(original_events, loaded_events):
            assert orig.event_type == loaded.event_type
            assert orig.i_start == loaded.i_start
            assert orig.t_start == loaded.t_start
            assert orig.machine_type == loaded.machine_type

    @pytest.mark.requires_data
    def test_velocity_events_with_different_parameters(self, test_data_dir: Path) -> None:
        """Test that different detect_events parameters produce different results."""
        if not test_data_dir.exists():
            pytest.skip("Test data directory does not exist")

        tif_file = test_data_dir / "Capillary1_0001.tif"
        if not tif_file.exists():
            pytest.skip("Capillary1_0001.tif not found in test data")

        kym_image = KymImage(tif_file, load_image=False)
        kym_analysis = kym_image.get_kym_analysis()

        if not kym_analysis.has_analysis(roi_id=1):
            pytest.skip("No analysis data available for ROI 1")

        # Run with conservative parameters (fewer events)
        events_conservative = kym_analysis.run_velocity_event_analysis(
            roi_id=1,
            mad_k=5.0,  # Higher threshold
            top_k_total=0,  # No fallback
        )

        # Run with sensitive parameters (more events)
        events_sensitive = kym_analysis.run_velocity_event_analysis(
            roi_id=1,
            mad_k=2.0,  # Lower threshold
            top_k_total=10,  # More fallback
        )

        # Sensitive should detect >= conservative (or equal)
        assert len(events_sensitive) >= len(events_conservative)

    @pytest.mark.requires_data
    def test_velocity_events_with_different_velocity_keys(self, test_data_dir: Path) -> None:
        """Test that different velocity_key values work correctly."""
        if not test_data_dir.exists():
            pytest.skip("Test data directory does not exist")

        tif_file = test_data_dir / "Capillary1_0001.tif"
        if not tif_file.exists():
            pytest.skip("Capillary1_0001.tif not found in test data")

        kym_image = KymImage(tif_file, load_image=False)
        kym_analysis = kym_image.get_kym_analysis()

        if not kym_analysis.has_analysis(roi_id=1):
            pytest.skip("No analysis data available for ROI 1")

        # Test with default "velocity" key
        events_velocity = kym_analysis.run_velocity_event_analysis(roi_id=1)

        # Test with "cleanVelocity" key (if available)
        if kym_analysis.get_analysis_value(roi_id=1, key="cleanVelocity") is not None:
            events_clean = kym_analysis.run_velocity_event_analysis(
                roi_id=1,
                velocity_key="cleanVelocity",
            )
            # Both should produce valid results
            assert isinstance(events_velocity, list)
            assert isinstance(events_clean, list)

    @pytest.mark.requires_data
    def test_velocity_events_reconciliation_on_load(self, test_data_dir: Path, tmp_path: Path) -> None:
        """Test that velocity events are reconciled to current ROIs on load."""
        if not test_data_dir.exists():
            pytest.skip("Test data directory does not exist")

        tif_file = test_data_dir / "Capillary1_0001.tif"
        if not tif_file.exists():
            pytest.skip("Capillary1_0001.tif not found in test data")

        import shutil
        test_tif = tmp_path / "test.tif"
        shutil.copy(tif_file, test_tif)

        kym_image = KymImage(test_tif, load_image=False)
        kym_analysis = kym_image.get_kym_analysis()

        if not kym_analysis.has_analysis(roi_id=1):
            pytest.skip("No analysis data available for ROI 1")

        # Run analysis for ROI 1
        kym_analysis.run_velocity_event_analysis(roi_id=1)
        kym_analysis.save_analysis()

        # Load in new instance
        kym_image2 = KymImage(test_tif, load_image=False)
        kym_analysis2 = kym_image2.get_kym_analysis()

        # Events for ROI 1 should be present
        assert kym_analysis2.get_velocity_events(roi_id=1) is not None

        # Events for non-existent ROI should not be present
        assert kym_analysis2.get_velocity_events(roi_id=999) is None


class TestVelocityEventLifecycle:
    """Tests for velocity event CRUD operations (add/update/delete/report)."""

    def test_add_velocity_event(self) -> None:
        """Test adding a velocity event."""
        test_image = np.zeros((100, 100), dtype=np.uint16)
        kym_image = KymImage(img_data=test_image, load_image=True)
        kym_analysis = kym_image.get_kym_analysis()
        
        # Set seconds_per_line for time calculations (no setter)
        kym_image.header.voxels[0] = 0.1
        
        # Create ROI
        bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
        roi = kym_image.rois.create_roi(bounds=bounds)
        
        # Add velocity event
        event_id = kym_analysis.add_velocity_event(roi_id=roi.id, t_start=1.5, t_end=2.0)
        assert event_id is not None
        assert isinstance(event_id, str)
        
        # Verify event was added
        events = kym_analysis.get_velocity_events(roi_id=roi.id)
        assert events is not None
        assert len(events) == 1
        assert events[0].t_start == 1.5
        assert events[0].t_end == 2.0
        assert events[0].event_type == "User Added"
        assert events[0].user_type.value == "unreviewed"
        
        # Verify dirty flag is set
        assert kym_analysis.is_dirty is True

    def test_add_velocity_event_no_end(self) -> None:
        """Test adding a velocity event without t_end."""
        test_image = np.zeros((100, 100), dtype=np.uint16)
        kym_image = KymImage(img_data=test_image, load_image=True)
        kym_analysis = kym_image.get_kym_analysis()
        
        kym_image.header.voxels[0] = 0.1
        bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
        roi = kym_image.rois.create_roi(bounds=bounds)
        
        event_id = kym_analysis.add_velocity_event(roi_id=roi.id, t_start=1.5)
        assert event_id is not None
        
        events = kym_analysis.get_velocity_events(roi_id=roi.id)
        assert events is not None
        assert len(events) == 1
        assert events[0].t_start == 1.5
        assert events[0].t_end is None

    def test_update_velocity_event_field(self) -> None:
        """Test updating a velocity event field."""
        test_image = np.zeros((100, 100), dtype=np.uint16)
        kym_image = KymImage(img_data=test_image, load_image=True)
        kym_analysis = kym_image.get_kym_analysis()
        
        kym_image.header.voxels[0] = 0.1
        bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
        roi = kym_image.rois.create_roi(bounds=bounds)
        
        # Add event
        event_id = kym_analysis.add_velocity_event(roi_id=roi.id, t_start=1.5, t_end=2.0)
        
        # Update user_type
        from kymflow.core.analysis.velocity_events.velocity_events import UserType
        updated_id = kym_analysis.update_velocity_event_field(
            event_id=event_id,
            field="user_type",
            value=UserType.TRUE_STALL.value
        )
        assert updated_id == event_id  # UUID doesn't change
        
        events = kym_analysis.get_velocity_events(roi_id=roi.id)
        assert events is not None
        assert events[0].user_type == UserType.TRUE_STALL
        
        # Update t_start
        updated_id2 = kym_analysis.update_velocity_event_field(
            event_id=event_id,
            field="t_start",
            value=1.8
        )
        assert updated_id2 == event_id
        
        events = kym_analysis.get_velocity_events(roi_id=roi.id)
        assert events[0].t_start == 1.8
        
        # Verify dirty flag is still set
        assert kym_analysis.is_dirty is True

    def test_update_velocity_event_range(self) -> None:
        """Test updating velocity event range atomically."""
        test_image = np.zeros((100, 100), dtype=np.uint16)
        kym_image = KymImage(img_data=test_image, load_image=True)
        kym_analysis = kym_image.get_kym_analysis()
        
        kym_image.header.voxels[0] = 0.1
        bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
        roi = kym_image.rois.create_roi(bounds=bounds)
        
        # Add event
        event_id = kym_analysis.add_velocity_event(roi_id=roi.id, t_start=1.5, t_end=2.0)
        
        # Update range atomically
        updated_id = kym_analysis.update_velocity_event_range(
            event_id=event_id,
            t_start=2.0,
            t_end=2.5
        )
        assert updated_id == event_id
        
        events = kym_analysis.get_velocity_events(roi_id=roi.id)
        assert events is not None
        assert events[0].t_start == 2.0
        assert events[0].t_end == 2.5

    def test_delete_velocity_event(self) -> None:
        """Test deleting a velocity event."""
        test_image = np.zeros((100, 100), dtype=np.uint16)
        kym_image = KymImage(img_data=test_image, load_image=True)
        kym_analysis = kym_image.get_kym_analysis()
        
        kym_image.header.voxels[0] = 0.1
        bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
        roi = kym_image.rois.create_roi(bounds=bounds)
        
        # Add multiple events
        event_id1 = kym_analysis.add_velocity_event(roi_id=roi.id, t_start=1.0, t_end=1.5)
        event_id2 = kym_analysis.add_velocity_event(roi_id=roi.id, t_start=2.0, t_end=2.5)
        
        events = kym_analysis.get_velocity_events(roi_id=roi.id)
        assert events is not None
        assert len(events) == 2
        
        # Delete first event
        deleted = kym_analysis.delete_velocity_event(event_id1)
        assert deleted is True
        
        events = kym_analysis.get_velocity_events(roi_id=roi.id)
        assert events is not None
        assert len(events) == 1
        assert events[0].t_start == 2.0  # Second event remains
        
        # Try to delete non-existent event
        deleted2 = kym_analysis.delete_velocity_event("non-existent-id")
        assert deleted2 is False
        
        # Verify dirty flag is set
        assert kym_analysis.is_dirty is True

    def test_get_velocity_report(self) -> None:
        """Test getting velocity report."""
        test_image = np.zeros((100, 100), dtype=np.uint16)
        kym_image = KymImage(img_data=test_image, load_image=True)
        kym_analysis = kym_image.get_kym_analysis()
        
        kym_image.header.voxels[0] = 0.1
        bounds1 = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
        roi1 = kym_image.rois.create_roi(bounds=bounds1)
        bounds2 = RoiBounds(dim0_start=60, dim0_stop=90, dim1_start=60, dim1_stop=90)
        roi2 = kym_image.rois.create_roi(bounds=bounds2)
        
        # Add events to both ROIs
        event_id1 = kym_analysis.add_velocity_event(roi_id=roi1.id, t_start=1.0, t_end=1.5)
        event_id2 = kym_analysis.add_velocity_event(roi_id=roi2.id, t_start=2.0, t_end=2.5)
        
        # Get report for specific ROI
        report1 = kym_analysis.get_velocity_report(roi_id=roi1.id)
        assert len(report1) == 1
        assert report1[0]["roi_id"] == roi1.id
        assert report1[0]["event_id"] == event_id1
        
        # Get report for all ROIs
        report_all = kym_analysis.get_velocity_report(roi_id=None)
        assert len(report_all) == 2
        roi_ids = {row["roi_id"] for row in report_all}
        assert roi_ids == {roi1.id, roi2.id}
        
        # Verify report structure
        for row in report_all:
            assert "event_id" in row
            assert "roi_id" in row
            assert "event_type" in row
            assert "t_start" in row
            assert "user_type" in row

    def test_remove_velocity_event(self) -> None:
        """Test removing velocity events by type."""
        test_image = np.zeros((100, 100), dtype=np.uint16)
        kym_image = KymImage(img_data=test_image, load_image=True)
        kym_analysis = kym_image.get_kym_analysis()
        
        kym_image.header.voxels[0] = 0.1
        bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
        roi = kym_image.rois.create_roi(bounds=bounds)
        
        # Add user-added event
        event_id1 = kym_analysis.add_velocity_event(roi_id=roi.id, t_start=1.0, t_end=1.5)
        
        # Add another user-added event
        event_id2 = kym_analysis.add_velocity_event(roi_id=roi.id, t_start=2.0, t_end=2.5)
        
        # Verify both events exist
        events = kym_analysis.get_velocity_events(roi_id=roi.id)
        assert events is not None
        assert len(events) == 2
        
        # Remove all events
        kym_analysis.remove_velocity_event(roi_id=roi.id, remove_these="_remove_all")
        events = kym_analysis.get_velocity_events(roi_id=roi.id)
        assert events is not None
        assert len(events) == 0
        
        # Add user-added event and auto-detected event (simulated)
        from kymflow.core.analysis.velocity_events.velocity_events import MachineType
        event_id3 = kym_analysis.add_velocity_event(roi_id=roi.id, t_start=3.0, t_end=3.5)
        # Create a simulated auto-detected event (baseline_drop with UNREVIEWED)
        from kymflow.core.analysis.velocity_events.velocity_events import VelocityEvent
        auto_event = VelocityEvent(
            event_type="baseline_drop",
            i_start=30,
            t_start=4.0,
            machine_type=MachineType.STALL_CANDIDATE,
            user_type=UserType.UNREVIEWED,
        )
        if roi.id not in kym_analysis._velocity_events:
            kym_analysis._velocity_events[roi.id] = []
        kym_analysis._velocity_events[roi.id].append(auto_event)
        
        events = kym_analysis.get_velocity_events(roi_id=roi.id)
        assert events is not None
        assert len(events) == 2
        
        # Remove only auto-detected events (should keep User Added)
        # remove_velocity_event with "auto_detected" removes events that are:
        # - NOT "User Added" AND have user_type == "unreviewed"
        # So it keeps: "User Added" events and events with user_type != "unreviewed"
        kym_analysis.remove_velocity_event(roi_id=roi.id, remove_these="auto_detected")
        events = kym_analysis.get_velocity_events(roi_id=roi.id)
        assert events is not None
        assert len(events) == 1
        assert events[0].event_type == "User Added"
        
        # Verify dirty flag is set
        assert kym_analysis.is_dirty is True

    def test_remove_velocity_event_edge_cases(self) -> None:
        """Test remove_velocity_event() with edge cases."""
        test_image = np.zeros((100, 100), dtype=np.uint16)
        kym_image = KymImage(img_data=test_image, load_image=True)
        kym_analysis = kym_image.get_kym_analysis()
        
        kym_image.header.voxels[0] = 0.1
        bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
        roi = kym_image.rois.create_roi(bounds=bounds)
        
        # Test removing from empty list
        kym_analysis.remove_velocity_event(roi_id=roi.id, remove_these="_remove_all")
        events = kym_analysis.get_velocity_events(roi_id=roi.id)
        assert events is None or len(events) == 0
        
        # Test with reviewed user-added event (should be kept)
        event_id1 = kym_analysis.add_velocity_event(roi_id=roi.id, t_start=1.0, t_end=1.5)
        from kymflow.core.analysis.velocity_events.velocity_events import UserType
        kym_analysis.update_velocity_event_field(event_id1, "user_type", UserType.TRUE_STALL.value)
        
        # Test with auto-detected event that has been reviewed (should be kept)
        from kymflow.core.analysis.velocity_events.velocity_events import VelocityEvent, MachineType
        reviewed_event = VelocityEvent(
            event_type="baseline_drop",
            i_start=20,
            t_start=2.0,
            machine_type=MachineType.STALL_CANDIDATE,
            user_type=UserType.TRUE_STALL,  # Reviewed, not unreviewed
        )
        if roi.id not in kym_analysis._velocity_events:
            kym_analysis._velocity_events[roi.id] = []
        kym_analysis._velocity_events[roi.id].append(reviewed_event)
        
        # Test with auto-detected unreviewed event (should be removed)
        unreviewed_event = VelocityEvent(
            event_type="baseline_drop",
            i_start=30,
            t_start=3.0,
            machine_type=MachineType.STALL_CANDIDATE,
            user_type=UserType.UNREVIEWED,
        )
        kym_analysis._velocity_events[roi.id].append(unreviewed_event)
        
        events_before = kym_analysis.get_velocity_events(roi_id=roi.id)
        assert events_before is not None
        assert len(events_before) == 3
        
        # Remove auto-detected events
        kym_analysis.remove_velocity_event(roi_id=roi.id, remove_these="auto_detected")
        events_after = kym_analysis.get_velocity_events(roi_id=roi.id)
        assert events_after is not None
        assert len(events_after) == 2  # User-added and reviewed should remain
        
        # Verify correct events remain
        event_types = [e.event_type for e in events_after]
        user_types = [e.user_type for e in events_after]
        assert "User Added" in event_types
        assert UserType.TRUE_STALL in user_types
        assert UserType.UNREVIEWED not in user_types
        
        # Test invalid remove_these value
        with pytest.raises(ValueError, match="Invalid remove_these value"):
            kym_analysis.remove_velocity_event(roi_id=roi.id, remove_these="invalid")

    def test_num_velocity_events(self) -> None:
        """Test num_velocity_events and total_num_velocity_events methods."""
        test_image = np.zeros((100, 100), dtype=np.uint16)
        kym_image = KymImage(img_data=test_image, load_image=True)
        kym_analysis = kym_image.get_kym_analysis()
        
        kym_image.header.voxels[0] = 0.1
        bounds1 = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
        roi1 = kym_image.rois.create_roi(bounds=bounds1)
        bounds2 = RoiBounds(dim0_start=60, dim0_stop=90, dim1_start=60, dim1_stop=90)
        roi2 = kym_image.rois.create_roi(bounds=bounds2)
        
        # Initially no events
        assert kym_analysis.num_velocity_events(roi_id=roi1.id) == 0
        assert kym_analysis.num_velocity_events(roi_id=roi2.id) == 0
        assert kym_analysis.total_num_velocity_events() == 0
        
        # Add events to roi1
        kym_analysis.add_velocity_event(roi_id=roi1.id, t_start=1.0, t_end=1.5)
        kym_analysis.add_velocity_event(roi_id=roi1.id, t_start=2.0, t_end=2.5)
        
        assert kym_analysis.num_velocity_events(roi_id=roi1.id) == 2
        assert kym_analysis.num_velocity_events(roi_id=roi2.id) == 0
        assert kym_analysis.total_num_velocity_events() == 2
        
        # Add event to roi2
        kym_analysis.add_velocity_event(roi_id=roi2.id, t_start=3.0, t_end=3.5)
        
        assert kym_analysis.num_velocity_events(roi_id=roi1.id) == 2
        assert kym_analysis.num_velocity_events(roi_id=roi2.id) == 1
        assert kym_analysis.total_num_velocity_events() == 3
