from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Optional


ProviderName = Literal["dropbox"]


@dataclass(frozen=True)
class RemoteFile:
    """A single remote file entry."""
    provider: ProviderName
    name: str
    size_bytes: int
    modified: Optional[datetime]

    # For re-fetching:
    # - Dropbox: either (shared_link_url + path_lower) or (path_lower) for auth'd paths
    shared_link_url: Optional[str]
    path_lower: str  # dropbox path within account or within shared link
