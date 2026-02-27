#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# release-pipeline.sh — Full release pipeline (git branch + tag + build + sign + notarize + merge)
#
# Run from: kymflow/ (repo root)
#   cd kymflow
#   ./pyinstaller/macos/build_feb_2026/release-pipeline.sh
#
# Pre-condition: on main; edit pyproject.toml with new version (e.g. 0.2.2).
# You may commit the version bump first, or leave it uncommitted — the script
# will add and commit it.
#
# Fails if tag or release branch already exists (previous run or retry).
# On failure: exit with error; never deletes tag or branch (user must do manually).
# -----------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# shellcheck source=/dev/null
source "$SCRIPT_DIR/_config.sh"

# ---- Read version from pyproject.toml ----
RELVER="$(grep -E '^version[[:space:]]*=' "$REPO_ROOT/pyproject.toml" 2>/dev/null | head -1 | sed -E 's/^version[[:space:]]*=[[:space:]]*['\''"]?([0-9]+\.[0-9]+\.[0-9]+)['\''"]?.*/\1/')"
RELVER="${RELVER:?ERROR: Could not read version from pyproject.toml}"
export RELBR="release/v${RELVER}"
export RELTAG="v${RELVER}"

echo "[release-pipeline] Version: $RELVER"
echo "[release-pipeline] Branch:  $RELBR"
echo "[release-pipeline] Tag:     $RELTAG"
echo ""

# ---- Pre-checks ----
echo "[release-pipeline] Pre-checks..."

CURRENT_BRANCH="$(git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
if [[ "$CURRENT_BRANCH" != "main" ]]; then
  echo "ERROR: Not on main branch (current: $CURRENT_BRANCH). Checkout main first."
  exit 2
fi

# Allow uncommitted pyproject.toml (and CHANGELOG) only; otherwise require clean
CHANGED="$(git -C "$REPO_ROOT" diff --name-only 2>/dev/null; git -C "$REPO_ROOT" diff --cached --name-only 2>/dev/null)" || true
if [[ -n "$CHANGED" ]]; then
  BAD="$(echo "$CHANGED" | grep -vE '^(pyproject\.toml|CHANGELOG\.md)$' || true)"
  if [[ -n "$BAD" ]]; then
    echo "ERROR: Working tree has changes other than pyproject.toml/CHANGELOG.md. Commit or stash first."
    exit 2
  fi
fi

if git -C "$REPO_ROOT" rev-parse "$RELTAG" >/dev/null 2>&1; then
  echo "ERROR: Tag $RELTAG already exists."
  echo "  Previous run may have completed or failed. To retry, manually run:"
  echo "    git tag -d $RELTAG"
  echo "    git branch -D $RELBR"
  exit 2
fi

if git -C "$REPO_ROOT" rev-parse "refs/heads/$RELBR" >/dev/null 2>&1; then
  echo "ERROR: Branch $RELBR already exists."
  echo "  Previous run may have completed or failed. To retry, manually run:"
  echo "    git tag -d $RELTAG"
  echo "    git branch -D $RELBR"
  exit 2
fi

echo "[release-pipeline] Pre-checks OK."
echo ""

# ---- Step 2: Create release branch ----
echo "[release-pipeline] Step 2: Create release branch"
git -C "$REPO_ROOT" checkout -b "$RELBR"

# ---- Step 3: Commit release (if pyproject.toml or CHANGELOG have uncommitted changes) ----
echo "[release-pipeline] Step 3: Commit release"
git -C "$REPO_ROOT" add pyproject.toml CHANGELOG.md 2>/dev/null || true
if ! git -C "$REPO_ROOT" diff --cached --quiet 2>/dev/null; then
  git -C "$REPO_ROOT" commit -m "Release ${RELTAG}"
else
  echo "[release-pipeline] No changes to commit (version bump already committed)."
fi

# ---- Step 4: Tag the commit ----
echo "[release-pipeline] Step 4: Tag the commit"
git -C "$REPO_ROOT" tag -a "$RELTAG" -m "KymFlow ${RELTAG}"

# ---- Step 5: Checkout tag (detached HEAD) ----
echo "[release-pipeline] Step 5: Checkout tag"
git -C "$REPO_ROOT" checkout "$RELTAG"

# ---- Step 6: Build pipeline ----
echo "[release-pipeline] Step 6: Build pipeline"
cd "$SCRIPT_DIR"

echo "[release-pipeline] 6.1 Build"
./build_arm_v2.sh

echo "[release-pipeline] 6.2 Codesign + notarization zip"
./codesign_and_zip.sh

echo "[release-pipeline] 6.3 Submit to notary service"
./notary_submit.sh

echo "[release-pipeline] 6.4 Poll until Accepted"
./notary_poll_until_done.sh

echo "[release-pipeline] 6.5 Staple + verify"
./staple_and_verify.sh

echo "[release-pipeline] 6.6 Create final release zip + manifest"
./make_release_zip.sh

# ---- Step 7: Push tag and branch ----
echo "[release-pipeline] Step 7: Push tag and branch"
cd "$REPO_ROOT"
git push origin "$RELTAG"
git push origin "$RELBR"

# ---- Step 8: Merge back to main ----
echo "[release-pipeline] Step 8: Merge back to main"
git checkout main
git pull
git merge --no-ff "$RELBR"
git push

# ---- Optional: Upload to GitHub Release (if gh is available) ----
REL_ZIP="$DIST_DIR/${APP_NAME}-${RELVER}-macos.zip"
REL_MANIFEST="$DIST_DIR/${APP_NAME}-${RELVER}-macos-manifest.json"
if command -v gh >/dev/null 2>&1; then
  echo "[release-pipeline] Uploading to GitHub Release..."
  if gh release view "$RELTAG" >/dev/null 2>&1; then
    gh release upload "$RELTAG" "$REL_ZIP" "$REL_MANIFEST" --clobber
  else
    gh release create "$RELTAG" "$REL_ZIP" "$REL_MANIFEST" --notes "KymFlow ${RELTAG}"
  fi
  echo "[release-pipeline] Uploaded to GitHub Release."
else
  echo "[release-pipeline] gh not found; skipping GitHub Release upload."
  echo "[release-pipeline] Artifacts: $REL_ZIP  $REL_MANIFEST"
fi

echo ""
echo "[release-pipeline] DONE."
echo "[release-pipeline] Zip:     $REL_ZIP"
echo "[release-pipeline] Manifest: $REL_MANIFEST"
