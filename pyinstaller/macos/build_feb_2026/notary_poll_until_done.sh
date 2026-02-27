#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# shellcheck source=/dev/null
source "$SCRIPT_DIR/_config.sh"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/_secrets.sh"

SUB_ID="${1:-}"

if [[ -z "$SUB_ID" ]]; then
  if [[ -f "$NOTARY_SUBMISSION_ID_FILE" ]]; then
    SUB_ID="$(cat "$NOTARY_SUBMISSION_ID_FILE" | tr -d '[:space:]')"
  fi
fi

if [[ -z "$SUB_ID" ]]; then
  echo "Usage: $0 <submission-id>"
  echo "Or run after notary_submit.sh (it writes $NOTARY_SUBMISSION_ID_FILE)."
  exit 2
fi

echo "[poll] ID      : $SUB_ID"
echo "[poll] Profile : $NOTARY_PROFILE"

while true; do
  JSON="$(xcrun notarytool info "$SUB_ID" --keychain-profile "$NOTARY_PROFILE" --output-format json)"
  echo "$JSON"

  STATUS="$(echo "$JSON" | python -c 'import sys, json; print(json.load(sys.stdin).get("status",""))' 2>/dev/null || echo "")"

  if [[ "$STATUS" == "Accepted" ]]; then
    echo "[poll] ✅ Accepted"
    exit 0
  elif [[ "$STATUS" == "Invalid" || "$STATUS" == "Rejected" ]]; then
    echo "[poll] ❌ $STATUS"
    echo "[poll] Fetch log:"
    xcrun notarytool log "$SUB_ID" --keychain-profile "$NOTARY_PROFILE" || true
    exit 1
  fi

  sleep 20
done
