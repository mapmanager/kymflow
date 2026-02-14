from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Tuple

from ..models import RemoteFile


class RemoteProvider(ABC):
    """Interface for remote file providers."""

    @abstractmethod
    def list_files(self, folder: str) -> List[RemoteFile]:
        raise NotImplementedError

    @abstractmethod
    def download_bytes(self, *, shared_link_url: str | None, path_lower: str) -> Tuple[bytes, str]:
        raise NotImplementedError
