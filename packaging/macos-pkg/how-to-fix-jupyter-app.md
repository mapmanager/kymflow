# KymFlow Jupyter.app Fix Roadmap

## Purpose

`KymFlow Jupyter.app` is intended to be a normal macOS launcher for KymFlow's JupyterLab environment:

- created during `.pkg` install
- opened by users from `~/Documents/KymFlow/KymFlow Jupyter.app`
- launches JupyterLab rooted at `~/Documents/KymFlow`
- provides a friendly app entry point compared to `Open KymFlow.command`

The goal is to keep the app visible and manageable like a normal macOS app while the server is running.

---

## Current Build and Install Wiring (Source of Truth)

### Build-time wiring

From `packaging/macos-pkg/build_pkg.sh`:

- copies `scripts/make_jupyter_app.sh` into `build/pkgbuild-scripts/`
- copies local icon `icons/icon-green.icns` into payload as `payload/resources/AppIcon.icns`
- packages both into the component pkg via `pkgbuild --scripts`

### Install-time wiring

From `packaging/macos-pkg/scripts/postinstall.sh`:

- creates `Open KymFlow.command` (fallback launcher)
- calls `make_jupyter_app.sh` with:
  - `USER_HOME`
  - `APP_ROOT`
  - `WORKSPACE_ROOT`
  - `PACKAGED_VERSION`
- resulting bundle path:
  - `~/Documents/KymFlow/KymFlow Jupyter.app`

### App bundle contents currently generated

From `packaging/macos-pkg/scripts/make_jupyter_app.sh`:

- `Contents/Info.plist`
  - `CFBundleIdentifier=org.cudmore.kymflow.jupyter`
  - `CFBundleExecutable=launch_jupyter`
  - bundle version fields set from installed KymFlow version
- `Contents/MacOS/launch_jupyter`
  - shell launcher
  - starts JupyterLab from:
    - `~/Library/Application Support/kymflow-pkg/venv/bin/jupyter`
  - logs to:
    - `~/Library/Application Support/kymflow-pkg/logs/jupyter-app-launch.log`
- `Contents/Resources/AppIcon.icns`

---

## Problem Statement

Observed behavior from real runs:

1. User double-clicks `KymFlow Jupyter.app`.
2. App icon bounces in Dock.
3. JupyterLab opens in browser and works.
4. App icon then disappears from Dock/menu bar.
5. Re-running can bounce/hang intermittently; users may force-quit and retry.

Runtime evidence:

- `lsof -nP -iTCP:8888 -sTCP:LISTEN` shows active Python listener (Jupyter server is alive).
- PIDs change across runs after manual kill, confirming this is not stale old install state.

Implication:

- launch succeeds, but the app process model is not behaving like a normal persistent macOS app instance.

---

## Solutions Tried So Far (and Outcome)

### Attempt A (earlier version): `exec "$JUPYTER_BIN" ...`

- replaced bundle launcher process with Python process
- known to break Launch Services/Dock association with the app bundle
- clearly bad for persistent Dock identity

Status: rejected.

### Attempt B (current): remove `exec`, run Jupyter as child process

- expected to keep bundle script process alive
- still observed: Dock icon disappears while Jupyter keeps serving
- issue persists in user testing

Status: insufficient fix.

---

## Why the Current Architecture Is Brittle

`KymFlow Jupyter.app` currently uses a shell script (`Contents/MacOS/launch_jupyter`) as the main executable. Even without `exec`, this is still a non-native process model for a "normal" app lifecycle:

- no real AppKit app object/lifecycle
- no persistent menu bar app state management
- weak LaunchServices behavior for repeated opens while a server process is already alive
- no explicit single-instance policy and no attach/reopen behavior

In short: this is a launcher bundle, not a full app runtime.

---

## Target Behavior (Definition of Done)

When a user double-clicks `KymFlow Jupyter.app`:

- Dock icon appears and remains while server is running
- second launch does not hang
- if server is already running, app should reopen browser or focus existing session
- user can quit app from Dock/menu and server exits cleanly

---

## Recommended Fix Strategy

## Phase 1: Stabilize current shell launcher (short-term mitigation)

1. Add single-instance lock in launcher (`$APP_ROOT/run/`):
   - PID file + liveness check
   - if running, open browser and exit success
2. Add explicit port conflict handling:
   - if 8888 already bound by non-owned process, show clear alert/log and exit
3. Add signal handling:
   - trap TERM/INT and kill child Jupyter cleanly

Expected value:

- reduces "every other launch hangs"
- improves re-launch behavior
- still not guaranteed to behave as a true native app lifecycle

## Phase 2: Build a real minimal native wrapper app (recommended final fix)

Implement a tiny macOS AppKit launcher (Swift) that:

1. Starts as a normal GUI app process (persistent Dock identity).
2. Spawns and supervises Jupyter child process.
3. Implements:
   - single-instance behavior
   - "open existing session" on second launch
   - graceful quit that stops child server
4. Writes logs to same app root log directory.
5. Uses same bundle identifier/icon and packaged install paths.

Expected value:

- fixes disappearing Dock icon class of issues
- consistent relaunch behavior
- app lifecycle aligns with user expectations

## Phase 3: Packaging integration for native wrapper

1. Add native app template/binary into packaging assets.
2. Update `make_jupyter_app.sh` to:
   - copy native executable (instead of shell script body)
   - keep Info.plist/icon wiring
3. Keep `Open KymFlow.command` as fallback during transition.
4. Extend `smoke_test.sh` with app lifecycle checks.

---

## Validation Plan

For each build candidate:

1. Fresh install:
   - open app once, verify Dock icon persists
2. Reopen while server running:
   - no hang/bounce loop
   - browser opens/focuses existing session
3. Quit from Dock:
   - app exits
   - Jupyter server process exits
   - `lsof -nP -iTCP:8888 -sTCP:LISTEN` is empty
4. Reopen after quit:
   - clean start
5. Confirm logs:
   - installer log
   - jupyter app launch/runtime logs

---

## Notes and Constraints

- Keep install locations under user home:
  - `~/Library/Application Support/kymflow-pkg`
  - `~/Documents/KymFlow`
- Do not move launchers to `/Applications` in this scope.
- Keep `.command` fallback until native wrapper is fully verified.

---

## Files Relevant to This Roadmap

- `packaging/macos-pkg/scripts/make_jupyter_app.sh`
- `packaging/macos-pkg/scripts/postinstall.sh`
- `packaging/macos-pkg/build_pkg.sh`
- `packaging/macos-pkg/smoke_test.sh`
- `packaging/macos-pkg/readme-jupyterlab-app.md`
- `packaging/macos-pkg/resources/conclusion.html`
