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

APP_LOG_DIR="${APP_ROOT}/logs"
APP_LOG_FILE="${APP_LOG_DIR}/jupyter-app-launch.log"

mkdir -p "${MACOS_DIR}" "${RESOURCES_DIR}" "${APP_LOG_DIR}"

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

cat > "${MACOS_DIR}/${APP_EXECUTABLE}" <<'EOF'
#!/bin/bash
set -euo pipefail

APP_ROOT="$HOME/Library/Application Support/kymflow-pkg"
WORKSPACE_ROOT="$HOME/Documents/KymFlow"
JUPYTER_BIN="$APP_ROOT/venv/bin/jupyter"
APP_LOG_DIR="$APP_ROOT/logs"
APP_LOG_FILE="$APP_LOG_DIR/jupyter-app-launch.log"

mkdir -p "$APP_LOG_DIR"

{
  echo "=== KymFlow Jupyter app launch ==="
  date
  echo "APP_ROOT=$APP_ROOT"
  echo "WORKSPACE_ROOT=$WORKSPACE_ROOT"
  echo "JUPYTER_BIN=$JUPYTER_BIN"

  if [ ! -x "$JUPYTER_BIN" ]; then
    echo "ERROR: jupyter not found at $JUPYTER_BIN" >&2
    exit 1
  fi

  mkdir -p "$WORKSPACE_ROOT"
  cd "$WORKSPACE_ROOT"

  exec "$JUPYTER_BIN" lab --notebook-dir="$WORKSPACE_ROOT"
} >> "$APP_LOG_FILE" 2>&1
EOF

chmod +x "${MACOS_DIR}/${APP_EXECUTABLE}"

if [ -f "${APP_ICON_SOURCE}" ]; then
  cp "${APP_ICON_SOURCE}" "${APP_ICON_DEST}"
  log "Copied icon: ${APP_ICON_DEST}"
else
  log "Icon source not found; app will use generic icon: ${APP_ICON_SOURCE}"
fi

log "Created app bundle: ${APP_BUNDLE_PATH}"
