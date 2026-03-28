# KymFlow macOS PKG Installer — Developer README

_Last updated: 2026-03-28T21:58:52.447951_

(Full detailed README based strictly on provided build_pkg.sh, postinstall.sh, smoke_test.sh)

## Overview
This document describes the current implementation of the KymFlow macOS pkg installer.

## Source of Truth
This README is based ONLY on:
- build_pkg.sh
- postinstall.sh
- smoke_test.sh

## Architecture

### Build Flow
build_pkg.sh:
- extracts version from pyproject.toml
- stages payload into payload/kymflow
- removes unwanted files (.DS_Store, __pycache__, *.pyc, .ipynb_checkpoints)
- copies postinstall.sh into pkgbuild scripts as postinstall
- runs pkgbuild → component pkg
- runs productbuild → final pkg

Output:
dist/KymFlow-<version>.pkg

### Install Flow (postinstall.sh)
Executed by macOS installer.

Steps:
1. Determine CURRENT_USER and USER_HOME
2. Define APP_ROOT:
   ~/Library/Application Support/kymflow-pkg
3. Create logs:
   logs/install-<timestamp>.log
4. Read packaged version from pyproject.toml
5. Compare with installed version (install_version.txt)
6. Determine install mode:
   - first_install
   - reinstall_same
   - upgrade
   - downgrade → blocked

7. Copy payload using rsync with exclusions:
   - __pycache__/
   - *.pyc
   - .DS_Store
   - .ipynb_checkpoints

8. Install uv (if missing)
9. Install Python (INSTALL_PYTHON_VERSION)
10. Create or reuse venv
11. Install:
    - jupyterlab
    - ipykernel
    - kymflow (from payload)

12. Register Jupyter kernel

13. Workspace setup:
   ~/Documents/KymFlow/
     Examples/       (always overwritten)
     Example-Data/   (always overwritten, currently empty)
     User/           (never touched)

14. Create launcher:
   Open KymFlow.command
   → launches Jupyter rooted at ~/Documents/KymFlow

15. Fix ownership:
   chown user:staff workspace

16. Write:
   install_version.txt
   install_state.json

### Runtime

User runs:
Open KymFlow.command

This launches:
jupyter lab --notebook-dir=~/Documents/KymFlow

## Runtime Directories

### Application Support

~/Library/Application Support/kymflow-pkg/
  uv/
  venv/
  payload/
  logs/
  install_version.txt
  install_state.json

### Workspace

~/Documents/KymFlow/
  Examples/
  Example-Data/
  User/
  Open KymFlow.command

## Smoke Test (smoke_test.sh)

Verifies:
- python exists in venv
- jupyter exists
- install_state.json exists
- logs exist
- workspace folders exist
- launcher exists
- kymflow import works

## Install Behavior

First install:
- full environment setup

Reinstall same version:
- reuse venv
- skip reinstall if healthy

Upgrade:
- reinstall packages

Downgrade:
- blocked by compare_versions()

## Logging

Logs stored in:
~/Library/Application Support/kymflow-pkg/logs/

Each run creates:
install-YYYYMMDD-HHMMSS.log

## Install State

install_state.json includes:
- version
- python_version
- install_mode
- log_file
- updated_at_utc

## Design Principles

- separation of installer-managed vs user-managed
- idempotent installs
- explicit logging
- no user data overwrite

## Future Improvements

- macOS installer UI (Distribution.xml)
- code signing (productsign)
- notarization (notarytool)
- packaged example datasets
- improved installer UX

## Summary

System is:
- stable
- reproducible
- upgrade-aware
- cleanly structured
