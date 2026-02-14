from __future__ import annotations

import os
from typing import Dict

from .base import RemoteProvider
from .dropbox_provider import DropboxProvider


def build_providers() -> Dict[str, RemoteProvider]:
    providers: Dict[str, RemoteProvider] = {}
    token = os.environ.get("DROPBOX_ACCESS_TOKEN", "")
    if token:
        providers["dropbox"] = DropboxProvider(token)
    return providers
