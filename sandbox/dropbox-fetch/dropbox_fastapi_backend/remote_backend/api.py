from __future__ import annotations

import mimetypes
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .id_codec import decode_file_id, encode_file_id
from .models import RemoteFile
from .providers.registry import build_providers


app = FastAPI(title="Remote File Backend", version="0.1.0")
_PROVIDERS = build_providers()


class ListRequest(BaseModel):
    provider: str = Field(..., description="Provider name, e.g. 'dropbox'")
    folder: str = Field(..., description="Folder ref: shared link URL or provider path")


class FileRow(BaseModel):
    id: str
    name: str
    size_bytes: int
    modified: Optional[str] = None  # ISO8601 UTC


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/api/remote/list")
def list_remote(req: ListRequest) -> Dict[str, Any]:
    provider = _PROVIDERS.get(req.provider)
    if provider is None:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unknown or unconfigured provider '{req.provider}'. "
                f"Configured: {sorted(_PROVIDERS.keys())}. "
                f"For Dropbox set DROPBOX_ACCESS_TOKEN."
            ),
        )

    files: List[RemoteFile] = provider.list_files(req.folder)
    rows: List[FileRow] = []
    for f in files:
        fid = encode_file_id(f)
        rows.append(
            FileRow(
                id=fid,
                name=f.name,
                size_bytes=f.size_bytes,
                modified=f.modified.isoformat() if f.modified else None,
            )
        )
    return {"provider": req.provider, "files": [r.model_dump() for r in rows]}


@app.get("/api/remote/file/{file_id}")
def download_remote(file_id: str):
    d = decode_file_id(file_id)
    provider_name = d.get("provider")
    provider = _PROVIDERS.get(provider_name)
    if provider is None:
        raise HTTPException(status_code=400, detail=f"Provider '{provider_name}' not configured")

    shared_link_url = d.get("shared_link_url")
    path_lower = d.get("path_lower") or ""
    if not path_lower:
        raise HTTPException(status_code=400, detail="Invalid file id: missing path_lower")

    data, filename = provider.download_bytes(shared_link_url=shared_link_url, path_lower=path_lower)

    ctype, _ = mimetypes.guess_type(filename)
    ctype = ctype or "application/octet-stream"

    def _iter_chunks(b: bytes, chunk_size: int = 1024 * 256):
        for i in range(0, len(b), chunk_size):
            yield b[i : i + chunk_size]

    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(_iter_chunks(data), media_type=ctype, headers=headers)


class StatsRequest(BaseModel):
    file_id: str


@app.post("/api/tif/stats")
def tif_stats(req: StatsRequest) -> Dict[str, Any]:
    try:
        import numpy as np
        import tifffile
    except Exception as e:
        raise HTTPException(status_code=500, detail="Missing tifffile/numpy in backend environment") from e

    d = decode_file_id(req.file_id)
    provider_name = d.get("provider")
    provider = _PROVIDERS.get(provider_name)
    if provider is None:
        raise HTTPException(status_code=400, detail=f"Provider '{provider_name}' not configured")

    data, filename = provider.download_bytes(
        shared_link_url=d.get("shared_link_url"),
        path_lower=d.get("path_lower") or "",
    )

    import io
    arr = tifffile.imread(io.BytesIO(data))
    shape = list(arr.shape)
    dtype = str(arr.dtype)
    vmin = float(np.nanmin(arr))
    vmax = float(np.nanmax(arr))

    return {"name": filename, "shape": shape, "dtype": dtype, "min": vmin, "max": vmax}
