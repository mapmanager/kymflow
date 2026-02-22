# How-To: Run pytest on Git Push via GitHub Actions

This guide explains how to add a GitHub Actions workflow that runs pytest on every push (and pull request) to a branch. kymflow uses this pattern; you can replicate it for other repos like nicewidgets or acqstore.

## What it does

When you push to `main` (or open a PR targeting `main`), GitHub Actions runs your test suite in the cloud. If tests fail, the workflow fails and GitHub shows a red X on the commit or PR.

## Prerequisites

- A GitHub repo
- Python project with `pyproject.toml` and a `[test]` or equivalent extra for pytest
- Tests runnable with `pytest tests/` from the repo root

## Basic workflow

Create `.github/workflows/test.yml` (or `tests.yml`) in your repo:

```yaml
name: Tests

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    name: Run tests
    runs-on: ubuntu-latest

    strategy:
      matrix:
        python-version: ["3.11", "3.12"]

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: pip

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          python -m pip install ".[test]"

      - name: Run tests
        run: pytest tests/
```

**Key pieces:**

- `on: push/pull_request` — When to run.
- `matrix: python-version` — Run tests on multiple Python versions (optional but recommended).
- `cache: pip` — Speeds CI by caching pip packages.
- `pip install ".[test]"` — Install your package with the test extra (adjust to match your `pyproject.toml`).

## kymflow example

kymflow’s workflow ([.github/workflows/test.yml](../.github/workflows/test.yml)) is more involved:

- Installs `nicewidgets` from GitHub (not PyPI) because kymflow depends on it during development.
- Runs pytest twice with different coverage targets (`core` and `gui_v2`) for separate Codecov badges.
- Uses `fail_ci_if_error: false` on the Codecov upload step so CI does not fail if Codecov is misconfigured.

For a simpler project, the basic workflow above is enough.

## Critique: Possible improvements

If you replicate the kymflow pattern (or a similar one), consider these refinements:

1. **Pytest runs twice** — kymflow runs the full suite twice (once for core coverage, once for gui_v2). That doubles CI time. Prefer a single run with multiple `--cov` paths or `--cov-branch`, or combine coverage reports before upload.
2. **Use uv** — kymflow uses uv locally but CI uses pip. Using `setup-uv` and `uv sync` would match local practice and can speed CI.
3. **`fail_ci_if_error: false` on Codecov** — Codecov upload failures do not fail the job, so misconfiguration can go unnoticed. Use `true` (or omit) once Codecov is stable, or only use `false` for non-blocking uploads.
4. **Branch filtering** — The workflow runs on every push/PR to main. For busy repos, consider excluding docs-only or trivial changes to reduce CI load.
5. **Pin nicewidgets version** — Installing from the default branch of nicewidgets can break when that branch changes. Pin to a tag or commit for reproducible CI.
6. **Exclude data-dependent tests** — If you use markers like `requires_data`, add `-m "not requires_data"` to pytest in CI so tests that need local data do not fail.
7. **Multi-OS testing** — Tests run only on ubuntu-latest. Add macOS (and optionally Windows) if your code may behave differently across platforms.

## Recipe: Add to a new repo (my_git_repo)

1. **Create the workflow file:**
   ```bash
   mkdir -p .github/workflows
   # Create .github/workflows/test.yml with the basic workflow above
   ```

2. **Ensure `pyproject.toml` has a test extra:**
   ```toml
   [project.optional-dependencies]
   test = [
     "pytest>=7.4",
     "pytest-cov>=4.1.0",
   ]
   ```

3. **Ensure `[tool.pytest.ini_options]` points to your tests:**
   ```toml
   [tool.pytest.ini_options]
   testpaths = ["tests"]
   pythonpath = ["src"]   # if you use src layout
   ```

4. **Push to `main` (or open a PR).** GitHub will run the workflow. Check the **Actions** tab.

5. **Optional: add a status badge to README:**
   ```markdown
   [![Tests](https://github.com/OWNER/REPO/actions/workflows/test.yml/badge.svg)](https://github.com/OWNER/REPO/actions/workflows/test.yml)
   ```

## Optional: Coverage and Codecov

To collect coverage and upload to Codecov:

```yaml
- name: Run tests with coverage
  run: |
    pytest --cov=src/my_pkg --cov-report=xml tests/

- name: Upload to Codecov
  uses: codecov/codecov-action@v5
  with:
    files: ./coverage.xml
    token: ${{ secrets.CODECOV_TOKEN }}
    fail_ci_if_error: false
```

Add `CODECOV_TOKEN` in **Settings → Secrets and variables → Actions** (from codecov.io).

## Optional: uv instead of pip

If you use uv:

```yaml
- name: Install uv
  uses: astral-sh/setup-uv@v4

- name: Set up Python
  uses: actions/setup-python@v5
  with:
    python-version: ${{ matrix.python-version }}

- name: Install dependencies
  run: uv sync --group test

- name: Run tests
  run: uv run pytest tests/
```

## Troubleshooting

- **Tests pass locally but fail in CI** — Check Python version, OS differences, or missing env vars. Use the same Python version in the matrix as locally.
- **Import errors** — Ensure `pythonpath` in `pyproject.toml` or `PYTHONPATH` includes your source (e.g. `src`).
- **Workflow not running** — Confirm the file is at `.github/workflows/test.yml` and the `on:` triggers match your branch names.
- **Slow CI** — Add `cache: pip` (or uv cache), and avoid installing unnecessary extras.
