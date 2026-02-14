from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import List, Optional, Tuple

import dropbox
from dropbox.files import FileMetadata

from ..models import RemoteFile
from .base import RemoteProvider


def _as_utc(dt) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class DropboxProvider(RemoteProvider):
    """Dropbox provider using the official Dropbox Python SDK."""

    def __init__(self, access_token: str) -> None:
        if not access_token:
            raise RuntimeError(
                "Missing Dropbox access token. Set DROPBOX_ACCESS_TOKEN in the environment."
            )
        self._dbx = dropbox.Dropbox(access_token)

    def list_files(self, folder: str) -> List[RemoteFile]:
        folder = folder.strip()
        if folder.startswith("http"):
            return self._list_shared_link(folder)
        return self._list_path(folder)

    def _list_shared_link(self, shared_link_url: str) -> List[RemoteFile]:
        shared_link = dropbox.files.SharedLink(url=shared_link_url)
        res = self._dbx.files_list_folder(path="", shared_link=shared_link)
        files: List[RemoteFile] = []
        files.extend(self._entries_to_files(res.entries, shared_link_url=shared_link_url))
        while res.has_more:
            res = self._dbx.files_list_folder_continue(res.cursor)
            files.extend(self._entries_to_files(res.entries, shared_link_url=shared_link_url))
        return files

    def _list_path(self, path: str) -> List[RemoteFile]:
        res = self._dbx.files_list_folder(path=path)
        files: List[RemoteFile] = []
        files.extend(self._entries_to_files(res.entries, shared_link_url=None))
        while res.has_more:
            res = self._dbx.files_list_folder_continue(res.cursor)
            files.extend(self._entries_to_files(res.entries, shared_link_url=None))
        return files

    def _entries_to_files(self, entries, *, shared_link_url: str | None) -> List[RemoteFile]:
        out: List[RemoteFile] = []
        for e in entries:
            if isinstance(e, FileMetadata):
                out.append(
                    RemoteFile(
                        provider="dropbox",
                        name=e.name,
                        size_bytes=int(e.size),
                        modified=_as_utc(getattr(e, "client_modified", None)),
                        shared_link_url=shared_link_url,
                        path_lower=str(e.path_lower or e.path_display or ""),
                    )
                )
        return out

    def download_bytes(self, *, shared_link_url: str | None, path_lower: str) -> Tuple[bytes, str]:
        if shared_link_url:
            md, resp = self._dbx.files_download(
                path=path_lower,
                shared_link=dropbox.files.SharedLink(url=shared_link_url),
            )
        else:
            md, resp = self._dbx.files_download(path=path_lower)
        data = resp.content
        name = getattr(md, "name", os.path.basename(path_lower) or "download.bin")
        return data, name
