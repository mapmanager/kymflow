#!/usr/bin/env bash
set -euo pipefail

ZIP="dist/KymFlow-pre-notarize.zip"
PROFILE="my-notarytool-profile-feb2025"
TOOL="/Applications/Xcode.app/Contents/Developer/usr/bin/notarytool"

MAX_ATTEMPTS=20
SLEEP_SECONDS=20

echo "[notary] ZIP: $ZIP"
echo "[notary] PROFILE: $PROFILE"
echo "[notary] Max attempts: $MAX_ATTEMPTS"
echo

attempt=1

while [ $attempt -le $MAX_ATTEMPTS ]; do
    echo "----------------------------------------"
    echo "[notary] Attempt $attempt"
    echo "----------------------------------------"

    OUTPUT="$(/usr/bin/arch -arm64 "$TOOL" submit "$ZIP" \
        --keychain-profile "$PROFILE" 2>&1 || true)"

    echo "$OUTPUT"

    # Extract submission ID if present
    ID="$(echo "$OUTPUT" | grep -Eo 'id: [0-9a-f-]+' | awk '{print $2}' | head -n1 || true)"

    # Check for successful upload confirmation
    if echo "$OUTPUT" | grep -q "Successfully uploaded file"; then
        echo
        echo "========================================"
        echo "[notary] SUCCESSFUL UPLOAD CONFIRMED"
        echo "[notary] Submission ID: $ID"
        echo "========================================"
        exit 0
    fi

    echo
    echo "[notary] Upload NOT confirmed (likely bus error)."

    if [ -n "$ID" ]; then
        echo "[notary] Submission ID created: $ID"
        echo "[notary] (This one may be incomplete on Apple side.)"
    fi

    echo "[notary] Waiting $SLEEP_SECONDS seconds before retry..."
    sleep "$SLEEP_SECONDS"

    attempt=$((attempt + 1))
done

echo
echo "========================================"
echo "[notary] GAVE UP AFTER $MAX_ATTEMPTS ATTEMPTS"
echo "========================================"
exit 1