# KymFlow macOS Installer (uv-based)

This project builds a native macOS `.pkg` without Constructor or Conda.

## Expected sibling layout

```text
parent/
├── kymflow/
│   ├── pyproject.toml
│   ├── src/
│   └── notebooks/
└── kymflow-pkg/
```

`build_pkg.sh` copies the installable project files from `../kymflow/` into `payload/` at build time.

## Runtime locations after install

Runtime and venv:

```text
~/Library/Application Support/KymFlow/
```

User workspace:

```text
~/Documents/KymFlow/
```

## Requirements

- macOS
- Xcode Command Line Tools
- `pkgbuild`
- `productbuild`
- internet access during install for `uv` bootstrap and package installation

## Build

From `kymflow-pkg/`:

```bash
./build_pkg.sh
```

Optional version override:

```bash
PKG_VERSION=0.1.1 ./build_pkg.sh
```

Output:

```text
dist/KymFlow-<version>.pkg
```

## Install

Double-click the generated `.pkg`.

The installer will:

1. copy the packaged `kymflow/` project into the user's Application Support
2. install `uv`
3. create a venv
4. install `jupyterlab`, `ipykernel`, and local `kymflow`
5. register a Jupyter kernel
6. create `~/Documents/KymFlow/{Notebooks,Data}`
7. create `~/Documents/KymFlow/Open KymFlow.command`

## Smoke test

After install:

```bash
./smoke_test.sh
```

## Signing / notarization

Suggested packaging order:

1. `pkgbuild`
2. `productbuild`
3. `productsign`
4. `notarytool`
5. `stapler`

This scaffold does not sign the package yet.


## viewing logs from .pkg install

```bash
grep -nE 'KymFlow|postinstall|ERROR|fail|uv|jupyter' /var/log/install.log | tail -n 200
```

