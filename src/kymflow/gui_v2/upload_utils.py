# upload_utils.py
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any


def normalize_uploaded_file(upload: Any) -> Path:
    """
    Normalize a NiceGUI upload (small or large) to a filesystem Path.

    - LargeFileUpload: returns the existing temp file path
    - SmallFileUpload: writes bytes to a temp file and returns its path

    The caller owns the returned file for the duration of processing.
    """
    # Case 1: Large file upload (already on disk)
    path = getattr(upload, "_path", None)
    if path is not None:
        return Path(path)

    # Case 2: Small file upload (in-memory)
    # We must persist it to disk ourselves
    suffix = ""
    name = getattr(upload, "name", None)
    if isinstance(name, str) and "." in name:
        suffix = "." + name.split(".")[-1]

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(upload.read())
        return Path(tmp.name)