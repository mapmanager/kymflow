# Filename: tests/conftest.py
"""Pytest helpers for optional dependencies."""

from __future__ import annotations

from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)

import importlib.util


def has_module(name: str) -> bool:
    """Return True if a module is importable."""
    return importlib.util.find_spec(name) is not None
