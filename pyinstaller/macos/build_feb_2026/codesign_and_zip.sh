#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# shellcheck source=/dev/null
source "$SCRIPT_DIR/_config.sh"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/_secrets.sh"

echo "[sign] Identity: $SIGN_ID"
echo "[sign] App     : $APP_PATH"
echo "[sign] Zip     : $PRE_NOTARIZE_ZIP"

if [[ ! -d "$APP_PATH" ]]; then
  echo "ERROR: App not found: $APP_PATH"
  exit 2
fi
if [[ ! -f "$APP_MAIN_BIN" ]]; then
  echo "ERROR: Main binary not found: $APP_MAIN_BIN"
  exit 2
fi

echo "[sign] Signing nested Mach-O files..."
while IFS= read -r -d '' f; do
  if file "$f" | grep -q "Mach-O"; then
    echo "  signing $f"
    codesign --force --options runtime --timestamp --sign "$SIGN_ID" "$f"
  fi
done < <(
  find "$APP_PATH/Contents/Frameworks" "$APP_PATH/Contents/Resources" \
    -type f -print0 2>/dev/null || true
)

echo "[sign] Signing main executable..."
codesign --force --options runtime --timestamp --sign "$SIGN_ID" "$APP_MAIN_BIN"

echo "[sign] Signing bundle (seal)..."
codesign --force --options runtime --timestamp --sign "$SIGN_ID" "$APP_PATH"

echo "[sign] Verifying..."
codesign --verify --deep --strict --verbose=2 "$APP_PATH"
echo "[sign] Verification OK"

echo "[zip] Creating notarization zip..."
rm -f "$PRE_NOTARIZE_ZIP"
ditto -c -k --sequesterRsrc --keepParent "$APP_PATH" "$PRE_NOTARIZE_ZIP"

echo "[zip] Done: $PRE_NOTARIZE_ZIP"
ls -lh "$PRE_NOTARIZE_ZIP" || true
