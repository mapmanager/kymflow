# How-To: Run pytest on Git Push via GitHub Actions (acqstore-friendly)

This guide shows a **minimal, reliable** GitHub Actions workflow that runs `pytest` on every push and PR.
It is written with **src-layout projects** and **uv** in mind (matches local dev), but includes a pip fallback.

---

## What it does

- On `push` and `pull_request` to `main`, GitHub Actions:
  1. Checks out the repo
  2. Sets up Python
  3. Installs your package + test deps
  4. Runs `pytest`

---

## Recommended workflow (uv)

Create: `.github/workflows/tests.yml`

```yaml
name: Tests

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  workflow_dispatch:

concurrency:
  group: tests-${{ github.ref }}
  cancel-in-progress: true

jobs:
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 15

    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.11", "3.12"]

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install uv
        uses: astral-sh/setup-uv@v4

      # If you later add uv.lock, prefer `uv sync --group test`.
      - name: Install package + test deps
        run: |
          uv pip install -e ".[test]"

      - name: Run pytest
        run: |
          uv run pytest -q
```

### Why this is a good default
- Matches your local workflow (`uv run pytest`).
- Avoids surprising environment drift between local and CI.
- Uses `concurrency` so multiple pushes don’t stack up.

---

## pip fallback workflow (if you don’t want uv in CI)

```yaml
name: Tests

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: pip

      - name: Install
        run: |
          python -m pip install --upgrade pip
          python -m pip install -e ".[test]"

      - name: Test
        run: pytest -q
```

---

## Project config checklist

### 1) `pyproject.toml` includes a test extra
```toml
[project.optional-dependencies]
test = [
  "pytest>=7",
  "pytest-cov>=4",
]
```

### 2) src-layout import reliability (optional but helpful)
If you have `src/` layout, either:
- install editable (recommended): `pip install -e .` / `uv pip install -e .`, or
- set `pythonpath`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

---

## Optional improvements (add only if needed)

- **Docs-only changes:** skip CI for markdown changes:
  - Use `paths-ignore:` under `on: push` and `pull_request`.
- **OS matrix:** add `macos-latest` if you care about platform differences.
- **Markers:** exclude data-dependent tests with `pytest -m "not requires_data"`.
- **System deps:** if you need OS libraries, add an `apt-get install ...` step.

---

## Troubleshooting

- **Import errors in CI:** confirm your editable install works and `tests/` are in repo.
- **Workflow not running:** confirm file is under `.github/workflows/` and branch is `main`.
- **Slow CI:** keep matrix small; add OS only when you need it.
