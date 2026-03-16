#!/usr/bin/env bash
# Simple local builder: create KymFlow.app from current src using nicegui-pack,
# without git tags, codesign, notarization, or release zips.

set -euo pipefail

# Script lives in pyinstaller/macos/build_feb_2026/; REPO_ROOT = kymflow/.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
BUILD_FOLDER="$SCRIPT_DIR"

cd "$BUILD_FOLDER"

# Optional: override some knobs for “dev” builds.
# You can change these or export them before calling the script.

# App name shown in Finder and inside Contents/MacOS/
export APP_NAME="${APP_NAME:-KymFlow}"

# Bundle ID (safe to reuse the real one for local testing)
export BUNDLE_ID="${BUNDLE_ID:-com.robertcudmore.kymflow}"

# Use the normal GUI entry point
export MAIN_PY="${MAIN_PY:-$REPO_ROOT/src/kymflow/gui_v2/app.py}"

# build_arm_v2.sh uses _config.sh and writes to BUILD_FOLDER/dist/ (no overrides here)
echo "[dev-build] Repo root : $REPO_ROOT"
echo "[dev-build] Build dir : $BUILD_FOLDER"
echo "[dev-build] App name  : $APP_NAME"
echo "[dev-build] Main py   : $MAIN_PY"

# Run the existing nicegui-pack-based build
bash "$BUILD_FOLDER/build_arm_v2.sh"

echo
echo "[dev-build] Done. Look for the app under:"
echo "  $BUILD_FOLDER/dist/${APP_NAME}.app"