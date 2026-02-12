# Dockerfile
# Render deployment: run NiceGUI in web mode (native=False), bind to $HOST:$PORT
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

FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy metadata first for caching
COPY pyproject.toml README.md LICENSE* ./

# Copy source
COPY src ./src

# Include sample/test data inside the image (Render-friendly)
# (This makes it available at /app/tests/data at runtime)
COPY tests/data ./tests/data

# Build argument to control editable install (default: false for production)
ARG DEV_MODE=false

# Install deps
RUN python -m pip install --upgrade pip && \
    # install nicewidgets from GitHub WITH the no_mpl extra (robust PEP 508 form)
    python -m pip install --no-cache-dir "nicewidgets[no_mpl] @ git+https://github.com/mapmanager/nicewidgets" && \
    # install kymflow itself (editable for dev, regular for production)
    if [ "$DEV_MODE" = "true" ]; then \
        python -m pip install --no-cache-dir -e ".[web]"; \
    else \
        python -m pip install --no-cache-dir ".[web]"; \
    fi

ENV PYTHONUNBUFFERED=1
ENV HOST=0.0.0.0
ENV PORT=8080

# Force web behavior in container
ENV KYMFLOW_GUI_NATIVE=0
ENV KYMFLOW_GUI_RELOAD=0
ENV KYMFLOW_REMOTE=1

# Default sample folder for Render/web runs
ENV KYMFLOW_DEFAULT_PATH=/app/tests/data
ENV KYMFLOW_DEFAULT_DEPTH=3

EXPOSE 8080

CMD ["python", "-m", "kymflow.gui_v2.app"]