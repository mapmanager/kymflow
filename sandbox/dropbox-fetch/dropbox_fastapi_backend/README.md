# Remote Dropbox Backend (FastAPI)

## Install (local)
```bash
uv pip install fastapi uvicorn dropbox pydantic
# optional for /api/tif/stats
uv pip install numpy tifffile
```

## Run
```bash
export DROPBOX_ACCESS_TOKEN="...your token..."
uv run python -m remote_backend.main
```

Health:
- GET http://127.0.0.1:8001/health

List:
- POST http://127.0.0.1:8001/api/remote/list
  body: {"provider":"dropbox","folder":"<shared folder link or /path>"}

Download:
- GET http://127.0.0.1:8001/api/remote/file/{file_id}

Optional stats (keeps frontend thin):
- POST http://127.0.0.1:8001/api/tif/stats
  body: {"file_id":"..."}
