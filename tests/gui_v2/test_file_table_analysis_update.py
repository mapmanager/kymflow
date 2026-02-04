"""Tests for FileTableView AnalysisUpdate handling."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.events import AnalysisUpdate, SelectionOrigin
from kymflow.gui_v2.views.file_table_view import FileTableView


@pytest.fixture
def sample_kym_file() -> KymImage:
    """Create a sample KymImage for testing."""
    import tempfile
    from pathlib import Path
    import numpy as np
    import tifffile
    
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.tif"
        test_image = np.zeros((100, 200), dtype=np.uint16)
        tifffile.imwrite(test_file, test_image)

        kym_file = KymImage(test_file, load_image=True)
        return kym_file


def test_file_table_view_emits_analysis_update_for_accepted(sample_kym_file: KymImage) -> None:
    """Test that FileTableView emits AnalysisUpdate when accepted checkbox is toggled."""
    emitted_events = []
    
    def capture_event(event):
        emitted_events.append(event)
    
    view = FileTableView(
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


def test_file_table_view_handles_accepted_bool_conversion(sample_kym_file: KymImage) -> None:
    """Test that FileTableView correctly converts various input types to bool for accepted."""
    emitted_events = []
    
    def capture_event(event):
        emitted_events.append(event)
    
    view = FileTableView(
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


def test_file_table_view_does_not_emit_when_callback_missing(sample_kym_file: KymImage) -> None:
    """Test that FileTableView does not crash when on_analysis_update callback is None."""
    view = FileTableView(
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


def test_file_table_view_includes_accepted_in_row_dict(sample_kym_file: KymImage) -> None:
    """Test that accepted field is included in getRowDict() and displayed in table."""
    view = FileTableView(on_selected=lambda e: None)
    
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
