"""Tests for deterministic provenance hashing helpers."""

from __future__ import annotations

from kymflow.core.kym_dataset.provenance import params_hash, stable_json_dumps


def test_stable_json_dumps_order_independent_for_dict_keys() -> None:
    a = {"b": 2, "a": 1, "nested": {"z": 9, "x": [3, 2, 1]}}
    b = {"nested": {"x": [3, 2, 1], "z": 9}, "a": 1, "b": 2}
    assert stable_json_dumps(a) == stable_json_dumps(b)


def test_params_hash_deterministic_for_equivalent_dicts() -> None:
    p1 = {"threshold": 0.2, "min_gap_s": 0.5, "event_type": "drop"}
    p2 = {"event_type": "drop", "min_gap_s": 0.5, "threshold": 0.2}
    assert params_hash(p1) == params_hash(p2)
