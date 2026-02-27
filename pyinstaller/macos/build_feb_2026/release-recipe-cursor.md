# KymFlow Release Recipe (cursor / future-me)

**Goal:** reproducible releases, release branch + tag, version in `pyproject.toml` only.

---

## Simplified workflow: release-pipeline.sh

For an almost end-to-end run, use `release-pipeline.sh`:

1. Edit `pyproject.toml` with the new version (e.g. `0.2.2`).
2. Ensure `main` is up to date and you have committed locally (or leave `pyproject.toml` uncommitted — the script will add and commit it).
3. Run from `kymflow/`:

```bash
cd kymflow
./pyinstaller/macos/build_feb_2026/release-pipeline.sh
```

The script: reads version from `pyproject.toml`, creates release branch + tag, builds, codesigns, notarizes, staples, zips, pushes, and merges back to `main`. Fails if tag or release branch already exists (e.g. from a previous run). Test the final zip manually before distributing.

Optional: if `gh` (GitHub CLI) is installed, the script uploads the zip + manifest to the GitHub Release.

---

## Full manual recipe (step-by-step)

Use this when you want to run each step manually or troubleshoot.

---

## Pre-flight (once per machine)

Before any release, confirm:

```bash
# Signing identity
security find-identity -v -p codesigning
```

---

## Sanity check (before Step 0)

Confirm you can run KymFlow from the command line:

```bash
cd kymflow   # or cd /path/to/kymflow
uv run python -m kymflow.gui_v2.app
```

Or use the entry point: `uv run kymflow-gui`

Expected: app opens in a window. Quit when satisfied.

---

## Step 0) Pick version and branch names

```bash
export RELVER="0.2.1"
export RELBR="release/v${RELVER}"
export RELTAG="v${RELVER}"
```

**Important:** `RELVER` must match what you put in `pyproject.toml`.

---

## Step 1) Prep on main

Assume local `main` is the source for the build (no explicit pull needed unless you sync with remote).

```bash
cd /path/to/kymflow   # or cd kymflow/ from kymflow_outer
git checkout main
git status
```

Expected: clean working tree on main.

---

## Step 2) Create release branch

```bash
git checkout -b "$RELBR"
```

---

## Step 3) Bump version + commit

1. Edit `pyproject.toml`: set `version = "X.Y.Z"` to match `RELVER`.
2. Update `CHANGELOG.md` if you use it.

```bash
git add pyproject.toml CHANGELOG.md 2>/dev/null || true
git add pyproject.toml
git commit -m "Release ${RELTAG}"
```

Expected: one commit that marks the release.

---

## Step 4) Tag the commit

```bash
git tag -a "$RELTAG" -m "KymFlow ${RELTAG}"
```

This tags the current commit (the release commit).

---

## Step 5) Build from the tag (detached HEAD)

```bash
git checkout "$RELTAG"
git status
```

Expected: detached HEAD at the tag, clean working tree.

---

## Step 6) Run the build pipeline manually

**Work dir:** `kymflow/pyinstaller/macos/build_feb_2026/`

```bash
cd kymflow/pyinstaller/macos/build_feb_2026
# Or, from kymflow_outer:  cd kymflow/pyinstaller/macos/build_feb_2026
```

### 6.1) Build

```bash
./build_arm_v2.sh
```

Output: `dist/KymFlow.app`

### 6.1b) Manual smoke test (before codesigning)

Open and test the app on your dev machine:

```bash
open dist/KymFlow.app
```

Load files, verify basic workflow. Ensure you are shipping an app that runs. Quit when satisfied.

### 6.2) Codesign + create notarization zip

```bash
./codesign_and_zip.sh
```

Output: `dist/KymFlow-pre-notarize.zip`

### 6.3) Submit to Apple notary service

> **Network requirement:** This step **requires stable internet**.  
> If you use a home router that Apple’s notary servers reject, switch to another network (e.g. phone hotspot, office Wi‑Fi) before running this.

```bash
./notary_submit.sh
```

Saves submission ID to `dist/notary_submission_id.txt`. Copy the printed ID if you need it for manual polling.

### 6.4) Poll until Accepted

```bash
./notary_poll_until_done.sh
```

Uses the submission ID from 6.3 (saved in `dist/notary_submission_id.txt`). If run without args after `notary_submit.sh`, it reads that file automatically. Polls every 20s until `Accepted` or `Invalid`/`Rejected`. On rejection, fetch the log and fix issues before retrying.

### 6.5) Staple + verify

```bash
./staple_and_verify.sh
```

Staples the notarization ticket to `dist/KymFlow.app`.

### 6.6) Create final release zip + manifest

```bash
./make_release_zip.sh
```

Reads version from `pyproject.toml` (x.y.z). Output:

- `dist/KymFlow-<version>-macos.zip` — distribution artifact
- `dist/KymFlow-<version>-macos-manifest.json` — metadata

---

## Step 7) Publish artifacts

Attach to a GitHub Release for tag `v<version>`:

- `KymFlow-<version>-macos.zip`
- `KymFlow-<version>-macos-manifest.json`

Or upload to Dropbox / other hosting if preferred.

Push the tag and release branch (provides traceability: the tag points to the exact commit whose source produced the zip):

```bash
git push origin "$RELTAG"
git push origin "$RELBR"
```

---

## Step 8) Merge back to main

```bash
git checkout main
git pull
git merge --no-ff "$RELBR"
git push
```

**Purpose:** Brings the release commit (version bump) back into `main`. That way `main` reflects the released version and future development continues from there. The release branch remains as an archive of what was distributed.

---

## Post-release checks

1. Download the zip as a user would.
2. Unzip and run the app (double-click).
3. Verify file picking for Desktop, Documents, Downloads.

The pipeline (codesign → notary → staple → ditto zip) produces a proper macOS-certified app; users should not need to grant Full Disk Access.
---

## Troubleshooting

| Issue | Action |
|-------|--------|
| Notary submit fails (network) | Use another network (phone hotspot, office Wi‑Fi). |
| `nicegui-pack` not found | Ensure `nicegui==3.7.1` is installed; `nicegui-pack` is an entry point in nicegui. |
| spctl rejects app | Confirm you ran `staple_and_verify.sh` after notary was accepted. |
| Version mismatch | Ensure `RELVER` matches `pyproject.toml`. |
| Tag or branch exists | Previous run or retry. To retry: manually run `git tag -d vX.Y.Z` and `git branch -D release/vX.Y.Z`. |
