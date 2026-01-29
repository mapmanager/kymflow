"""Tests for stall analysis functionality.

DEPRECATED: Stall analysis tests are deprecated in favor of velocity event analysis.
These tests are kept for reference but are skipped by default.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from kymflow.core.analysis.stall_analysis import (
    Stall,
    StallAnalysis,
    StallAnalysisParams,
    detect_stalls,
)
from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.core.utils.logging import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)

pytestmark = pytest.mark.skip(reason="Stall analysis tests are deprecated in favor of velocity event analysis")


class TestStallDataclass:
    """Tests for the Stall dataclass."""

    def test_stall_creation(self) -> None:
        """Test creating a Stall object with valid data."""
        stall = Stall(bin_start=10, bin_stop=15)
        assert stall.bin_start == 10
        assert stall.bin_stop == 15
        assert stall.stall_bins == 6

    def test_stall_validation_bin_start_negative(self) -> None:
        """Test that Stall raises error for negative bin_start."""
        with pytest.raises(ValueError, match="bin_start must be >= 0"):
            Stall(bin_start=-1, bin_stop=5)

    def test_stall_validation_bin_stop_before_start(self) -> None:
        """Test that Stall raises error when bin_stop < bin_start."""
        with pytest.raises(ValueError, match="bin_stop.*must be >= bin_start"):
            Stall(bin_start=10, bin_stop=5)

    def test_stall_bins_property_is_derived(self) -> None:
        """Test that stall_bins is derived from bin_start/bin_stop."""
        stall = Stall(bin_start=10, bin_stop=15)
        assert stall.stall_bins == 6


class TestDetectStallsSimple:
    """Tests for detect_stalls() with simple cases."""

    def test_no_stalls(self) -> None:
        """Test detect_stalls with no NaN values."""
        velocity = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        stalls = detect_stalls(velocity, refactory_bins=0)
        assert len(stalls) == 0

    def test_all_stalls(self) -> None:
        """Test detect_stalls with all NaN values."""
        velocity = np.array([np.nan, np.nan, np.nan, np.nan, np.nan])
        stalls = detect_stalls(velocity, refactory_bins=0)
        assert len(stalls) == 1
        assert stalls[0].bin_start == 0
        assert stalls[0].bin_stop == 4
        assert stalls[0].stall_bins == 5

    def test_single_stall_in_middle(self) -> None:
        """Test detect_stalls with single stall in middle of array."""
        velocity = np.array([1.0, 2.0, np.nan, np.nan, np.nan, 3.0, 4.0])
        stalls = detect_stalls(velocity, refactory_bins=0)
        assert len(stalls) == 1
        assert stalls[0].bin_start == 2
        assert stalls[0].bin_stop == 4
        assert stalls[0].stall_bins == 3

    def test_stall_at_start(self) -> None:
        """Test detect_stalls with stall at start of array."""
        velocity = np.array([np.nan, np.nan, 1.0, 2.0, 3.0])
        stalls = detect_stalls(velocity, refactory_bins=0)
        assert len(stalls) == 1
        assert stalls[0].bin_start == 0
        assert stalls[0].bin_stop == 1
        assert stalls[0].stall_bins == 2

    def test_stall_at_end(self) -> None:
        """Test detect_stalls with stall at end of array."""
        velocity = np.array([1.0, 2.0, 3.0, np.nan, np.nan])
        stalls = detect_stalls(velocity, refactory_bins=0)
        assert len(stalls) == 1
        assert stalls[0].bin_start == 3
        assert stalls[0].bin_stop == 4
        assert stalls[0].stall_bins == 2

    def test_multiple_stalls_with_spacing(self) -> None:
        """Test detect_stalls with multiple well-spaced stalls."""
        velocity = np.array(
            [1.0, np.nan, np.nan, 2.0, 3.0, np.nan, 4.0, 5.0, np.nan, np.nan, np.nan, 6.0]
        )
        stalls = detect_stalls(velocity, refactory_bins=0)
        assert len(stalls) == 3

        # First stall: bins 1-2
        assert stalls[0].bin_start == 1
        assert stalls[0].bin_stop == 2
        assert stalls[0].stall_bins == 2

        # Second stall: bin 5
        assert stalls[1].bin_start == 5
        assert stalls[1].bin_stop == 5
        assert stalls[1].stall_bins == 1

        # Third stall: bins 8-10
        assert stalls[2].bin_start == 8
        assert stalls[2].bin_stop == 10
        assert stalls[2].stall_bins == 3

    def test_invalid_input_not_1d(self) -> None:
        """Test detect_stalls raises error for non-1D array."""
        velocity = np.array([[1.0, 2.0], [3.0, 4.0]])
        with pytest.raises(ValueError, match="velocity must be 1D array"):
            detect_stalls(velocity, refactory_bins=0)

    def test_invalid_input_negative_refactory_bins(self) -> None:
        """Test detect_stalls raises error for negative refactory_bins."""
        velocity = np.array([1.0, 2.0, 3.0])
        with pytest.raises(ValueError, match="refactory_bins must be >= 0"):
            detect_stalls(velocity, refactory_bins=-1)


class TestDetectStallsMinDuration:
    """Tests for detect_stalls() min_stall_duration filtering."""

    def test_min_stall_duration_filters_short_stalls(self) -> None:
        """Test that stalls shorter than min_stall_duration are filtered out."""
        # One short stall (2 bins) and one long stall (5 bins)
        velocity = np.array([1.0, np.nan, np.nan, 2.0, 3.0, np.nan, np.nan, np.nan, np.nan, np.nan, 4.0])
        # With min_stall_duration=3, only the 5-bin stall should be detected
        stalls = detect_stalls(velocity, refactory_bins=0, min_stall_duration=3)
        assert len(stalls) == 1
        assert stalls[0].bin_start == 5
        assert stalls[0].bin_stop == 9
        assert stalls[0].stall_bins == 5

    def test_min_stall_duration_all_filtered(self) -> None:
        """Test that all stalls can be filtered out if they're all too short."""
        # Use array where stalls are definitely 1 bin each and don't extend to end
        velocity = np.array([1.0, np.nan, 2.0, np.nan, 3.0, 4.0])
        # First stall: index 1 (1 bin), second stall: index 3 (1 bin)
        # With min_stall_duration=2, both should be filtered out
        stalls = detect_stalls(velocity, refactory_bins=0, min_stall_duration=2)
        assert len(stalls) == 0

    def test_min_stall_duration_none_filtered(self) -> None:
        """Test that all stalls pass when min_stall_duration=1."""
        velocity = np.array([1.0, np.nan, 2.0, np.nan, 3.0])
        stalls = detect_stalls(velocity, refactory_bins=0, min_stall_duration=1)
        assert len(stalls) == 2

    def test_min_stall_duration_exact_threshold(self) -> None:
        """Test that stalls exactly at the threshold are included."""
        velocity = np.array([1.0, np.nan, np.nan, 2.0])
        # Stall spans indices 1-2 (2 bins). With min_stall_duration=2, it should be included.
        stalls = detect_stalls(velocity, refactory_bins=0, min_stall_duration=2)
        assert len(stalls) == 1
        assert stalls[0].bin_start == 1
        assert stalls[0].bin_stop == 2
        assert stalls[0].stall_bins == 2

    def test_min_stall_duration_one_below_threshold(self) -> None:
        """Test that stalls one bin below threshold are filtered out."""
        velocity = np.array([1.0, np.nan, 2.0, 3.0])
        # Stall at index 1 is 1 bin, min_stall_duration=2 should filter it out
        stalls = detect_stalls(velocity, refactory_bins=0, min_stall_duration=2)
        assert len(stalls) == 0

    def test_min_stall_duration_with_refractory_period(self) -> None:
        """Test that filtered stalls don't affect refractory period."""
        # This case ensures that a short stall filtered by min_stall_duration does not
        # update the refractory anchor and therefore does not suppress later stalls.
        #
        # Stall 0: indices 1-2 (2 bins) -> accepted
        # Stall 1: index 5 (1 bin) -> filtered (min_stall_duration=2)
        # Stall 2: indices 7-8 (2 bins) -> should still be accepted
        velocity = np.array([1.0, np.nan, np.nan, 2.0, 3.0, np.nan, 4.0, np.nan, np.nan, 5.0])
        stalls = detect_stalls(velocity, refactory_bins=2, min_stall_duration=2)
        assert len(stalls) == 2
        assert stalls[0].bin_start == 1
        assert stalls[0].bin_stop == 2
        assert stalls[0].stall_bins == 2
        assert stalls[1].bin_start == 7
        assert stalls[1].bin_stop == 8
        assert stalls[1].stall_bins == 2

    def test_min_stall_duration_invalid_value(self) -> None:
        """Test that min_stall_duration < 1 raises error."""
        velocity = np.array([1.0, 2.0, 3.0])
        with pytest.raises(ValueError, match="min_stall_duration must be >= 1"):
            detect_stalls(velocity, refactory_bins=0, min_stall_duration=0)

    def test_min_stall_duration_zero_raises_error(self) -> None:
        """Test that min_stall_duration=0 raises error."""
        velocity = np.array([1.0, 2.0, 3.0])
        with pytest.raises(ValueError, match="min_stall_duration must be >= 1"):
            detect_stalls(velocity, refactory_bins=0, min_stall_duration=0)


class TestDetectStallsEndStallNonNanBins:
    """Tests for detect_stalls() end_stall_non_nan_bins bridging behavior."""

    def test_end_stall_non_nan_bins_bridges_short_non_nan_pop(self) -> None:
        """A short non-NaN pop (< threshold) is bridged, merging stalls."""
        # NaNs at 1-2, a 1-bin non-NaN "pop" at 3, then NaNs again at 4-5.
        # With end_stall_non_nan_bins=1, we end a stall at the first non-NaN, so we get 2 stalls.
        # With end_stall_non_nan_bins=2, that 1-bin pop is bridged and we get 1 merged stall.
        velocity = np.array([1.0, np.nan, np.nan, 2.0, np.nan, np.nan, 3.0, 4.0])

        stalls_end1 = detect_stalls(
            velocity,
            refactory_bins=0,
            end_stall_non_nan_bins=1,
        )
        assert [(s.bin_start, s.bin_stop) for s in stalls_end1] == [(1, 2), (4, 5)]

        stalls_end2 = detect_stalls(
            velocity,
            refactory_bins=0,
            end_stall_non_nan_bins=2,
        )
        assert [(s.bin_start, s.bin_stop) for s in stalls_end2] == [(1, 5)]

    def test_end_stall_non_nan_bins_affects_min_stall_duration(self) -> None:
        """Bridging can increase span so a stall passes min_stall_duration."""
        velocity = np.array([1.0, np.nan, 2.0, np.nan, 3.0, 4.0])

        # Without bridging (end=1), stall is just index 1 (1 bin) => filtered out by min=3.
        stalls_end1 = detect_stalls(
            velocity,
            refactory_bins=0,
            min_stall_duration=3,
            end_stall_non_nan_bins=1,
        )
        assert stalls_end1 == []

        # With end=2, the single non-NaN at index 2 is bridged and stall spans indices 1-3 (3 bins).
        stalls_end2 = detect_stalls(
            velocity,
            refactory_bins=0,
            min_stall_duration=3,
            end_stall_non_nan_bins=2,
        )
        assert [(s.bin_start, s.bin_stop, s.stall_bins) for s in stalls_end2] == [(1, 3, 3)]

    def test_stall_analysis_run_uses_end_stall_non_nan_bins_param(self) -> None:
        """StallAnalysis.run should honor params.end_stall_non_nan_bins."""
        velocity = np.array([1.0, np.nan, np.nan, 2.0, np.nan, np.nan, 3.0, 4.0])
        params = StallAnalysisParams(
            refactory_bins=0,
            min_stall_duration=1,
            end_stall_non_nan_bins=2,
        )
        analysis = StallAnalysis.run(velocity=velocity, params=params)
        assert analysis.params.end_stall_non_nan_bins == 2
        assert [(s.bin_start, s.bin_stop) for s in analysis.stalls] == [(1, 5)]


class TestDetectStallsRefractory:
    """Tests for detect_stalls() refractory period logic."""

    def test_refactory_bins_zero_all_detected(self) -> None:
        """Test that refactory_bins=0 detects all stalls separately."""
        velocity = np.array([1.0, np.nan, 2.0, np.nan, 3.0])
        stalls = detect_stalls(velocity, refactory_bins=0)
        assert len(stalls) == 2

    def test_refactory_bins_within_period_skip_second(self) -> None:
        """Test that stalls within refractory period skip the second stall."""
        # Two stalls with only 1 bin between them (stall stops at bin 1, next starts at bin 3)
        # With refactory_bins=2, we need at least 2 bins after stop before starting new stall
        velocity = np.array([1.0, np.nan, 2.0, np.nan, 3.0, 4.0])
        # First stall: bin 1, stop at 1
        # Second stall starts at bin 3, which is only 1 bin after stop (3 - 1 = 2 bins)
        # If refactory_bins=3, second stall should be skipped
        stalls = detect_stalls(velocity, refactory_bins=3)
        assert len(stalls) == 1
        assert stalls[0].bin_start == 1
        assert stalls[0].bin_stop == 1

    def test_refactory_bins_beyond_period_both_detected(self) -> None:
        """Test that stalls beyond refractory period are both detected."""
        # Two stalls with sufficient spacing
        velocity = np.array([1.0, np.nan, 2.0, 3.0, 4.0, np.nan, 5.0])
        # First stall: bin 1, stop at 1
        # Second stall starts at bin 5, which is 4 bins after stop (5 - 1 = 4)
        # With refactory_bins=3, second stall should be detected
        stalls = detect_stalls(velocity, refactory_bins=3)
        assert len(stalls) == 2

    def test_refactory_bins_exact_boundary(self) -> None:
        """Test refractory period at exact boundary."""
        # Two stalls with exactly refactory_bins spacing
        velocity = np.array([1.0, np.nan, 2.0, 3.0, np.nan, 4.0])
        # First stall: bin 1, stop at 1
        # Second stall starts at bin 4, which is exactly 3 bins after stop (4 - 1 = 3)
        # With refactory_bins=3, this is still within the refractory period and is skipped
        stalls = detect_stalls(velocity, refactory_bins=3)
        assert len(stalls) == 1

    def test_refactory_bins_one_bin_before_threshold(self) -> None:
        """Test that stall one bin before threshold is skipped."""
        velocity = np.array([1.0, np.nan, 2.0, np.nan, 4.0])
        # First stall: bin 1, stop at 1
        # Second stall starts at bin 3, which is 2 bins after stop (3 - 1 = 2)
        # With refactory_bins=3, condition is: 3 >= 1 + 3 = 4, which is False
        # So second stall should be skipped
        stalls = detect_stalls(velocity, refactory_bins=3)
        assert len(stalls) == 1

    def test_refactory_bins_consecutive_stalls_merge(self) -> None:
        """Test that consecutive stalls separated by single valid value are handled."""
        # Stalls at bins 0, 2, 4 with valid values in between
        velocity = np.array([np.nan, 1.0, np.nan, 2.0, np.nan, 3.0])
        # First stall: bin 0, stop at 0
        # Second stall at bin 2: 2 >= 0 + 1 = 1 (with refactory_bins=1) -> True, detected
        # Third stall at bin 4: 4 >= 2 + 1 = 3 (with refactory_bins=1) -> True, detected
        stalls = detect_stalls(velocity, refactory_bins=1)
        assert len(stalls) == 3


class TestDetectStallsStartBin:
    """Tests for detect_stalls() start_bin parameter."""

    def test_start_bin_defaults_to_zero(self) -> None:
        """Test that start_bin defaults to 0 (backward compatibility)."""
        velocity = np.array([1.0, 2.0, np.nan, np.nan, np.nan, 3.0, 4.0])
        stalls_default = detect_stalls(velocity, refactory_bins=0)
        stalls_explicit = detect_stalls(velocity, refactory_bins=0, start_bin=0)
        stalls_none = detect_stalls(velocity, refactory_bins=0, start_bin=None)
        
        assert len(stalls_default) == len(stalls_explicit) == len(stalls_none) == 1
        assert stalls_default[0].bin_start == stalls_explicit[0].bin_start == stalls_none[0].bin_start == 2
        assert stalls_default[0].bin_stop == stalls_explicit[0].bin_stop == stalls_none[0].bin_stop == 4

    def test_start_bin_offsets_bin_numbers(self) -> None:
        """Test that start_bin correctly offsets bin numbers."""
        velocity = np.array([1.0, 2.0, np.nan, np.nan, np.nan, 3.0, 4.0])
        
        # Without offset (default)
        stalls_no_offset = detect_stalls(velocity, refactory_bins=0)
        assert stalls_no_offset[0].bin_start == 2
        assert stalls_no_offset[0].bin_stop == 4
        
        # With offset
        stalls_with_offset = detect_stalls(velocity, refactory_bins=0, start_bin=100)
        assert stalls_with_offset[0].bin_start == 102  # 100 + 2
        assert stalls_with_offset[0].bin_stop == 104   # 100 + 4
        assert stalls_with_offset[0].stall_bins == 3  # Duration unchanged

    def test_start_bin_multiple_stalls(self) -> None:
        """Test start_bin with multiple stalls."""
        velocity = np.array(
            [1.0, np.nan, np.nan, 2.0, 3.0, np.nan, np.nan, np.nan, 4.0, 5.0]
        )
        stalls = detect_stalls(velocity, refactory_bins=0, start_bin=50)
        
        assert len(stalls) == 2
        # First stall: array indices 1-2, actual bins 51-52
        assert stalls[0].bin_start == 51
        assert stalls[0].bin_stop == 52
        # Second stall: array indices 5-7, actual bins 55-57
        assert stalls[1].bin_start == 55
        assert stalls[1].bin_stop == 57

    def test_start_bin_stall_at_start(self) -> None:
        """Test start_bin with stall at start of array."""
        velocity = np.array([np.nan, np.nan, 1.0, 2.0, 3.0])
        stalls = detect_stalls(velocity, refactory_bins=0, start_bin=200)
        
        assert len(stalls) == 1
        assert stalls[0].bin_start == 200  # 200 + 0
        assert stalls[0].bin_stop == 201   # 200 + 1

    def test_start_bin_stall_at_end(self) -> None:
        """Test start_bin with stall at end of array."""
        velocity = np.array([1.0, 2.0, 3.0, np.nan, np.nan])
        stalls = detect_stalls(velocity, refactory_bins=0, start_bin=10)
        
        assert len(stalls) == 1
        assert stalls[0].bin_start == 13  # 10 + 3
        assert stalls[0].bin_stop == 14   # 10 + 4

    def test_start_bin_all_stalls(self) -> None:
        """Test start_bin with all NaN values."""
        velocity = np.array([np.nan, np.nan, np.nan, np.nan, np.nan])
        stalls = detect_stalls(velocity, refactory_bins=0, start_bin=1000)
        
        assert len(stalls) == 1
        assert stalls[0].bin_start == 1000  # 1000 + 0
        assert stalls[0].bin_stop == 1004   # 1000 + 4

    def test_start_bin_refractory_period(self) -> None:
        """Test that start_bin doesn't affect refractory period logic."""
        velocity = np.array(
            [1.0, np.nan, 2.0, np.nan, np.nan, 3.0, np.nan, np.nan, 4.0]
        )
        # With refactory_bins=2, stalls can start only when (i - last_stop) > 2.
        stalls = detect_stalls(velocity, refactory_bins=2, start_bin=50)

        # Detected stall starts (array indices): 1, 4, 7
        assert len(stalls) == 3
        assert stalls[0].bin_start == 51  # 50 + 1
        assert stalls[1].bin_start == 54  # 50 + 4
        assert stalls[2].bin_start == 57  # 50 + 7

    def test_start_bin_negative_raises_error(self) -> None:
        """Test that negative start_bin raises ValueError."""
        velocity = np.array([1.0, 2.0, 3.0])
        with pytest.raises(ValueError, match="start_bin must be >= 0"):
            detect_stalls(velocity, refactory_bins=0, start_bin=-1)

    def test_start_bin_zero_explicit(self) -> None:
        """Test that start_bin=0 works explicitly."""
        velocity = np.array([1.0, 2.0, np.nan, np.nan, 3.0])
        stalls = detect_stalls(velocity, refactory_bins=0, start_bin=0)
        
        assert len(stalls) == 1
        assert stalls[0].bin_start == 2
        assert stalls[0].bin_stop == 3


class TestDetectStallsIntegration:
    """Integration tests using real KymImage and KymAnalysis data."""

    @pytest.mark.requires_data
    def test_detect_stalls_with_real_data(self, test_data_dir: Path) -> None:
        """Test detect_stalls with real kymograph analysis data."""
        if not test_data_dir.exists():
            pytest.skip("Test data directory does not exist")

        # Find Capillary1_0001.tif
        tif_file = test_data_dir / "Capillary1_0001.tif"
        if not tif_file.exists():
            pytest.skip("Capillary1_0001.tif not found in test data")

        # Load KymImage
        kym_image = KymImage(tif_file, load_image=False)
        kym_analysis = kym_image.get_kym_analysis()

        # Check if analysis exists
        if not kym_analysis.has_analysis(roi_id=1):
            # logger.warning(f'{tif_file}')
            pytest.skip(f"No analysis data available for ROI 1 in {tif_file}")

        # Get velocity data
        velocity = kym_analysis.get_analysis_value(roi_id=1, key="velocity")
        if velocity is None:
            pytest.skip("No velocity data available for ROI 1")

        logger.info(f"Testing with velocity array of length {len(velocity)}")
        logger.info(f"Number of NaN values: {np.sum(np.isnan(velocity))}")

        # Detect stalls with different refractory periods
        stalls_0 = detect_stalls(velocity, refactory_bins=0)
        stalls_10 = detect_stalls(velocity, refactory_bins=10)
        stalls_100 = detect_stalls(velocity, refactory_bins=100)

        logger.info(f"Detected {len(stalls_0)} stalls with refactory_bins=0")
        logger.info(f"Detected {len(stalls_10)} stalls with refactory_bins=10")
        logger.info(f"Detected {len(stalls_100)} stalls with refactory_bins=100")

        # Verify stalls are valid
        for stall in stalls_0:
            assert stall.bin_start >= 0
            assert stall.bin_stop >= stall.bin_start
            assert stall.bin_stop < len(velocity)
            assert stall.stall_bins == (stall.bin_stop - stall.bin_start + 1)

        # Verify that larger refactory_bins results in fewer or equal stalls
        assert len(stalls_0) >= len(stalls_10)
        assert len(stalls_10) >= len(stalls_100)

    @pytest.mark.requires_data
    def test_stall_ranges_are_correct(self, test_data_dir: Path) -> None:
        """Test that detected stall ranges actually contain NaN values."""
        if not test_data_dir.exists():
            pytest.skip("Test data directory does not exist")

        tif_file = test_data_dir / "Capillary1_0001.tif"
        if not tif_file.exists():
            pytest.skip("Capillary1_0001.tif not found in test data")

        kym_image = KymImage(tif_file, load_image=False)
        kym_analysis = kym_image.get_kym_analysis()

        if not kym_analysis.has_analysis(roi_id=1):
            pytest.skip("No analysis data available for ROI 1")

        velocity = kym_analysis.get_analysis_value(roi_id=1, key="velocity")
        if velocity is None:
            pytest.skip("No velocity data available for ROI 1")

        stalls = detect_stalls(velocity, refactory_bins=0)

        # Verify that all bins in stall ranges are NaN
        for stall in stalls:
            stall_range = velocity[stall.bin_start : stall.bin_stop + 1]
            assert np.all(
                np.isnan(stall_range)
            ), f"Stall at {stall.bin_start}-{stall.bin_stop} contains non-NaN values"

        # Verify that bins immediately before and after stalls are not NaN
        # (unless at array boundaries)
        for stall in stalls:
            if stall.bin_start > 0:
                assert not np.isnan(
                    velocity[stall.bin_start - 1]
                ), f"Bin before stall {stall.bin_start} should not be NaN"
            if stall.bin_stop < len(velocity) - 1:
                assert not np.isnan(
                    velocity[stall.bin_stop + 1]
                ), f"Bin after stall {stall.bin_stop} should not be NaN"


class TestStallPlotting:
    """Tests for plotting functions."""

    @pytest.mark.requires_data
    def test_plot_stalls_matplotlib_creates_figure(self, test_data_dir: Path) -> None:
        """Test that plot_stalls_matplotlib creates a figure."""
        from kymflow.core.plotting.stall_plots import plot_stalls_matplotlib

        if not test_data_dir.exists():
            pytest.skip("Test data directory does not exist")

        tif_file = test_data_dir / "Capillary1_0001.tif"
        if not tif_file.exists():
            pytest.skip("Capillary1_0001.tif not found in test data")

        kym_image = KymImage(tif_file, load_image=False)
        kym_analysis = kym_image.get_kym_analysis()

        if not kym_analysis.has_analysis(roi_id=1):
            pytest.skip("No analysis data available for ROI 1")

        # Get velocity and detect stalls
        velocity = kym_analysis.get_analysis_value(roi_id=1, key="velocity")
        if velocity is None:
            pytest.skip("No velocity data available for ROI 1")

        stalls = detect_stalls(velocity, refactory_bins=10)

        # Create plot
        fig = plot_stalls_matplotlib(
            kym_image=kym_image,
            roi_id=1,
            stalls=stalls,
            use_time_axis=False,
        )

        assert fig is not None

    @pytest.mark.requires_data
    def test_plot_stalls_plotly_creates_figure(self, test_data_dir: Path) -> None:
        """Test that plot_stalls_plotly creates a figure."""
        from kymflow.core.plotting.stall_plots import plot_stalls_plotly

        if not test_data_dir.exists():
            pytest.skip("Test data directory does not exist")

        tif_file = test_data_dir / "Capillary1_0001.tif"
        if not tif_file.exists():
            pytest.skip("Capillary1_0001.tif not found in test data")

        kym_image = KymImage(tif_file, load_image=False)
        kym_analysis = kym_image.get_kym_analysis()

        if not kym_analysis.has_analysis(roi_id=1):
            pytest.skip("No analysis data available for ROI 1")

        # Get velocity and detect stalls
        velocity = kym_analysis.get_analysis_value(roi_id=1, key="velocity")
        if velocity is None:
            pytest.skip("No velocity data available for ROI 1")

        stalls = detect_stalls(velocity, refactory_bins=10)

        # Create plot
        fig = plot_stalls_plotly(
            kym_image=kym_image,
            roi_id=1,
            stalls=stalls,
            use_time_axis=False,
        )

        assert fig is not None

    @pytest.mark.requires_data
    def test_plot_stalls_with_empty_stalls_list(self, test_data_dir: Path) -> None:
        """Test plotting with empty stalls list."""
        from kymflow.core.plotting.stall_plots import (
            plot_stalls_matplotlib,
            plot_stalls_plotly,
        )

        if not test_data_dir.exists():
            pytest.skip("Test data directory does not exist")

        tif_file = test_data_dir / "Capillary1_0001.tif"
        if not tif_file.exists():
            pytest.skip("Capillary1_0001.tif not found in test data")

        kym_image = KymImage(tif_file, load_image=False)
        kym_analysis = kym_image.get_kym_analysis()

        if not kym_analysis.has_analysis(roi_id=1):
            pytest.skip("No analysis data available for ROI 1")

        # Create plots with empty stalls list
        fig_mpl = plot_stalls_matplotlib(
            kym_image=kym_image, roi_id=1, stalls=[], use_time_axis=False
        )
        fig_plotly = plot_stalls_plotly(
            kym_image=kym_image, roi_id=1, stalls=[], use_time_axis=False
        )

        assert fig_mpl is not None
        assert fig_plotly is not None

    @pytest.mark.requires_data
    def test_plot_stalls_with_time_axis(self, test_data_dir: Path) -> None:
        """Test plotting with time axis enabled."""
        from kymflow.core.plotting.stall_plots import (
            plot_stalls_matplotlib,
            plot_stalls_plotly,
        )

        if not test_data_dir.exists():
            pytest.skip("Test data directory does not exist")

        tif_file = test_data_dir / "Capillary1_0001.tif"
        if not tif_file.exists():
            pytest.skip("Capillary1_0001.tif not found in test data")

        kym_image = KymImage(tif_file, load_image=False)
        kym_analysis = kym_image.get_kym_analysis()

        if not kym_analysis.has_analysis(roi_id=1):
            pytest.skip("No analysis data available for ROI 1")

        velocity = kym_analysis.get_analysis_value(roi_id=1, key="velocity")
        if velocity is None:
            pytest.skip("No velocity data available for ROI 1")

        stalls = detect_stalls(velocity, refactory_bins=10)

        # Create plots with time axis
        fig_mpl = plot_stalls_matplotlib(
            kym_image=kym_image, roi_id=1, stalls=stalls, use_time_axis=True
        )
        fig_plotly = plot_stalls_plotly(
            kym_image=kym_image, roi_id=1, stalls=stalls, use_time_axis=True
        )

        assert fig_mpl is not None
        assert fig_plotly is not None

    def test_plot_stalls_with_missing_analysis(self) -> None:
        """Test plotting with missing analysis data."""
        from kymflow.core.plotting.stall_plots import (
            plot_stalls_matplotlib,
            plot_stalls_plotly,
        )

        # Create a KymImage without analysis
        test_image = np.zeros((100, 100), dtype=np.uint16)
        kym_image = KymImage(img_data=test_image, load_image=False)

        # Create plots - should return None when no analysis data is available
        fig_mpl = plot_stalls_matplotlib(
            kym_image=kym_image, roi_id=999, stalls=[], use_time_axis=False
        )
        fig_plotly = plot_stalls_plotly(
            kym_image=kym_image, roi_id=999, stalls=[], use_time_axis=False
        )

        assert fig_mpl is None
        assert fig_plotly is None
