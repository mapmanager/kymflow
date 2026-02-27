#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# shellcheck source=/dev/null
source "$SCRIPT_DIR/_config.sh"

if [[ ! -d "$APP_PATH" ]]; then
  echo "ERROR: App not found: $APP_PATH"
  exit 2
fi

echo "[staple] Stapling: $APP_PATH"
xcrun stapler staple "$APP_PATH"

echo "[staple] Assess (Gatekeeper):"
spctl --assess --type execute --verbose=4 "$APP_PATH"

echo "[staple] Done."
