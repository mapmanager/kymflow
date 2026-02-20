"""Provenance helpers for deterministic parameter hashing."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def stable_json_dumps(obj: object) -> str:
    """Serialize an object to deterministic JSON text.

    Args:
        obj: JSON-compatible object.

    Returns:
        Stable JSON string with sorted keys and compact separators.
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def params_hash(params: dict[str, Any]) -> str:
    """Compute SHA-256 hash for a params dictionary.

    Args:
        params: Parameter dictionary.

    Returns:
        Hex-encoded SHA-256 digest.
    """
    payload = stable_json_dumps(params).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
