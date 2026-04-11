#
# Production build (for deployment):
#   docker build -t kymflow:latest .
#
# Development build (editable install, picks up local src changes):
#   docker build --build-arg DEV_MODE=true -t kymflow:dev .
#
# Run container:
#   docker run --rm -p 8080:8080 kymflow:latest
#
# Run dev container with volume mount (for live code changes):
#   docker run --rm -p 8080:8080 -v $(pwd)/src:/app/src kymflow:dev
#
# Run the container locally
#   docker run --rm -p 8080:8080 kymflow:latest

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

RUN uv sync --frozen $(if [ "$DEV_MODE" != "true" ]; then echo "--no-editable"; fi) && \
    uv pip install "nicewidgets[no_mpl] @ git+https://github.com/mapmanager/nicewidgets@swap-to-nicewidget-image-line-widgets"

    # uv pip install "nicewidgets[no_mpl] @ git+https://github.com/mapmanager/nicewidgets"

EXPOSE 8080

CMD ["uv", "run", "python", "-m", "kymflow.gui_v2.app"]