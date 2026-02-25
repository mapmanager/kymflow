#!/usr/bin/env bash

# Allow script to run standalone OR be sourced.
# Do NOT use set -euo here because parent may already use it.

# -----------------------------------------------------------------------------
# Build stamp metadata
# -----------------------------------------------------------------------------
BUILD_LOCAL="$(date '+%Y-%m-%d %H:%M:%S %Z')"
BUILD_BUNDLE_VERSION="$(date '+%Y%m%d.%H%M%S')"

ARCH="$(uname -m 2>/dev/null || echo 'unknown')"

GIT_SHA="$(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')"
GIT_DIRTY="$(git diff --quiet 2>/dev/null && echo 'clean' || echo 'dirty')"

# -----------------------------------------------------------------------------
# Versions / toolchain info
# - nicegui-pack has no --version flag; it comes from NiceGUI.
# -----------------------------------------------------------------------------
# if command -v nicegui-pack >/dev/null 2>&1; then
#     NICEGUI_PACK_PATH="$(command -v nicegui-pack)"
# else
#     NICEGUI_PACK_PATH="not-found"
# fi

# Python version (best-effort)
PYTHON_VERSION="$(python -c 'import sys; print(sys.version.split()[0])' 2>/dev/null || echo 'not-found')"

# NiceGUI version (best-effort)
NICEGUI_VERSION="$(python -c 'import nicegui; print(getattr(nicegui, "__version__", "unknown"))' 2>/dev/null || echo 'not-found')"

# PyInstaller version (best-effort)
PYINSTALLER_VERSION="$(python -c 'import PyInstaller; print(getattr(PyInstaller, "__version__", "unknown"))' 2>/dev/null || echo 'not-found')"

# Conda env (best-effort)
# CONDA_ENV_NAME="${CONDA_DEFAULT_ENV:-not-found}"

# -----------------------------------------------------------------------------
# Output path
# -----------------------------------------------------------------------------
BUILD_INFO_PATH="../../src/kymflow/_build_info.py"

# Export so parent script (when sourced) can see it
export BUILD_INFO_PATH

# -----------------------------------------------------------------------------
# Write file (plain Python module that PyInstaller will bundle)
# -----------------------------------------------------------------------------
cat > "$BUILD_INFO_PATH" <<EOF
# Auto-generated at build time. DO NOT EDIT.

BUILD_TIMESTAMP = "${BUILD_LOCAL}"
BUILD_BUNDLE_VERSION = "${BUILD_BUNDLE_VERSION}"

GIT_INFO = "SHA:${GIT_SHA} STATE:${GIT_DIRTY}"

ARCH = "${ARCH}"
PYTHON_VERSION = "${PYTHON_VERSION}"

NICEGUI_VERSION = "${NICEGUI_VERSION}"
PYINSTALLER_VERSION = "${PYINSTALLER_VERSION}"
EOF

echo "[build_arm] Wrote build info: $BUILD_INFO_PATH"
echo "[build_arm] ---- _build_info.py ----"
cat "$BUILD_INFO_PATH"
echo "[build_arm] ------------------------"