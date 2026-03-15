"""Tests for SaveController - metadata-only saves and dirty state checks."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
import tifffile

from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.core.image_loaders.kym_image_list import KymImageList
from kymflow.core.image_loaders.roi import RoiBounds
from kymflow.core.state import TaskState
from kymflow.core.utils.hidden_cache_paths import get_hidden_cache_path
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.controllers.save_controller import SaveController
from kymflow.gui_v2.events import SaveAll, SaveSelected
from kymflow.gui_v2.state import AppState


@pytest.fixture
def app_state_with_file() -> tuple[AppState, KymImage]:
    """Create an AppState with a test file loaded."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.tif"
        test_image = np.zeros((100, 200), dtype=np.uint16)
        tifffile.imwrite(test_file, test_image)

        kym_file = KymImage(test_file, load_image=True)

        app_state = AppState()
        image_list = KymImageList(path=None, file_extension=".tif", depth=1)
        image_list.images = [kym_file]
        app_state.files = image_list
        app_state.selected_file = kym_file

        return app_state, kym_file


@pytest.mark.asyncio
async def test_save_selected_metadata_only_dirty(
    bus: EventBus, app_state_with_file: tuple[AppState, KymImage]
) -> None:
    """Test that SaveController saves files with metadata-only dirty state."""
    app_state, kym_file = app_state_with_file
    task_state = TaskState()
    controller = SaveController(app_state, task_state, bus)  # Subscribes to events

    # Update metadata only (no analysis)
    kym_file.update_experiment_metadata(species="mouse", region="cortex")
    assert kym_file.is_metadata_dirty is True
    assert kym_file.get_kym_analysis().is_dirty is True

    # Mock save_analysis to verify it's called (handler is async; run it with patched run.io_bound)
    with patch.object(kym_file.get_kym_analysis(), "save_analysis") as mock_save:
        mock_save.return_value = True

        async def mock_io_bound(fn):
            return fn()

        with patch("kymflow.gui_v2.controllers.save_controller.ui.notify"):
            with patch("kymflow.gui_v2.controllers.save_controller.run") as mock_run:
                mock_run.io_bound = mock_io_bound
                await controller._on_save_selected_async(SaveSelected(phase="intent"))

        # Verify save_analysis was called (even without analysis data)
        mock_save.assert_called_once()


@pytest.mark.asyncio
async def test_save_selected_uses_is_dirty_not_has_analysis(
    bus: EventBus, app_state_with_file: tuple[AppState, KymImage]
) -> None:
    """Test that SaveController uses is_dirty property (not has_analysis gate)."""
    app_state, kym_file = app_state_with_file
    task_state = TaskState()
    controller = SaveController(app_state, task_state, bus)  # Subscribes to events

    # Update metadata only (no analysis data)
    kym_file.update_experiment_metadata(note="test note")
    assert kym_file.get_kym_analysis().is_dirty is True
    assert not kym_file.get_kym_analysis().has_analysis()

    # Mock save_analysis (handler is async; run it with patched run.io_bound)
    with patch.object(kym_file.get_kym_analysis(), "save_analysis") as mock_save:
        mock_save.return_value = True

        async def mock_io_bound(fn):
            return fn()

        with patch("kymflow.gui_v2.controllers.save_controller.ui.notify"):
            with patch("kymflow.gui_v2.controllers.save_controller.run") as mock_run:
                mock_run.io_bound = mock_io_bound
                await controller._on_save_selected_async(SaveSelected(phase="intent"))

        # Should call save_analysis even though has_analysis() is False
        mock_save.assert_called_once()


@pytest.mark.asyncio
async def test_save_all_metadata_only_dirty(
    bus: EventBus, app_state_with_file: tuple[AppState, KymImage]
) -> None:
    """Test that SaveController saves all files with metadata-only dirty state."""
    app_state, kym_file = app_state_with_file

    # Create second file with metadata dirty
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file2 = Path(tmpdir) / "test2.tif"
        test_image2 = np.zeros((80, 150), dtype=np.uint16)
        tifffile.imwrite(test_file2, test_image2)
        kym_file2 = KymImage(test_file2, load_image=True)

        # Add both files to app_state
        image_list = KymImageList(path=None, file_extension=".tif", depth=1)
        image_list.images = [kym_file, kym_file2]
        app_state.files = image_list

        # Update metadata for both files (no analysis)
        kym_file.update_experiment_metadata(species="mouse")
        kym_file2.update_experiment_metadata(region="cortex")

        task_state = TaskState()
        controller = SaveController(app_state, task_state, bus)  # Subscribes to events

        # Mock save_analysis for both files (handler is async; run it with patched run.io_bound)
        with patch.object(kym_file.get_kym_analysis(), "save_analysis") as mock_save1:
            with patch.object(kym_file2.get_kym_analysis(), "save_analysis") as mock_save2:
                mock_save1.return_value = True
                mock_save2.return_value = True

                async def mock_io_bound(fn):
                    return fn()

                with patch("kymflow.gui_v2.controllers.save_controller.ui.notify"):
                    with patch("kymflow.gui_v2.controllers.save_controller.run") as mock_run:
                        mock_run.io_bound = mock_io_bound
                        await controller._on_save_all_async(SaveAll(phase="intent"))

                # Both should be saved (even without analysis data)
                mock_save1.assert_called_once()
                mock_save2.assert_called_once()


@pytest.mark.asyncio
async def test_save_selected_skips_when_not_dirty(
    bus: EventBus, app_state_with_file: tuple[AppState, KymImage]
) -> None:
    """Test that SaveController skips save when file is not dirty."""
    app_state, kym_file = app_state_with_file
    task_state = TaskState()
    controller = SaveController(app_state, task_state, bus)  # Subscribes to events

    # File is not dirty
    assert not kym_file.get_kym_analysis().is_dirty

    # Mock save_analysis; run handler (it should return early and not call save_analysis)
    with patch.object(kym_file.get_kym_analysis(), "save_analysis") as mock_save:
        async def mock_io_bound(fn):
            return fn()

        with patch("kymflow.gui_v2.controllers.save_controller.ui.notify"):
            with patch("kymflow.gui_v2.controllers.save_controller.run") as mock_run:
                mock_run.io_bound = mock_io_bound
                await controller._on_save_selected_async(SaveSelected(phase="intent"))

        # Should not call save_analysis when not dirty
        mock_save.assert_not_called()


@pytest.mark.asyncio
async def test_save_selected_calls_update_radon_report_for_image(
    bus: EventBus, app_state_with_file: tuple[AppState, KymImage]
) -> None:
    """Test that SaveController calls update_radon_report_for_image after successful save."""
    app_state, kym_file = app_state_with_file
    task_state = TaskState()
    controller = SaveController(app_state, task_state, bus)

    kym_file.update_experiment_metadata(species="mouse")
    assert kym_file.get_kym_analysis().is_dirty is True

    with patch.object(kym_file.get_kym_analysis(), "save_analysis") as mock_save:
        mock_save.return_value = True
        with patch.object(
            app_state.files, "update_radon_report_for_image"
        ) as mock_update:
            async def mock_io_bound(fn):
                return fn()

            with patch("kymflow.gui_v2.controllers.save_controller.ui.notify"):
                with patch("kymflow.gui_v2.controllers.save_controller.run") as mock_run:
                    mock_run.io_bound = mock_io_bound
                    await controller._on_save_selected_async(SaveSelected(phase="intent"))

            mock_save.assert_called_once()
            mock_update.assert_called_once_with(kym_file)


@pytest.mark.asyncio
async def test_save_selected_integration_radon_and_velocity_event_csv_written(
    bus: EventBus,
) -> None:
    """Integration: Save Selected through controller writes radon and kym event DB CSVs.

    Goes through SaveController._on_save_selected_async (same as user clicking Save Selected).
    Verifies radon_report_db.csv and kym_event_db.csv exist in the folder after save.
    """
    import pandas as pd

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        test_file = tmp_path / "test.tif"
        tifffile.imwrite(test_file, np.zeros((100, 100), dtype=np.uint16))

        kym_file = KymImage(test_file, load_image=True)
        bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
        roi = kym_file.rois.create_roi(bounds=bounds)
        kym_file.get_kym_analysis().analyze_roi(roi.id, window_size=16, use_multiprocessing=False)
        kym_file.update_experiment_metadata(species="mouse")
        assert kym_file.get_kym_analysis().is_dirty is True

        image_list = KymImageList(path=tmp_path, file_extension=".tif", depth=1)
        image_list.images = [kym_file]
        assert image_list._get_radon_db_path() is not None
        assert image_list._get_velocity_event_db_path() is not None

        app_state = AppState()
        app_state.files = image_list
        app_state.selected_file = kym_file
        task_state = TaskState()
        controller = SaveController(app_state, task_state, bus)

        radon_db = tmp_path / "radon_report_db.csv"
        event_db = tmp_path / "kym_event_db.csv"
        assert not radon_db.exists()
        assert not event_db.exists()

        async def mock_io_bound(fn):
            return fn()

        with patch("kymflow.gui_v2.controllers.save_controller.ui.notify"):
            with patch("kymflow.gui_v2.controllers.save_controller.run") as mock_run:
                mock_run.io_bound = mock_io_bound
                await controller._on_save_selected_async(SaveSelected(phase="intent"))

        assert radon_db.exists()
        df_radon = pd.read_csv(radon_db)
        assert "roi_id" in df_radon.columns
        assert "vel_cv" in df_radon.columns or "vel_mean" in df_radon.columns
        assert len(df_radon) >= 1

        assert event_db.exists()
        df_events = pd.read_csv(event_db)
        assert "_unique_row_id" in df_events.columns or df_events.empty

        hidden_radon = get_hidden_cache_path(radon_db)
        assert hidden_radon.exists()


@pytest.mark.asyncio
async def test_save_all_integration_radon_and_velocity_event_csv_written(
    bus: EventBus,
) -> None:
    """Integration: Save All through controller writes radon and kym event DB CSVs.

    Goes through SaveController._on_save_all_async (same as user clicking Save All).
    Verifies radon_report_db.csv and kym_event_db.csv exist and include all saved files.
    """
    import pandas as pd

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        # Two files so Save All has something to save
        test_file1 = tmp_path / "test1.tif"
        test_file2 = tmp_path / "test2.tif"
        tifffile.imwrite(test_file1, np.zeros((100, 100), dtype=np.uint16))
        tifffile.imwrite(test_file2, np.zeros((80, 80), dtype=np.uint16))

        def make_image(path: Path) -> KymImage:
            kym = KymImage(path, load_image=True)
            bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
            roi = kym.rois.create_roi(bounds=bounds)
            kym.get_kym_analysis().analyze_roi(roi.id, window_size=16, use_multiprocessing=False)
            kym.update_experiment_metadata(species="mouse")
            return kym

        kym1 = make_image(test_file1)
        kym2 = make_image(test_file2)
        assert kym1.get_kym_analysis().is_dirty and kym2.get_kym_analysis().is_dirty

        image_list = KymImageList(path=tmp_path, file_extension=".tif", depth=1)
        image_list.images = [kym1, kym2]
        app_state = AppState()
        app_state.files = image_list
        task_state = TaskState()
        controller = SaveController(app_state, task_state, bus)

        radon_db = tmp_path / "radon_report_db.csv"
        event_db = tmp_path / "kym_event_db.csv"
        assert not radon_db.exists()
        assert not event_db.exists()

        async def mock_io_bound(fn):
            return fn()

        with patch("kymflow.gui_v2.controllers.save_controller.ui.notify"):
            with patch("kymflow.gui_v2.controllers.save_controller.run") as mock_run:
                mock_run.io_bound = mock_io_bound
                await controller._on_save_all_async(SaveAll(phase="intent"))

        assert radon_db.exists()
        df_radon = pd.read_csv(radon_db)
        assert "roi_id" in df_radon.columns
        assert len(df_radon) >= 2

        assert event_db.exists()
        hidden_radon = get_hidden_cache_path(radon_db)
        assert hidden_radon.exists()
