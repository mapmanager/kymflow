"""Tests for metadata loading, saving, and field handling."""

from __future__ import annotations

from pathlib import Path

import pytest

from kymflow.core.image_loaders.metadata import ExperimentMetadata


def test_experiment_metadata_from_dict() -> None:
    """Test creating ExperimentMetadata from dictionary."""
    payload = {
        "species": "mouse",
        "region": "cortex",
        "cell_type": "neuron",
        "depth": 100.5,
        "branch_order": 2,
        "direction": "anterograde",
        "sex": "M",
        "genotype": "WT",
        "condition": "control",
        "note": "Test sample",
    }
    meta = ExperimentMetadata.from_dict(payload)
    assert meta.species == "mouse"
    assert meta.region == "cortex"
    assert meta.depth == 100.5
    assert meta.branch_order == 2
    assert meta.direction == "anterograde"


def test_experiment_metadata_unknown_fields_ignored() -> None:
    """Test that unknown fields are ignored when loading from dict."""
    payload = {
        "species": "mouse",
        "unknown_field": "should be ignored",
    }
    meta = ExperimentMetadata.from_dict(payload)
    assert meta.species == "mouse"
    # Unknown field should not cause error


def test_experiment_metadata_to_dict() -> None:
    """Test converting ExperimentMetadata to dictionary."""
    meta = ExperimentMetadata(
        species="mouse",
        region="cortex",
        note="Test",
    )
    d = meta.to_dict()
    assert d["species"] == "mouse"
    assert d["region"] == "cortex"
    assert d["note"] == "Test"
    # Check abbreviated keys
    assert "acq_date" in d
    assert "acq_time" in d

