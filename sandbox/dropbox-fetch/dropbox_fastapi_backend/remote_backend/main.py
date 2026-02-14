from __future__ import annotations

import os
import uvicorn


def main() -> None:
    host = os.environ.get("REMOTE_BACKEND_HOST", "127.0.0.1")
    port = int(os.environ.get("REMOTE_BACKEND_PORT", "8001"))
    uvicorn.run("remote_backend.api:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
