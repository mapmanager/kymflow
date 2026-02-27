#!/usr/bin/env bash
set -euo pipefail

source ./secrets.sh

APP="dist/KymFlow.app"
MAIN="$APP/Contents/MacOS/KymFlow"
ZIP="dist/KymFlow-pre-notarize.zip"

echo "[sign] Identity: $SIGN_ID"
echo "[sign] App: $APP"

# 1️⃣ Sign nested Mach-O files first
echo "[sign] Signing nested Mach-O files..."

while IFS= read -r -d '' f; do
  if file "$f" | grep -q "Mach-O"; then
    echo "  signing $f"
    codesign --force --options runtime --timestamp --sign "$SIGN_ID" "$f"
  fi
done < <(
  find "$APP/Contents/Frameworks" "$APP/Contents/Resources" \
    -type f -print0 2>/dev/null || true
)

# 2️⃣ Sign main executable
echo "[sign] Signing main executable..."
codesign --force --options runtime --timestamp --sign "$SIGN_ID" "$MAIN"

# 3️⃣ Sign bundle LAST (seal)
echo "[sign] Signing bundle..."
codesign --force --options runtime --timestamp --sign "$SIGN_ID" "$APP"

# 4️⃣ Verify
echo "[sign] Verifying..."
codesign --verify --deep --strict --verbose=2 "$APP"

echo "[sign] Verification OK"

# 5️⃣ Zip properly for notarization
echo "[zip] Creating notarization zip..."
rm -f "$ZIP"
ditto -c -k --sequesterRsrc --keepParent "$APP" "$ZIP"

echo "[zip] Done: $ZIP"
