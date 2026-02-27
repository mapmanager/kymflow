#!/usr/bin/env bash
set -euo pipefail

source ./secrets.sh

ZIP="dist/NiceGUIMin-pre-notarize.zip"

echo "[min-notary] Submitting $ZIP"
xcrun notarytool submit "$ZIP" --keychain-profile "$NOTARY_PROFILE" || true

echo "[min-notary] Latest history:"
xcrun notarytool history --keychain-profile "$NOTARY_PROFILE" | head -n 30

echo "[min-notary] Paste the new submission id and poll with:"
echo "xcrun notarytool info <ID> --keychain-profile \"$NOTARY_PROFILE\" --output-format json"
