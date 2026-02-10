"""Tests for FileTableView AnalysisUpdate handling."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.events import AnalysisUpdate, DetectEvents, MetadataUpdate, SelectionOrigin
from kymflow.gui_v2.events_state import AnalysisCompleted, FileListChanged  # noqa: F401
from kymflow.gui_v2.views.file_table_bindings import FileTableBindings
from kymflow.gui_v2.views.file_table_view import FileTableView


@pytest.fixture
def mock_app_context():
    """Create a mock AppContext for testing."""
    mock_context = MagicMock()
    mock_app_config = MagicMock()
    mock_app_config.get_blinded.return_value = False
    mock_context.app_config = mock_app_config
    return mock_context


@pytest.fixture
def sample_kym_file() -> KymImage:
    """Create a sample KymImage for testing."""
    import tempfile
    from pathlib import Path
    import numpy as np
    import tifffile
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create nested directory structure to ensure parent3 exists
        tmp_path = Path(tmpdir)
        subdir = tmp_path / "a" / "b" / "c"
        subdir.mkdir(parents=True)
        test_file = subdir / "test.tif"
        test_image = np.zeros((100, 200), dtype=np.uint16)
        tifffile.imwrite(test_file, test_image)

        kym_file = KymImage(test_file, load_image=True)
        return kym_file


def test_file_table_view_emits_analysis_update_for_accepted(sample_kym_file: KymImage, mock_app_context) -> None:
    """Test that FileTableView emits AnalysisUpdate when accepted checkbox is toggled."""
    emitted_events = []
    
    def capture_event(event):
        emitted_events.append(event)
    
    view = FileTableView(
        mock_app_context,
        on_selected=lambda e: None,
        on_analysis_update=capture_event,
    )
    
    # Set up files
    view.set_files([sample_kym_file])
    
    # Simulate cell edit for accepted field
    row_data = sample_kym_file.getRowDict()
    view._on_cell_edited(
        row_index=0,
        field="accepted",
        old_value=True,
        new_value=False,
        row_data=row_data,
    )
    
    # Verify AnalysisUpdate was emitted
    assert len(emitted_events) == 1
    event = emitted_events[0]
    assert isinstance(event, AnalysisUpdate)
    assert event.file == sample_kym_file
    assert event.fields == {"accepted": False}
    assert event.origin == SelectionOrigin.FILE_TABLE
    assert event.phase == "intent"


def test_file_table_view_handles_accepted_bool_conversion(sample_kym_file: KymImage, mock_app_context) -> None:
    """Test that FileTableView correctly converts various input types to bool for accepted."""
    emitted_events = []
    
    def capture_event(event):
        emitted_events.append(event)
    
    view = FileTableView(
        mock_app_context,
        on_selected=lambda e: None,
        on_analysis_update=capture_event,
    )
    
    view.set_files([sample_kym_file])
    row_data = sample_kym_file.getRowDict()
    
    # Test string "true"
    view._on_cell_edited(0, "accepted", True, "true", row_data)
    assert emitted_events[-1].fields["accepted"] is True
    
    # Test string "false"
    view._on_cell_edited(0, "accepted", True, "false", row_data)
    assert emitted_events[-1].fields["accepted"] is False
    
    # Test actual bool False
    view._on_cell_edited(0, "accepted", True, False, row_data)
    assert emitted_events[-1].fields["accepted"] is False
    
    # Test actual bool True
    view._on_cell_edited(0, "accepted", False, True, row_data)
    assert emitted_events[-1].fields["accepted"] is True


def test_file_table_view_does_not_emit_when_callback_missing(sample_kym_file: KymImage, mock_app_context) -> None:
    """Test that FileTableView does not crash when on_analysis_update callback is None."""
    view = FileTableView(
        mock_app_context,
        on_selected=lambda e: None,
        on_analysis_update=None,  # No callback
    )
    
    view.set_files([sample_kym_file])
    row_data = sample_kym_file.getRowDict()
    
    # Should not crash when callback is None
    view._on_cell_edited(
        row_index=0,
        field="accepted",
        old_value=True,
        new_value=False,
        row_data=row_data,
    )


def test_file_table_view_includes_accepted_in_row_dict(sample_kym_file: KymImage, mock_app_context) -> None:
    """Test that accepted field is included in getRowDict() and displayed in table."""
    view = FileTableView(mock_app_context, on_selected=lambda e: None)
    
    # Set files and get rows
    view.set_files([sample_kym_file])
    
    # The accepted field should be in the row dict
    row_dict = sample_kym_file.getRowDict()
    assert "accepted" in row_dict
    assert isinstance(row_dict["accepted"], bool)
    
    # Default should be True
    assert row_dict["accepted"] is True
    
    # Change accepted and verify it updates
    sample_kym_file.get_kym_analysis().set_accepted(False)
    row_dict = sample_kym_file.getRowDict()
    assert row_dict["accepted"] is False


def test_file_table_view_blinded_displays_blinded_data(sample_kym_file: KymImage) -> None:
    """Test that FileTableView displays blinded data when blinded=True."""
    from unittest.mock import MagicMock
    
    # Create mock app context with blinded=True
    mock_context = MagicMock()
    mock_app_config = MagicMock()
    mock_app_config.get_blinded.return_value = True
    mock_context.app_config = mock_app_config
    
    view = FileTableView(
        mock_context,
        on_selected=lambda e: None,
    )
    
    # Set _blind_index on file (simulating AcqImageList behavior)
    sample_kym_file._blind_index = 0
    
    # Set files - should use blinded data
    view.set_files([sample_kym_file])
    
    # Check that pending_rows has blinded data
    assert len(view._pending_rows) == 1
    row = view._pending_rows[0]
    
    # File Name should be blinded
    assert row["File Name"] == "File 1"
    
    # Both Grandparent Folder and Parent Folder should be blinded if they exist
    if row["Grandparent Folder"] is not None:
        assert row["Grandparent Folder"] == "Blinded"
    if row["Parent Folder"] is not None:
        assert row["Parent Folder"] == "Blinded"
    
    # Path should remain unchanged (for internal use)
    assert row["path"] is not None
    
    # Verify the original file name is different (if path exists)
    if sample_kym_file.path:
        assert row["File Name"] != sample_kym_file.path.name


def test_file_table_view_blinded_false_displays_real_data(sample_kym_file: KymImage) -> None:
    """Test that FileTableView displays real data when blinded=False."""
    from unittest.mock import MagicMock
    
    # Create mock app context with blinded=False
    mock_context = MagicMock()
    mock_app_config = MagicMock()
    mock_app_config.get_blinded.return_value = False
    mock_context.app_config = mock_app_config
    
    view = FileTableView(
        mock_context,
        on_selected=lambda e: None,
    )
    
    # Set files - should use real data
    view.set_files([sample_kym_file])
    
    # Check that pending_rows has real data
    assert len(view._pending_rows) == 1
    row = view._pending_rows[0]
    
    # File Name should be real
    assert row["File Name"] == sample_kym_file.path.name
    
    # Grandparent Folder should be real (if path has grandparent)
    if sample_kym_file.path and len(sample_kym_file.path.parent.parts) > 0:
        # Grandparent folder might be None if path is shallow, but shouldn't be "Blinded"
        assert row["Grandparent Folder"] != "Blinded"


def test_file_table_bindings_metadata_update_uses_row_level_update(
    sample_kym_file: KymImage, mock_app_context
) -> None:
    """MetadataUpdate(state) for a single file should prefer row-level update over full refresh."""
    bus = EventBus("test-client")
    view = FileTableView(mock_app_context, on_selected=lambda e: None)

    # Prepare a real KymImage and render the grid so that _grid is initialized
    kym_file = sample_kym_file
    mock_app_context.app_config.get_blinded.return_value = False

    view.set_files([kym_file])
    view.render()

    bindings = FileTableBindings(bus, view, app_state=None)

    # Spy on view helpers
    view.update_row_for_file = MagicMock()
    bindings._refresh_rows_preserve_selection = MagicMock()

    event = MetadataUpdate(
        file=kym_file,
        metadata_type="experimental",
        fields={"note": "new note"},
        origin=SelectionOrigin.EXTERNAL,
        phase="state",
    )

    bindings._on_metadata_update(event)

    # Row-level helper should be used; full refresh must not be called
    view.update_row_for_file.assert_called_once_with(kym_file)
    bindings._refresh_rows_preserve_selection.assert_not_called()


def test_file_table_bindings_metadata_update_falls_back_when_file_missing(mock_app_context) -> None:
    """If the file is not present in the table, bindings should fall back to full refresh."""
    bus = EventBus("test-client")
    view = FileTableView(mock_app_context, on_selected=lambda e: None)

    # Render without setting files so _files_by_path is empty
    view.render()

    bindings = FileTableBindings(bus, view, app_state=None)

    view.update_row_for_file = MagicMock()
    bindings._refresh_rows_preserve_selection = MagicMock()

    kym_file = MagicMock(spec=KymImage)
    kym_file.path = "/tmp/other.tif"

    event = MetadataUpdate(
        file=kym_file,
        metadata_type="experimental",
        fields={"note": "new note"},
        origin=SelectionOrigin.EXTERNAL,
        phase="state",
    )

    bindings._on_metadata_update(event)

    view.update_row_for_file.assert_not_called()
    bindings._refresh_rows_preserve_selection.assert_called_once()


def test_file_table_bindings_analysis_update_uses_row_level_update(
    sample_kym_file: KymImage, mock_app_context
) -> None:
    """AnalysisUpdate(state) for a single file should prefer row-level update over full refresh."""
    bus = EventBus("test-client")
    view = FileTableView(mock_app_context, on_selected=lambda e: None)

    # Prepare a real KymImage and render the grid so that _grid is initialized
    kym_file = sample_kym_file
    mock_app_context.app_config.get_blinded.return_value = False

    view.set_files([kym_file])
    view.render()

    bindings = FileTableBindings(bus, view, app_state=None)

    # Spy on view helpers
    view.update_row_for_file = MagicMock()
    bindings._refresh_rows_preserve_selection = MagicMock()

    event = AnalysisUpdate(
        file=kym_file,
        fields={"accepted": True},
        origin=SelectionOrigin.EXTERNAL,
        phase="state",
    )

    bindings._on_analysis_update(event)

    # Row-level helper should be used; full refresh must not be called
    view.update_row_for_file.assert_called_once_with(kym_file)
    bindings._refresh_rows_preserve_selection.assert_not_called()


def test_file_table_bindings_analysis_update_falls_back_when_grid_none(
    sample_kym_file: KymImage, mock_app_context
) -> None:
    """If the grid is not yet rendered, bindings should fall back to full refresh."""
    bus = EventBus("test-client")
    view = FileTableView(mock_app_context, on_selected=lambda e: None)

    # Set files but don't render, so _grid is None
    view.set_files([sample_kym_file])
    # view.render() is NOT called

    bindings = FileTableBindings(bus, view, app_state=None)

    view.update_row_for_file = MagicMock()
    bindings._refresh_rows_preserve_selection = MagicMock()

    event = AnalysisUpdate(
        file=sample_kym_file,
        fields={"accepted": True},
        origin=SelectionOrigin.EXTERNAL,
        phase="state",
    )

    bindings._on_analysis_update(event)

    view.update_row_for_file.assert_not_called()
    bindings._refresh_rows_preserve_selection.assert_called_once()


def test_file_table_bindings_analysis_completed_uses_row_level_update(
    sample_kym_file: KymImage, mock_app_context
) -> None:
    """AnalysisCompleted(state) for a single file should prefer row-level update over full refresh."""
    bus = EventBus("test-client")
    view = FileTableView(mock_app_context, on_selected=lambda e: None)

    # Prepare a real KymImage and render the grid so that _grid is initialized
    kym_file = sample_kym_file
    mock_app_context.app_config.get_blinded.return_value = False

    view.set_files([kym_file])
    view.render()

    bindings = FileTableBindings(bus, view, app_state=None)

    # Spy on view helpers
    view.update_row_for_file = MagicMock()
    bindings._refresh_rows_preserve_selection = MagicMock()

    event = AnalysisCompleted(
        file=kym_file,
        roi_id=1,
        success=True,
    )

    bindings._on_analysis_completed(event)

    # Row-level helper should be used; full refresh must not be called
    view.update_row_for_file.assert_called_once_with(kym_file)
    bindings._refresh_rows_preserve_selection.assert_not_called()


def test_file_table_bindings_analysis_completed_skips_on_failure(
    sample_kym_file: KymImage, mock_app_context
) -> None:
    """AnalysisCompleted with success=False should skip update entirely."""
    bus = EventBus("test-client")
    view = FileTableView(mock_app_context, on_selected=lambda e: None)

    view.set_files([sample_kym_file])
    view.render()

    bindings = FileTableBindings(bus, view, app_state=None)

    view.update_row_for_file = MagicMock()
    bindings._refresh_rows_preserve_selection = MagicMock()

    event = AnalysisCompleted(
        file=sample_kym_file,
        roi_id=1,
        success=False,
    )

    bindings._on_analysis_completed(event)

    # No update should be called when success=False
    view.update_row_for_file.assert_not_called()
    bindings._refresh_rows_preserve_selection.assert_not_called()


def test_file_table_bindings_detect_events_single_file_row_level(
    sample_kym_file: KymImage, mock_app_context
) -> None:
    """DetectEvents(state) for a single file should prefer row-level update over full refresh."""
    bus = EventBus("test-client")
    view = FileTableView(mock_app_context, on_selected=lambda e: None)

    # Prepare a real KymImage and render the grid so that _grid is initialized
    kym_file = sample_kym_file
    mock_app_context.app_config.get_blinded.return_value = False

    view.set_files([kym_file])
    view.render()

    bindings = FileTableBindings(bus, view, app_state=None)

    # Spy on view helpers
    view.update_row_for_file = MagicMock()
    bindings._refresh_rows_preserve_selection = MagicMock()

    event = DetectEvents(
        path=str(kym_file.path),
        roi_id=1,
        phase="state",
    )

    bindings._on_detect_events(event)

    # Row-level helper should be used; full refresh must not be called
    view.update_row_for_file.assert_called_once_with(kym_file)
    bindings._refresh_rows_preserve_selection.assert_not_called()


def test_file_table_bindings_detect_events_batch_fallback(mock_app_context) -> None:
    """DetectEvents with path=None (batch operation) should fall back to full refresh."""
    bus = EventBus("test-client")
    view = FileTableView(mock_app_context, on_selected=lambda e: None)

    view.render()

    bindings = FileTableBindings(bus, view, app_state=None)

    view.update_row_for_file = MagicMock()
    bindings._refresh_rows_preserve_selection = MagicMock()

    event = DetectEvents(
        path=None,  # Batch operation
        roi_id=None,
        phase="state",
    )

    bindings._on_detect_events(event)

    view.update_row_for_file.assert_not_called()
    bindings._refresh_rows_preserve_selection.assert_called_once()


def test_file_table_bindings_detect_events_path_not_in_table(
    sample_kym_file: KymImage, mock_app_context
) -> None:
    """If the path is not in the table, bindings should fall back to full refresh."""
    bus = EventBus("test-client")
    view = FileTableView(mock_app_context, on_selected=lambda e: None)

    # Set files with one file, but event has different path
    view.set_files([sample_kym_file])
    view.render()

    bindings = FileTableBindings(bus, view, app_state=None)

    view.update_row_for_file = MagicMock()
    bindings._refresh_rows_preserve_selection = MagicMock()

    # Event with path that doesn't match any file in the table
    event = DetectEvents(
        path="/tmp/nonexistent/path.tif",
        roi_id=1,
        phase="state",
    )

    bindings._on_detect_events(event)

    view.update_row_for_file.assert_not_called()
    bindings._refresh_rows_preserve_selection.assert_called_once()
