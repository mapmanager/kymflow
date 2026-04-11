#
# Build image locally:
#   docker build -t kymflow:latest .
#
# Run locally and open in browser:
#   docker run --rm -p 8080:8080 kymflow:latest
#   then visit http://localhost:8080
#
# Deploy on Raspberry Pi:
#   docker build -t kymflow:latest .
#   docker run -d --name kymflow --restart unless-stopped -p 8080:8080 kymflow:latest
#   then verify it is reachable in a browser through your Cloudflare tunnel/domain
#

FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HOST=0.0.0.0
ENV PORT=8080

# Force web behavior
ENV KYMFLOW_GUI_NATIVE=0
ENV KYMFLOW_GUI_RELOAD=0
ENV KYMFLOW_REMOTE=1
ENV KYMFLOW_DEFAULT_PATH=/app/tests/data
ENV KYMFLOW_DEFAULT_DEPTH=3

COPY pyproject.toml uv.lock ./
COPY README* ./
COPY LICENSE* ./
COPY src ./src
COPY tests/data ./tests/data

ARG DEV_MODE=false
# Git ref for nicewidgets (e.g. main). Override: docker compose build --build-arg NICEWIDGETS_REF=v0.1.0
ARG NICEWIDGETS_REF=main

RUN uv sync --frozen $(if [ "$DEV_MODE" != "true" ]; then echo "--no-editable"; fi) && \
    uv pip install "nicewidgets[no_mpl] @ git+https://github.com/mapmanager/nicewidgets@${NICEWIDGETS_REF}"

EXPOSE 8080

CMD ["uv", "run", "python", "-m", "kymflow.gui_v2.app"]