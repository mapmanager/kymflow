#!/bin/bash
set -euo pipefail
#
# Build or refresh ~/Documents/KymFlow/KymFlow Jupyter.app (minimal bundle).
# Invoked from postinstall (pkg) or install-kymflow-curl.sh.
#

log() {
  echo "[make_jupyter_app] $*"
}

fail() {
  echo "[make_jupyter_app] ERROR: $*" >&2
  exit 1
}

[ "$#" -eq 4 ] || fail "Usage: make_jupyter_app.sh <user_home> <app_root> <workspace_root> <bundle_version>"

USER_HOME="$1"
APP_ROOT="$2"
WORKSPACE_ROOT="$3"
BUNDLE_VERSION="$4"

[ -n "${USER_HOME}" ] || fail "user_home is empty"
[ -n "${APP_ROOT}" ] || fail "app_root is empty"
[ -n "${WORKSPACE_ROOT}" ] || fail "workspace_root is empty"
[ -n "${BUNDLE_VERSION}" ] || fail "bundle_version is empty"

APP_NAME="KymFlow Jupyter"
APP_BUNDLE_PATH="${WORKSPACE_ROOT}/${APP_NAME}.app"
CONTENTS_DIR="${APP_BUNDLE_PATH}/Contents"
MACOS_DIR="${CONTENTS_DIR}/MacOS"
RESOURCES_DIR="${CONTENTS_DIR}/Resources"

APP_EXECUTABLE="launch_jupyter"
APP_ICON_NAME="AppIcon"
APP_ICON_SOURCE="${APP_ROOT}/payload/resources/AppIcon.icns"
APP_ICON_DEST="${RESOURCES_DIR}/${APP_ICON_NAME}.icns"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NATIVE_LAUNCHER_SOURCE="${SCRIPT_DIR}/launch_jupyter"
SWIFT_SOURCE_FALLBACK="${SCRIPT_DIR}/../app_launcher/launch_jupyter.swift"
NATIVE_LAUNCHER_DEST="${MACOS_DIR}/${APP_EXECUTABLE}"

mkdir -p "${MACOS_DIR}" "${RESOURCES_DIR}"

# CFBundle* strings: escape & < > for XML text nodes.
xml_escape() {
  printf '%s' "$1" | python3 -c 'import sys; print(sys.stdin.read().replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))'
}

PLIST_SHORT="$(xml_escape "${BUNDLE_VERSION}")"
PLIST_BUNDLE="$(xml_escape "${BUNDLE_VERSION}")"

cat > "${CONTENTS_DIR}/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDevelopmentRegion</key>
  <string>English</string>
  <key>CFBundleDisplayName</key>
  <string>KymFlow Jupyter</string>
  <key>CFBundleExecutable</key>
  <string>${APP_EXECUTABLE}</string>
  <key>CFBundleIconFile</key>
  <string>${APP_ICON_NAME}</string>
  <key>CFBundleIdentifier</key>
  <string>org.cudmore.kymflow.jupyter</string>
  <key>CFBundleInfoDictionaryVersion</key>
  <string>6.0</string>
  <key>CFBundleName</key>
  <string>KymFlow Jupyter</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>${PLIST_SHORT}</string>
  <key>CFBundleVersion</key>
  <string>${PLIST_BUNDLE}</string>
  <key>LSMinimumSystemVersion</key>
  <string>13.0</string>
  <key>NSHighResolutionCapable</key>
  <true/>
</dict>
</plist>
EOF

if [ -x "${NATIVE_LAUNCHER_SOURCE}" ]; then
  cp "${NATIVE_LAUNCHER_SOURCE}" "${NATIVE_LAUNCHER_DEST}"
  chmod +x "${NATIVE_LAUNCHER_DEST}"
  log "Installed native launcher binary from scripts payload"
elif [ -f "${SWIFT_SOURCE_FALLBACK}" ] && command -v swiftc >/dev/null 2>&1; then
  # Fallback for developer curl/source-tree runs: build native launcher from source.
  swiftc \
    -O \
    -target arm64-apple-macos13.0 \
    -framework AppKit \
    -framework Foundation \
    "${SWIFT_SOURCE_FALLBACK}" \
    -o "${NATIVE_LAUNCHER_DEST}"
  chmod +x "${NATIVE_LAUNCHER_DEST}"
  log "Built native launcher from Swift source fallback"
else
  fail "Native launcher missing: expected executable ${NATIVE_LAUNCHER_SOURCE}, or Swift source ${SWIFT_SOURCE_FALLBACK} with swiftc available."
fi

if [ -f "${APP_ICON_SOURCE}" ]; then
  cp "${APP_ICON_SOURCE}" "${APP_ICON_DEST}"
  log "Copied icon: ${APP_ICON_DEST}"
else
  log "Icon source not found; app will use generic icon: ${APP_ICON_SOURCE}"
fi

log "Created app bundle: ${APP_BUNDLE_PATH}"
