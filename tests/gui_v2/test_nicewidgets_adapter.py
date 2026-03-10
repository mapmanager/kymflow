"""Unit tests for nicewidgets adapter (Phase 2 migration)."""

from __future__ import annotations

import numpy as np
import pytest

from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.core.image_loaders.roi import RoiBounds
from kymflow.core.analysis.velocity_events.velocity_events import (
    MachineType,
    UserType,
    VelocityEvent,
)
from kymflow.gui_v2.adapters import (
    kymimage_to_channel_manager,
    velocity_events_to_acq_image_events,
)


def _make_synthetic_kym(
    num_lines: int = 100,
    pixels_per_line: int = 50,
    seconds_per_line: float = 0.001,
    um_per_pixel: float = 1.0,
    rois: list[tuple[int, int, int, int]] | None = None,
) -> KymImage:
    """Create a synthetic KymImage with img_data (no file)."""
    data = np.random.rand(num_lines, pixels_per_line).astype(np.float32)
    kym = KymImage(img_data=data, load_image=False)
    if rois:
        for r0, r1, c0, c1 in rois:
            kym.rois.create_roi(
                bounds=RoiBounds(dim0_start=r0, dim0_stop=r1, dim1_start=c0, dim1_stop=c1),
                channel=1,
                z=0,
            )
    return kym


class TestKymimageToChannelManager:
    """Tests for kymimage_to_channel_manager."""

    def test_returns_channel_manager_and_rois(self) -> None:
        """Adapter returns (ChannelManager, List[RegionOfInterest]) with correct bounds."""
        kym = _make_synthetic_kym(20, 30, rois=[(0, 10, 0, 15)])
        manager, rois = kymimage_to_channel_manager(kym)
        assert manager is not None
        assert len(rois) == 1
        # ROI names use format ROI_<roi_id>; kymflow may use 1-based IDs
        # Adapter uses name=str(roi_id) for widget display (e.g. "1", "2")
        assert rois[0].name.isdigit()
        assert rois[0].r0 == 0 and rois[0].r1 == 10
        assert rois[0].c0 == 0 and rois[0].c1 == 15

    def test_manager_has_correct_structure(self) -> None:
        """ChannelManager has valid geometry and channel data."""
        kym = _make_synthetic_kym(num_lines=50, pixels_per_line=80)
        manager, rois = kymimage_to_channel_manager(kym)
        # Synthetic KymImage without path may have default voxels
        assert manager.row_scale > 0
        assert manager.col_scale > 0
        ch = manager.get_active_channel()
        assert ch.data.shape == (50, 80)

    def test_multiple_rois_use_roi_naming(self) -> None:
        """ROI names are str(roi_id) for bindings mapping (ids from get_roi_ids)."""
        kym = _make_synthetic_kym(20, 20, rois=[(0, 5, 0, 5), (10, 15, 10, 15)])
        _, rois = kymimage_to_channel_manager(kym)
        assert len(rois) == 2
        for roi in rois:
            assert roi.name.isdigit()
        assert rois[0].r0 == 0 and rois[0].r1 == 5
        assert rois[1].r0 == 10 and rois[1].r1 == 15

    def test_empty_rois_returns_empty_list(self) -> None:
        """KymImage with no ROIs yields empty rois list."""
        kym = _make_synthetic_kym(10, 10)
        _, rois = kymimage_to_channel_manager(kym)
        assert rois == []

    def test_fallback_when_header_incomplete(self) -> None:
        """Adapter uses fallback dt/dx when header shape/voxels missing or invalid."""
        data = np.zeros((5, 5), dtype=np.float32)
        kym = KymImage(img_data=data, load_image=False)
        manager, _ = kymimage_to_channel_manager(kym)
        # Adapter returns valid manager (fallback or header-derived)
        assert manager.row_scale > 0
        assert manager.col_scale > 0
        ch = manager.get_active_channel()
        assert ch.data.shape == (5, 5)


class TestVelocityEventsToAcqImageEvents:
    """Tests for velocity_events_to_acq_image_events."""

    def test_converts_single_event(self) -> None:
        """Single VelocityEvent maps to single AcqImageEvent."""
        ev = VelocityEvent(
            event_type="baseline_drop",
            i_start=10,
            t_start=1.0,
            i_end=20,
            t_end=2.0,
            machine_type=MachineType.STALL_CANDIDATE,
            user_type=UserType.UNREVIEWED,
        )
        object.__setattr__(ev, "_uuid", "test-uuid-123")
        result = velocity_events_to_acq_image_events([ev])
        assert len(result) == 1
        assert result[0].start_t == 1.0
        assert result[0].stop_t == 2.0
        assert result[0].event_type == "baseline_drop"
        assert result[0].user_type == "unreviewed"
        assert result[0].event_id == "test-uuid-123"

    def test_converts_event_with_none_stop_t(self) -> None:
        """VelocityEvent with t_end=None maps to stop_t=None."""
        ev = VelocityEvent(
            event_type="User Added",
            i_start=5,
            t_start=0.5,
        )
        object.__setattr__(ev, "_uuid", "point-event")
        result = velocity_events_to_acq_image_events([ev])
        assert len(result) == 1
        assert result[0].stop_t is None

    def test_none_input_returns_empty_list(self) -> None:
        """None events returns empty list."""
        assert velocity_events_to_acq_image_events(None) == []

    def test_empty_list_returns_empty_list(self) -> None:
        """Empty events list returns empty list."""
        assert velocity_events_to_acq_image_events([]) == []

    def test_generates_uuid_when_missing(self) -> None:
        """Event without _uuid gets generated UUID."""
        ev = VelocityEvent(
            event_type="baseline_drop",
            i_start=0,
            t_start=0.0,
        )
        result = velocity_events_to_acq_image_events([ev])
        assert len(result) == 1
        assert result[0].event_id is not None
        assert len(result[0].event_id) > 0


def test_parse_roi_id_from_name() -> None:
    """_parse_roi_id_from_name extracts roi_id from ROI_<id>."""
    from kymflow.gui_v2.views.image_line_viewer_v2_view import (
        _parse_roi_id_from_name,
    )

    assert _parse_roi_id_from_name("ROI_0") == 0
    assert _parse_roi_id_from_name("ROI_1") == 1
    assert _parse_roi_id_from_name("ROI_42") == 42
    assert _parse_roi_id_from_name("ROI_") is None
    assert _parse_roi_id_from_name("Other") is None
    assert _parse_roi_id_from_name("") is None


class TestImageLineViewerV2View:
    """Basic tests for ImageLineViewerV2View (Phase 2)."""

    def test_instantiation(self) -> None:
        """View can be instantiated with optional callbacks."""
        from kymflow.gui_v2.views.image_line_viewer_v2_view import (
            ImageLineViewerV2View,
        )

        view = ImageLineViewerV2View()
        assert view._current_file is None
        assert view._current_roi_id is None

    def test_set_theme_before_render(self) -> None:
        """set_theme does not crash when widgets not yet created."""
        from kymflow.core.plotting.theme import ThemeMode
        from kymflow.gui_v2.views.image_line_viewer_v2_view import (
            ImageLineViewerV2View,
        )

        view = ImageLineViewerV2View()
        view.set_theme(ThemeMode.DARK)
        assert view._theme == ThemeMode.DARK

    def test_set_selected_file_none(self) -> None:
        """set_selected_file(None) does not crash."""
        from kymflow.gui_v2.views.image_line_viewer_v2_view import (
            ImageLineViewerV2View,
        )

        view = ImageLineViewerV2View()
        view.set_selected_file(None)
        assert view._current_file is None
