# codex_ticket_43_44_repo_split_execute_acqstore.md
# Ticket 43–44 — Repo split execution: create `acqstore/` sibling repo and extract Zarr core
#
# Scope: EXECUTE the plan from docs/repo_split_plan.md.
# Keep python import namespace `kymflow_zarr`.
#
# IMPORTANT: This ticket may require creating a new folder outside the current repo root.
# If Codex tooling cannot create sibling folders reliably, do the minimal manual step:
#   - create the empty folder `../acqstore` (relative to `kymflow/` repo root)
# Then continue with the automated steps.

## Preconditions
- `src/kymflow/core/zarr/docs/repo_split_plan.md` exists (from Ticket 41–42) and is approved.
- You are working in `kymflow_outer/kymflow/` repo.

## Goals
1. Create a new sibling folder: `kymflow_outer/acqstore/`
2. Populate it with the extracted project:
   - `pyproject.toml`
   - `src/kymflow_zarr/...`
   - `tests/`
   - `docs/`
   - `prompts/`
   - `examples/`
3. Ensure the extracted repo is independently runnable:
   - `uv run pytest -q` passes in `acqstore/`
4. Ensure the kymflow repo can develop against it:
   - document (or add a helper script) for `uv pip install -e ../acqstore`

## Step-by-step tasks

### 1) Create new repo skeleton
- Create folder `../acqstore` (sibling of `kymflow/`) if not already present.
- In `../acqstore`, initialize a git repo (if desired) OR leave as uncommitted folder; note status in report.

### 2) Move/copy files according to the plan
- Use `git mv` where possible within the same repo.
- If moving across repo boundaries requires `cp -R`, do it carefully and preserve structure.
- Target layout in `acqstore/`:
  - `pyproject.toml` at repo root
  - `src/kymflow_zarr/` under `src/`
  - `tests/` at repo root
  - `docs/` at repo root
  - `prompts/` at repo root
  - `examples/` at repo root

### 3) Fix paths and runner prompts in the new repo
- Update `prompts/runners/codex_run_ticket.md` to reflect the new repo paths.
- Ensure docs references (relative links) are correct after moving.

### 4) Validate extracted repo
From inside `acqstore/`:
- `uv run pytest -q`
- run at least one example (pick the simplest that does not require external data)

### 5) Minimal integration note for kymflow
In `kymflow/` repo, add a short note somewhere (choose one):
- `src/kymflow/core/zarr/README.md` (if that file remains as a stub)
- OR `kymflow/README.md` (developer section)
Explain:
- `uv pip install -e ../acqstore`
- how to run acqstore tests

### 6) Leave behind a stub in kymflow (optional but recommended)
Option A (recommended): Replace `src/kymflow/core/zarr/` with a small README stub that points to the new repo location.
- Do NOT keep duplicate source code in both places.

## Acceptance criteria
- `acqstore/` exists and contains the extracted project with correct layout.
- `uv run pytest -q` passes in `acqstore/`.
- Prompt runner works inside `acqstore/prompts/`.
- No remaining imports in `acqstore` reference old `kymflow.*` modules (search and confirm).
- `kymflow/` has clear developer note on editable install of `acqstore`.

## Commands to run (must be reported)
- In `acqstore/`: `uv run pytest -q`
- In `kymflow/`: (optional) a quick import smoke test that `kymflow_zarr` imports from the editable install
