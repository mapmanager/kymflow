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

# Read version from pyproject.toml (x.y.z only; grep/sed works from any env)
APP_VERSION="$(grep -E '^version[[:space:]]*=' "$REPO_ROOT/pyproject.toml" 2>/dev/null | head -1 | sed -E 's/^version[[:space:]]*=[[:space:]]*['\''"]?([0-9]+\.[0-9]+\.[0-9]+)['\''"]?.*/\1/')"
APP_VERSION="${APP_VERSION:-0.0.0}"

REL_BASENAME="${APP_NAME}-${APP_VERSION}-macos"
REL_ZIP="$DIST_DIR/${REL_BASENAME}.zip"
REL_MANIFEST="$DIST_DIR/${REL_BASENAME}-manifest.json"

echo "[release] App: $APP_PATH"
echo "[release] Version: $APP_VERSION"

# Quick sanity checks (should pass after stapling)
echo "[release] spctl assess..."
SPCTL_OUT="$(spctl --assess --type execute --verbose=4 "$APP_PATH" 2>&1 || true)"
echo "$SPCTL_OUT"
if ! echo "$SPCTL_OUT" | grep -qi "accepted"; then
  echo "ERROR: spctl did not accept the app. Did you run staple_and_verify.sh?"
  exit 3
fi

# Capture signing metadata
CS_META="$(codesign -dv --verbose=4 "$APP_PATH" 2>&1 || true)"
TEAM_ID="$(echo "$CS_META" | sed -nE 's/^TeamIdentifier=([A-Z0-9]+).*/\1/p' | tail -n 1)"
SIGNING_AUTH="$(echo "$CS_META" | sed -nE 's/^Authority=(Developer ID Application:.*)/\1/p' | head -n 1)"

NOTARY_ID=""
if [[ -f "$NOTARY_SUBMISSION_ID_FILE" ]]; then
  NOTARY_ID="$(cat "$NOTARY_SUBMISSION_ID_FILE" | tr -d '[:space:]')"
fi

# Create manifest JSON next to zip (use env vars for macOS bash 3.x compatibility)
export APP_PATH REL_ZIP REL_MANIFEST APP_NAME BUNDLE_ID APP_VERSION TEAM_ID SIGNING_AUTH NOTARY_ID
python - <<'PY'
import json, os, pathlib, time

zip_path = os.environ["REL_ZIP"]
manifest_path = os.environ["REL_MANIFEST"]
data = {
  "app_name": os.environ["APP_NAME"],
  "bundle_id": os.environ["BUNDLE_ID"],
  "version": os.environ["APP_VERSION"],
  "build_timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
  "team_id": os.environ.get("TEAM_ID", ""),
  "signing_authority": os.environ.get("SIGNING_AUTH", ""),
  "notary_submission_id": os.environ.get("NOTARY_ID", ""),
  "stapled": True,
  "artifact_zip": os.path.basename(zip_path),
}
pathlib.Path(manifest_path).write_text(json.dumps(data, indent=2) + "\n")
print(f"[release] Wrote manifest: {manifest_path}")
PY

echo "[release] Creating final distribution zip..."
rm -f "$REL_ZIP"
ditto -c -k --sequesterRsrc --keepParent "$APP_PATH" "$REL_ZIP"
ls -lh "$REL_ZIP"

echo "[release] ✅ Done"
echo "[release] Zip     : $REL_ZIP"
echo "[release] Manifest: $REL_MANIFEST"
