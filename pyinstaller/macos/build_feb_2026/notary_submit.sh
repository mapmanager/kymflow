#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# shellcheck source=/dev/null
source "$SCRIPT_DIR/_config.sh"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/_secrets.sh"

if [[ ! -f "$PRE_NOTARIZE_ZIP" ]]; then
  echo "ERROR: Zip not found: $PRE_NOTARIZE_ZIP"
  exit 2
fi

echo "[notary] Submitting: $PRE_NOTARIZE_ZIP"
echo "[notary] Profile   : $NOTARY_PROFILE"
echo "[notary] Uploading to Apple (this may take a few minutes)..."
echo ""

# Submit and capture stdout (notarytool prints the submission id)
OUT="$(xcrun notarytool submit "$PRE_NOTARIZE_ZIP" --keychain-profile "$NOTARY_PROFILE" 2>&1 || true)"
echo "$OUT"

# Extract UUID (handles "id: <uuid>" line)
SUB_ID="$(echo "$OUT" | sed -nE 's/^[[:space:]]*id:[[:space:]]*([0-9a-f-]{36}).*/\1/p' | tail -n 1)"

if [[ -z "$SUB_ID" ]]; then
  echo "ERROR: Could not parse submission id from notarytool output."
  exit 3
fi

echo "$SUB_ID" > "$NOTARY_SUBMISSION_ID_FILE"
echo "[notary] Saved submission id to: $NOTARY_SUBMISSION_ID_FILE"
echo "[notary] ID: $SUB_ID"

echo "[notary] Next: ./notary_poll_until_done.sh (or run info manually)"
