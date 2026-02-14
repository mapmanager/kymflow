from __future__ import annotations

import base64
import json
from dataclasses import asdict
from typing import Any, Dict

from .models import RemoteFile


def _b64url_encode(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("ascii").rstrip("=")


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def encode_file_id(rf: RemoteFile) -> str:
    """Encode enough information to re-fetch the file without server-side session state."""
    d = asdict(rf)
    if d.get("modified") is not None:
        d["modified"] = d["modified"].isoformat()
    payload = json.dumps(d, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return _b64url_encode(payload)


def decode_file_id(file_id: str) -> Dict[str, Any]:
    """Decode a file id back to a dict (provider-specific download args)."""
    raw = _b64url_decode(file_id)
    d: Dict[str, Any] = json.loads(raw.decode("utf-8"))
    return d
