# codex_ticket_41_42_repo_split_plan_acqstore.md
# Ticket 41–42 — Repo split plan: extract standalone `acqstore/` repo (keep import name `kymflow_zarr`)
#
# Scope: PLANNING ONLY. Do NOT move files yet. Produce a concrete, executable plan in docs/.
# Branch: work on current branch.

## Goals
1. Produce `docs/repo_split_plan.md` that precisely describes how to extract the current Zarr core project
   (currently under `src/kymflow/core/zarr/`) into a new sibling repo folder:
   `kymflow_outer/acqstore/`.
2. Keep the python import namespace **unchanged for now**:
   - package import remains `kymflow_zarr` (no rename in this ticket).
3. Ensure the plan addresses:
   - moving prompts/docs/tests/examples
   - how Codex tickets will be run after extraction
   - how kymflow will depend on the new repo during development (editable install)
4. Clarify what `indexers/` is and confirm it moves with the core (it is: dataset indexing framework).

## Important clarifications (must be reflected in the plan)
- The new repo is intended to become fully standalone and should not import from old kymflow modules.
- Old `kymflow/` code is a donor/reference only.
- `kym_dataset/` is **not** a required dependency; it may be moved into the new repo as reference-only (examples) and later deleted.

## Deliverables
Create / update:
- `src/kymflow/core/zarr/docs/repo_split_plan.md` (new)

## `docs/repo_split_plan.md` must include (minimum sections)
1. **Executive summary** (what/why)
2. **Current state inventory**
   - list the current subtrees under `src/kymflow/core/zarr/`:
     - `src/kymflow_zarr/` (core package)
     - `tests/`
     - `docs/`
     - `prompts/`
     - `examples/`
     - any others (e.g. `indexers/` if present as a module/subpackage)
3. **Target repo layout (acqstore/)**
   - propose the target tree, e.g.
     - `acqstore/pyproject.toml`
     - `acqstore/src/kymflow_zarr/...`
     - `acqstore/tests/...`
     - `acqstore/docs/...`
     - `acqstore/prompts/...`
     - `acqstore/examples/...`
4. **Exact move map**
   - a table mapping: `OLD_PATH -> NEW_PATH`
5. **Import namespace decision**
   - explicitly state: keep `kymflow_zarr` import name for now
6. **Local dev workflow**
   - how to work on both repos locally
   - `uv pip install -e ../acqstore` from within `kymflow/`
7. **Codex workflow after split**
   - where prompts live (in new repo)
   - how to run tickets (paths, runner)
8. **Validation checklist**
   - commands to run in the new repo:
     - `uv run pytest -q`
     - key examples (list explicitly; use relative paths after split)
9. **Rollback plan**
   - how to revert if extraction breaks something

## Notes on `indexers/`
- If there is an `indexers/` package or module in the current core, it should move with the core.
- In the plan doc, explain briefly that this is the dataset indexing framework (tables + incremental/staleness + extractors).

## Acceptance criteria
- `docs/repo_split_plan.md` exists and is concrete enough that a developer can execute it step-by-step.
- No file moves are performed in this ticket.
- No code behavior changes.

## Commands
Run and report results:
- `uv run pytest src/kymflow/core/zarr/tests -q` (or equivalent existing command in current layout)
