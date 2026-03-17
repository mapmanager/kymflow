"""Tests for FooterView and footer status level styling."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from kymflow.gui_v2.views.footer_view import (
    FooterView,
    FooterStatusLevel,
    STATUS_LABEL_BASE_CLASSES,
    STATUS_LEVEL_CLASSES,
)


def test_status_level_classes_keys() -> None:
    """STATUS_LEVEL_CLASSES includes all levels used by FooterStatusMessage and 'none'."""
    expected = {"none", "info", "success", "warning", "error"}
    assert set(STATUS_LEVEL_CLASSES.keys()) == expected


def test_status_level_warning_has_styling() -> None:
    """Warning level has non-empty classes for visibility."""
    assert STATUS_LEVEL_CLASSES["warning"] != ""
    assert "yellow" in STATUS_LEVEL_CLASSES["warning"].lower()


def test_status_level_error_has_styling() -> None:
    """Error level has non-empty classes for visibility."""
    assert STATUS_LEVEL_CLASSES["error"] != ""
    assert "red" in STATUS_LEVEL_CLASSES["error"].lower()


def test_status_level_none_info_success_clear_styling() -> None:
    """none, info, success have no extra classes so previous warning/error is cleared."""
    for level in ("none", "info", "success"):
        assert STATUS_LEVEL_CLASSES[level] == ""


def test_set_last_event_updates_text_and_classes() -> None:
    """set_last_event sets label text and calls classes(replace=...) with level styling."""
    view = FooterView()
    mock_label = MagicMock()
    view._status_label = mock_label

    view.set_last_event("Hello", level="info")
    assert mock_label.text == "Hello"
    mock_label.classes.assert_called_once()
    call_kw = mock_label.classes.call_args[1]
    assert "replace" in call_kw
    assert STATUS_LABEL_BASE_CLASSES in call_kw["replace"]
    assert "yellow" not in call_kw["replace"].lower()
    assert "red" not in call_kw["replace"].lower()


def test_set_last_event_warning_applies_warning_classes() -> None:
    """set_last_event with level=warning applies warning classes."""
    view = FooterView()
    mock_label = MagicMock()
    view._status_label = mock_label

    view.set_last_event("Warning message", level="warning")
    assert mock_label.text == "Warning message"
    mock_label.classes.assert_called_once()
    call_kw = mock_label.classes.call_args[1]
    assert STATUS_LEVEL_CLASSES["warning"] in call_kw["replace"]


def test_set_last_event_error_applies_error_classes() -> None:
    """set_last_event with level=error applies error classes."""
    view = FooterView()
    mock_label = MagicMock()
    view._status_label = mock_label

    view.set_last_event("Error message", level="error")
    assert mock_label.text == "Error message"
    mock_label.classes.assert_called_once()
    call_kw = mock_label.classes.call_args[1]
    assert STATUS_LEVEL_CLASSES["error"] in call_kw["replace"]


def test_set_last_event_none_clears_special_styling() -> None:
    """set_last_event with level=none uses only base classes (no warning/error)."""
    view = FooterView()
    mock_label = MagicMock()
    view._status_label = mock_label

    view.set_last_event("Done", level="none")
    call_kw = mock_label.classes.call_args[1]
    replaced = call_kw["replace"]
    assert STATUS_LABEL_BASE_CLASSES in replaced
    assert STATUS_LEVEL_CLASSES["warning"] not in replaced or "warning" not in replaced
    assert STATUS_LEVEL_CLASSES["error"] not in replaced or "error" not in replaced


def test_set_last_event_no_op_when_status_label_none() -> None:
    """set_last_event does nothing when _status_label is None."""
    view = FooterView()
    view._status_label = None
    view.set_last_event("No crash", level="warning")  # should not raise
