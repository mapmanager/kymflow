#!/usr/bin/env bash
set -euo pipefail

source ./secrets.sh

APP="dist/NiceGUIMin.app"
MAIN="$APP/Contents/MacOS/NiceGUIMin"
ZIP="dist/NiceGUIMin-pre-notarize.zip"

echo "[min-sign] Identity: ${SIGN_ID:-<missing SIGN_ID>}"
echo "[min-sign] App: $APP"
echo "[min-sign] Zip: $ZIP"

# -----------------------------------------------------------------------------
# Sanity checks
# -----------------------------------------------------------------------------
if [ -z "${SIGN_ID:-}" ]; then
  echo "[min-sign] ERROR: SIGN_ID is not set (source ./secrets.sh)" >&2
  exit 1
fi
if [ ! -d "$APP" ]; then
  echo "[min-sign] ERROR: App not found: $APP" >&2
  exit 1
fi
if [ ! -f "$MAIN" ]; then
  echo "[min-sign] ERROR: Main executable not found: $MAIN" >&2
  exit 1
fi

# -----------------------------------------------------------------------------
# Codesign: sign nested Mach-O first, then main, then the bundle
# -----------------------------------------------------------------------------
echo "[min-sign] Signing nested Mach-O files..."
while IFS= read -r -d '' f; do
  if file "$f" | grep -q "Mach-O"; then
    codesign --force --options runtime --timestamp --sign "$SIGN_ID" "$f"
  fi
done < <(find "$APP/Contents" -type f -print0)

echo "[min-sign] Signing main executable..."
codesign --force --options runtime --timestamp --sign "$SIGN_ID" "$MAIN"

echo "[min-sign] Sealing app bundle..."
codesign --force --options runtime --timestamp --sign "$SIGN_ID" "$APP"

# -----------------------------------------------------------------------------
# Verify signature strictly
# -----------------------------------------------------------------------------
echo "[min-sign] Verifying signature..."
codesign --verify --deep --strict --verbose=2 "$APP"
echo "[min-sign] Verification OK"

# -----------------------------------------------------------------------------
# Zip cleanly for notarization (avoid __MACOSX)
# -----------------------------------------------------------------------------
echo "[min-sign] Creating notarization zip..."
rm -f "$ZIP"
ditto -c -k --keepParent "$APP" "$ZIP"

# Confirm zip cleanliness
if unzip -l "$ZIP" | grep -q "__MACOSX"; then
  echo "[min-sign] ERROR: Zip contains __MACOSX; rebuild zip without Finder metadata." >&2
  exit 1
fi

echo "[min-sign] Done: $ZIP"
ls -lh "$ZIP"