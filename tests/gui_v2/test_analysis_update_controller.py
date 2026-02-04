"""Tests for AnalysisUpdateController."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.controllers.analysis_update_controller import AnalysisUpdateController
from kymflow.gui_v2.events import AnalysisUpdate, SelectionOrigin
from kymflow.gui_v2.state import AppState


def test_analysis_update_controller_updates_kymanalysis(bus: EventBus, app_state: AppState) -> None:
    """Test that AnalysisUpdateController updates kymanalysis and calls app_state.update_analysis()."""
    controller = AnalysisUpdateController(app_state, bus)
    
    # Create mock file with kymanalysis
    mock_file = MagicMock()
    mock_kym_analysis = MagicMock()
    mock_file.get_kym_analysis.return_value = mock_kym_analysis
    
    # Track calls to update_analysis
    update_analysis_calls = []
    original_update_analysis = app_state.update_analysis
    
    def track_update_analysis(kym_file):
        update_analysis_calls.append(kym_file)
        return original_update_analysis(kym_file)
    
    app_state.update_analysis = track_update_analysis
    
    # Emit AnalysisUpdate intent event
    intent_event = AnalysisUpdate(
        file=mock_file,
        fields={"accepted": False},
        origin=SelectionOrigin.FILE_TABLE,
        phase="intent",
    )
    bus.emit(intent_event)
    
    # Verify kymanalysis.set_accepted was called
    mock_kym_analysis.set_accepted.assert_called_once_with(False)
    
    # Verify app_state.update_analysis was called
    assert len(update_analysis_calls) == 1
    assert update_analysis_calls[0] == mock_file
    
    # Restore original method
    app_state.update_analysis = original_update_analysis


def test_analysis_update_controller_updates_accepted_true(bus: EventBus, app_state: AppState) -> None:
    """Test that AnalysisUpdateController handles accepted=True correctly."""
    controller = AnalysisUpdateController(app_state, bus)
    
    mock_file = MagicMock()
    mock_kym_analysis = MagicMock()
    mock_file.get_kym_analysis.return_value = mock_kym_analysis
    
    # Emit AnalysisUpdate with accepted=True
    intent_event = AnalysisUpdate(
        file=mock_file,
        fields={"accepted": True},
        origin=SelectionOrigin.FILE_TABLE,
        phase="intent",
    )
    bus.emit(intent_event)
    
    # Verify set_accepted was called with True
    mock_kym_analysis.set_accepted.assert_called_once_with(True)


def test_analysis_update_controller_handles_multiple_fields(bus: EventBus, app_state: AppState) -> None:
    """Test that AnalysisUpdateController can handle multiple fields (future extensibility)."""
    controller = AnalysisUpdateController(app_state, bus)
    
    mock_file = MagicMock()
    mock_kym_analysis = MagicMock()
    mock_file.get_kym_analysis.return_value = mock_kym_analysis
    
    # Emit AnalysisUpdate with accepted field
    intent_event = AnalysisUpdate(
        file=mock_file,
        fields={"accepted": False},
        origin=SelectionOrigin.FILE_TABLE,
        phase="intent",
    )
    bus.emit(intent_event)
    
    # Verify set_accepted was called
    mock_kym_analysis.set_accepted.assert_called_once_with(False)
