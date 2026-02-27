#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# build_arm_v2_timestamp.sh
#
# Purpose: Write src/kymflow/_build_info.py with build-time metadata. This file
# is bundled into the .app by PyInstaller and used at runtime (e.g. "About"
# dialog) and by build_arm_v2_set_plist.sh for CFBundleVersion.
#
# What it does:
#   - Captures build timestamp, git state, Python/NiceGUI/PyInstaller versions
#   - Sets BUILD_BUNDLE_VERSION (YYYYMMDD.HHMMSS) for Info.plist CFBundleVersion
#
# Must be SOURCED by build_arm_v2.sh so it inherits the active venv. Safe to
# run standalone for debugging.
# -----------------------------------------------------------------------------

# Allow script to run standalone OR be sourced.
# Do NOT use set -euo here because parent may already use it.

# Load shared config (safe if already loaded)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/_config.sh"

BUILD_LOCAL="$(date '+%Y-%m-%d %H:%M:%S %Z')"
BUILD_BUNDLE_VERSION="$(date '+%Y%m%d.%H%M%S')"
ARCH="$(uname -m 2>/dev/null || echo 'unknown')"

GIT_SHA="$(git -C "$REPO_ROOT" rev-parse --short HEAD 2>/dev/null || echo 'unknown')"
GIT_DIRTY="$(git -C "$REPO_ROOT" diff --quiet 2>/dev/null && echo 'clean' || echo 'dirty')"

# Python version (best-effort)
PYTHON_VERSION="$(python -c 'import sys; print(sys.version.split()[0])' 2>/dev/null || echo 'not-found')"

# NiceGUI version (best-effort)
NICEGUI_VERSION="$(python -c 'import nicegui; print(getattr(nicegui, "__version__", "unknown"))' 2>/dev/null || echo 'not-found')"

# PyInstaller version (best-effort)
PYINSTALLER_VERSION="$(python -c 'import PyInstaller; print(getattr(PyInstaller, "__version__", "unknown"))' 2>/dev/null || echo 'not-found')"

# Build env (best-effort)
BUILD_ENV="${VIRTUAL_ENV:-${CONDA_DEFAULT_ENV:-not-found}}"

mkdir -p "$(dirname "$BUILD_INFO_PATH")"

cat > "$BUILD_INFO_PATH" <<EOF
# Auto-generated at build time. DO NOT EDIT.

BUILD_TIMESTAMP_LOCAL = "${BUILD_LOCAL}"
BUILD_BUNDLE_VERSION = "${BUILD_BUNDLE_VERSION}"

GIT_SHA = "${GIT_SHA}"
GIT_STATE = "${GIT_DIRTY}"

ARCH = "${ARCH}"
PYTHON_VERSION = "${PYTHON_VERSION}"
BUILD_ENV = "${BUILD_ENV}"

NICEGUI_VERSION = "${NICEGUI_VERSION}"
PYINSTALLER_VERSION = "${PYINSTALLER_VERSION}"
EOF

echo "[build] Wrote build info: $BUILD_INFO_PATH"
echo "[build] ---- $(basename "$BUILD_INFO_PATH") ----"
cat "$BUILD_INFO_PATH"
echo "[build] ------------------------"
