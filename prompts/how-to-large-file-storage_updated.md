# How-To: Large File Storage Protection

This guide explains how large-file protection works in repos like kymflow and acqstore, and how to add it to a new repo.

## What it does

Pre-commit and pre-push gates block `git commit` and `git push` when files exceed a size limit (e.g. 60MB). If a large file is detected, the operation aborts with a message to fix the file or add it via Git LFS.

## Components

- **`scripts/git-large-file-check.sh`** — Bash script that checks file sizes and exits with status 1 if any exceed the limit.
- **`scripts/hooks/pre-commit`** — Git hook that runs the checker in "staged" mode before each commit.
- **`scripts/hooks/pre-push`** — Git hook that runs the checker in "tracked" mode before each push.

Using `core.hooksPath`, these hooks live in `scripts/hooks/` and are version-controlled, so they come with the repo when developers clone.

## How the script works

- **`staged` mode** — Checks only files that are staged for commit (`git diff --cached --name-only --diff-filter=ACM`).
- **`tracked` mode** — Checks all files tracked by git (`git ls-files`).

The size limit is configurable via `MAX_SIZE_MB` (default 60) at the top of the script.

---

## Example scripts

### scripts/git-large-file-check.sh

```bash
#!/usr/bin/env bash
# Shared script: check for too-large files in git

set -euo pipefail

# ===== configuration =====
MAX_SIZE_MB=60                     # change this if needed
MAX_SIZE_BYTES=$((MAX_SIZE_MB * 1024 * 1024))

MODE="${1:-staged}"                # "staged" or "tracked"

# Select file list based on mode
case "$MODE" in
  staged)
    echo "🔍 Large file check (> ${MAX_SIZE_MB}MB) on STAGED files..."
    FILES=$(git diff --cached --name-only --diff-filter=ACM)
    ;;
  tracked)
    echo "🔍 Large file check (> ${MAX_SIZE_MB}MB) on ALL TRACKED files..."
    FILES=$(git ls-files)
    ;;
  *)
    echo "Unknown mode '$MODE' (expected 'staged' or 'tracked')" >&2
    exit 1
    ;;
esac

if [ -z "${FILES}" ]; then
  echo "✓ No files to check."
  exit 0
fi

BLOCK=0

for file in $FILES; do
  if [ ! -f "$file" ]; then
    continue
  fi

  size_bytes=$(wc -c < "$file" | tr -d '[:space:]')

  if [ "$size_bytes" -gt "$MAX_SIZE_BYTES" ]; then
    size_mb=$((size_bytes / 1024 / 1024))
    echo "❌ ERROR: '$file' is ${size_mb}MB (limit: ${MAX_SIZE_MB}MB)"
    BLOCK=1
  fi
done

if [ "$BLOCK" -ne 0 ]; then
  echo
  echo "❌ Operation aborted — large files detected."
  echo "Fix the files or add them to Git LFS."
  exit 1
fi

# PASS MESSAGE
echo "✓ All files OK — no large files detected."

exit 0
```

### scripts/hooks/pre-commit

```bash
#!/usr/bin/env bash

# Call the shared checker script in "staged" mode
REPO_ROOT="$(git rev-parse --show-toplevel)"
exec "$REPO_ROOT/scripts/git-large-file-check.sh" staged
```

### scripts/hooks/pre-push

```bash
#!/usr/bin/env bash

# Call the shared checker script in "tracked" mode
REPO_ROOT="$(git rev-parse --show-toplevel)"
exec "$REPO_ROOT/scripts/git-large-file-check.sh" tracked
```

---

## Installation (add to a new repo)

1. Add `scripts/git-large-file-check.sh` (copy from the example above).
2. Create `scripts/hooks/` and add `pre-commit` and `pre-push` (copy from examples above).
3. Make script and hooks executable:
   ```bash
   chmod +x scripts/git-large-file-check.sh scripts/hooks/pre-commit scripts/hooks/pre-push
   ```
4. One-time per clone, tell git to use the hooks directory:
   ```bash
   git config core.hooksPath scripts/hooks
   ```

## Why core.hooksPath

By default, git looks for hooks in `.git/hooks/`, which is not version-controlled. Anything you put there is not shared when others clone the repo.

Using `git config core.hooksPath scripts/hooks` points git at `scripts/hooks/` inside the repo. Those files are version-controlled, so they are included when users clone. Each developer only needs to run the `git config` command once after cloning to activate the hooks.

## Recipe: Worked example (my_git_repo)

This section walks through adding large-file protection to a fresh repo named `my_git_repo`. Use it to understand how the pieces fit together.

**1. Create and enter the repo:**
```bash
mkdir my_git_repo && cd my_git_repo
git init
```

**2. Create the scripts layout:**
```bash
mkdir -p scripts/hooks
```

**3. Add the checker script** — Create `scripts/git-large-file-check.sh` with the full content from the Example scripts section above.

**4. Add the hooks** — Create `scripts/hooks/pre-commit` and `scripts/hooks/pre-push` with the content from the examples above.

**5. Make them executable:**
```bash
chmod +x scripts/git-large-file-check.sh scripts/hooks/pre-commit scripts/hooks/pre-push
```

**6. Activate hooks (one-time):**
```bash
git config core.hooksPath scripts/hooks
```

**7. Resulting layout:**
```
my_git_repo/
├── .git/
├── scripts/
│   ├── git-large-file-check.sh
│   └── hooks/
│       ├── pre-commit
│       └── pre-push
└── ... (your project files)
```

**8. Verify** — Add a small file, commit, push. The pre-commit hook runs on `git commit`; the pre-push hook runs on `git push`. Create a file larger than 60MB and try to add/commit it — the hook should block the operation.

**9. For collaborators** — When someone clones `my_git_repo`, they get `scripts/` and `scripts/hooks/` automatically. They only need to run step 6 once: `git config core.hooksPath scripts/hooks`.

## Troubleshooting

- **Skip the check temporarily** (use sparingly): `git commit --no-verify` or `git push --no-verify`.
- **Add large files legitimately** — Use [Git LFS](https://git-lfs.github.com/) to track large files (TIFFs, datasets, etc.). Install LFS, run `git lfs track "*.tif"` (or your pattern), commit `.gitattributes`, then add and commit the files as usual.

---

## Recommended hardening for `acqstore/`

### 1) Blocklist `.zarr/` trees (path-based), not just size-based

Even small `.zarr/` trees often contain hundreds/thousands of chunk files and will quickly bloat git history.
So treat **any** Zarr directory-store as “never commit” by default.

Add a **path-based blocklist** to your checker script, e.g.:

- Reject any path that matches:
  - `*.zarr/**` (directory stores)
  - `*.ome.zarr/**`
  - `**/.zarr/**` (if you keep them nested)
  - `**/data/**` (optional, if you keep datasets under a standard folder)

And also reject common “accidental artifacts”:
- `*.tif`, `*.tiff` above a small threshold (e.g. 5–10 MB) unless explicitly allowed
- `*.parquet` above threshold (if someone exports huge tables)

**Escape hatch:** allow an explicit allowlist (e.g. `docs/_static/**`), or require Git LFS for specific patterns if you truly need to track them.

### 2) Add a CI guard (GitHub Actions) so the main branch is protected

Local hooks are great, but CI is the real safety net.

Add a workflow like `.github/workflows/large-files.yml` that runs on PRs and pushes:

- checks the **diff** (new/modified files) for:
  - size > MAX
  - path matches the `.zarr` blocklist
- fails the build with a clear message and next steps (use `.gitignore`, move data out, or use Git LFS).

### 3) Add `.gitignore` defaults (strongly recommended)

At minimum:

- `*.zarr/`
- `*.ome.zarr/`
- `**/datasets/**` (if you standardize)
- `**/*.tif`
- `**/*.tiff`

This prevents the most common “oops, I committed a dataset” scenario.

### 4) (Optional) Git LFS policy

If you later decide to allow *some* large binaries, standardize it:

- Track with LFS: `*.tif`, `*.tiff`, `*.czi`, `*.nd2`, `*.oir`, `*.zip`
- Still keep `.zarr/` directories blocked (LFS works poorly for huge directory trees).

---

## Minimal CI workflow skeleton (example)

Create: `.github/workflows/large-files.yml`

```yaml
name: Large file guard

on:
  pull_request:
  push:

jobs:
  guard:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - name: Run large-file guard
        shell: bash
        run: |
          bash scripts/git-large-file-check.sh tracked
```

If you want the CI to check **only changes in the PR**, enhance the script to accept a “diff-base” and check only files changed vs that base SHA.

