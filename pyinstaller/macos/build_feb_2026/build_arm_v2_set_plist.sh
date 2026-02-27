#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# build_arm_v2_set_plist.sh
#
# Purpose: Update the built app's Info.plist with version metadata so the macOS
# "About <App>" dialog and Finder "Get Info" show correct version info.
#
# What it does:
#   - Sets CFBundleShortVersionString from kymflow's importlib.metadata version
#   - Sets CFBundleVersion (build number) from _build_info.BUILD_BUNDLE_VERSION
#
# Safe to re-run. Called by build_arm_v2.sh after nicegui-pack creates the .app.
# -----------------------------------------------------------------------------

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/_config.sh"

if [[ ! -f "$APP_PLIST" ]]; then
  echo "WARNING: Info.plist not found at $APP_PLIST"
  exit 0
fi

APP_VERSION="$(python -c 'from importlib.metadata import version; print(version("'"$PYPI_PACKAGE"'"))' 2>/dev/null || echo '0.0.0')"

# Optional: allow BUILD_BUNDLE_VERSION to be defined in _build_info.py; fallback "0"
BUNDLE_BUILD="$(python -c 'from kymflow import _build_info; print(getattr(_build_info, "BUILD_BUNDLE_VERSION", "0"))' 2>/dev/null || echo '0')"

echo "[plist] Setting Info.plist versions for $APP_NAME"
echo "[plist] CFBundleShortVersionString: $APP_VERSION"
echo "[plist] CFBundleVersion: $BUNDLE_BUILD"

# CFBundleShortVersionString (user-visible)
 /usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString $APP_VERSION" "$APP_PLIST" 2>/dev/null \
   || /usr/libexec/PlistBuddy -c "Add :CFBundleShortVersionString string $APP_VERSION" "$APP_PLIST"

# CFBundleVersion (build number)
 /usr/libexec/PlistBuddy -c "Set :CFBundleVersion $BUNDLE_BUILD" "$APP_PLIST" 2>/dev/null \
   || /usr/libexec/PlistBuddy -c "Add :CFBundleVersion string $BUNDLE_BUILD" "$APP_PLIST"

echo "[plist] Info.plist now contains:"
/usr/libexec/PlistBuddy -c "Print :CFBundleShortVersionString" "$APP_PLIST" || true
/usr/libexec/PlistBuddy -c "Print :CFBundleVersion" "$APP_PLIST" || true
