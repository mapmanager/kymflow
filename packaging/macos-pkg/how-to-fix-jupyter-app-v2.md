# How to Fix KymFlow Jupyter App, v2

_Last updated: 2026-03-30T13:30:55.073555+00:00_

## Purpose

This document is a developer roadmap for replacing the current shell-backed macOS Jupyter launcher app with a small native Swift/AppKit launcher.

It is based on the current source-of-truth files provided for this work:

- `how-to-fix-jupyter-app.md`
- `make_jupyter_app.sh`
- `postinstall.sh`
- `build_pkg.sh`

This roadmap is specifically about the **installed Jupyter launcher app** created by the pkg installer. It is **not** about the hypothetical NiceGUI desktop app.

---

## Short version

The current shell-backed `.app` is the wrong process model for the behavior you want.

### Current problem
When the user launches:

```text
~/Documents/KymFlow/KymFlow Jupyter.app
```

the app icon bounces, JupyterLab opens in the browser, the Dock icon disappears, but the Jupyter server continues running in the background.

### Desired behavior
You want:

- a persistent Dock icon while Jupyter is running
- a real app presence, not a transient wrapper
- the ability to quit from the Dock and have that also stop the running Jupyter server

### Proposed fix
Stop trying to make the shell-backed app persist in the Dock; replace the shell launcher with a tiny native Swift/AppKit wrapper that supervises the Jupyter child process.

That native wrapper becomes the real macOS app process.
Jupyter becomes a child process that the app launches, tracks, and terminates.

---

## Problem statement

## What exists now

The current installer creates a small macOS app wrapper for the JupyterLab launcher.
That app bundle is generated during install and lives under the user workspace.

The current app shape is effectively:

```text
~/Documents/KymFlow/KymFlow Jupyter.app/
  Contents/
    Info.plist
    MacOS/
      launch_jupyter
    Resources/
      AppIcon.icns
```

The current `launch_jupyter` is shell-backed.

The installed runtime and workspace model are user-scoped, not system-scoped:

- runtime:
  ```text
  ~/Library/Application Support/kymflow-pkg
  ```
- workspace:
  ```text
  ~/Documents/KymFlow
  ```

That user-scoped model is correct and should be preserved.

## Observed runtime behavior

On first run:

- the app icon appears and bounces in the Dock
- JupyterLab opens in the browser
- the app icon disappears from the Dock
- the Jupyter server remains alive in the background

You confirmed this with:

```bash
lsof -nP -iTCP:8888 -sTCP:LISTEN
```

and saw a live Python process still listening on port 8888.

This means:

- Jupyter is running correctly
- the browser launch is working
- the shell-backed launcher app is **not** maintaining the Dock/app lifecycle

## Root cause

This is not really a Jupyter problem.
It is a macOS app lifecycle problem.

A shell executable inside `Contents/MacOS/` is not giving you the persistent AppKit-managed app behavior you actually want.

Even if the shell process launches the right command and even if it avoids `exec`, the launcher still does not reliably behave like a real macOS foreground application with:

- stable Dock identity
- relaunch semantics
- quit handling
- managed child-process supervision

That is why the Dock icon disappears even though the server remains alive.

---

## Proposed solution

Replace the shell-backed executable with a small native Swift/AppKit launcher.

That native launcher will:

- run as a real macOS app process
- remain alive in the Dock while Jupyter is running
- launch Jupyter as a child process
- optionally detect/reuse an already-running Jupyter instance
- intercept quit requests
- terminate the child Jupyter process on quit
- exit when the child exits, if that is the desired behavior

This is the smallest architecture change that solves the actual problem.

---

## Why Swift/AppKit is the right fix

## What not to do

Do not continue trying to force the shell app to persist in the Dock.

You already have evidence that the shell-backed approach launches Jupyter but does not maintain the app presence you want.

Further shell tweaks may improve edge cases, but they do not solve the real lifecycle problem.

## Why AppKit

A small AppKit launcher gives you:

- native Dock lifecycle
- a real application process
- predictable quit handling
- clean child process spawning
- a path to later enhancements like menu items, status, or “server already running” UX

## Scope boundary

This does **not** mean turning KymFlow into a native app.

It only means replacing the tiny launcher executable inside the app bundle with a native wrapper.

Your current runtime model remains unchanged:

- Jupyter still comes from the installed venv
- workspace still lives in `~/Documents/KymFlow`
- runtime still lives in `~/Library/Application Support/kymflow-pkg`

---

## Expected final bundle structure

The app bundle structure can remain the same:

```text
~/Documents/KymFlow/KymFlow Jupyter.app/
  Contents/
    Info.plist
    MacOS/
      launch_jupyter
    Resources/
      AppIcon.icns
```

The critical change is:

- `Contents/MacOS/launch_jupyter` becomes a compiled native executable
- it is no longer a shell script

The icon path remains:

```text
Contents/Resources/AppIcon.icns
```

and should continue to come from:

```text
resources/AppIcon.icns
```

during install-time generation.

---

## Design goals for the native launcher

The native wrapper should satisfy all of the following:

### 1. Persistent Dock presence
The Dock icon should remain present while the launcher app is alive.

### 2. Same Jupyter launch logic as today
It should launch the same installed Jupyter runtime you already use:

```text
~/Library/Application Support/kymflow-pkg/venv/bin/jupyter
```

with the same workspace root:

```text
~/Documents/KymFlow
```

### 3. Clean quit behavior
When the user quits from the Dock or app menu:

- terminate the Jupyter child process
- wait briefly for clean shutdown
- force-kill if necessary
- then quit the app

### 4. No Terminal window
The launcher should not rely on Terminal or `.command`.

### 5. Logs go to file
Because no Terminal is visible, stdout/stderr and launcher events should be logged to a file.

### 6. Future-ready
The wrapper should be minimal now, but should leave room for later:
- single-instance behavior
- reopen/focus behavior
- “already running” detection
- menu-based controls

---

## Recommended architecture

## Parent-child model

The Swift/AppKit launcher is the **parent** process.
Jupyter is the **child** process.

The parent is responsible for:

- locating the installed runtime
- launching the child
- monitoring the child
- handling app lifecycle events
- shutting the child down when the app quits

This is the correct inversion.

Do not try to make Jupyter “be” the app.

## Runtime paths

Continue using the existing user-scoped install model:

- app root:
  ```text
  ~/Library/Application Support/kymflow-pkg
  ```
- venv:
  ```text
  ~/Library/Application Support/kymflow-pkg/venv
  ```
- workspace root:
  ```text
  ~/Documents/KymFlow
  ```
- log directory:
  ```text
  ~/Library/Application Support/kymflow-pkg/logs
  ```

Do not introduce `/Library/...` paths.
Do not introduce system-wide install paths.

---

## Behavioral specification

## On app launch

The native launcher should:

1. resolve:
   - `APP_ROOT`
   - `WORKSPACE_ROOT`
   - `LOG_DIR`
   - `JUPYTER_BIN`
2. ensure the log directory exists
3. open a runtime log file, for example:
   ```text
   ~/Library/Application Support/kymflow-pkg/logs/jupyter-app-runtime.log
   ```
4. decide whether a Jupyter server is already running
5. if no server is running:
   - launch JupyterLab as a child process
   - keep the app alive in the Dock
6. if a server is already running:
   - do not start a duplicate server
   - optionally open/focus browser on the existing URL
   - keep or focus the app instance

## While running

The native launcher should:

- keep the Dock presence alive
- monitor the child process
- optionally capture or redirect output to log file
- optionally maintain PID/state info

## On app quit

When the user chooses **Quit** from Dock or app menu:

1. if child Jupyter process exists:
   - send termination
   - wait a few seconds
   - escalate to kill if still alive
2. exit the app

## On child exit

If the Jupyter child exits on its own:

- the app can either:
  - quit automatically, or
  - remain open briefly and then quit
- for first implementation, automatic quit is reasonable

---

## Single-instance / already-running strategy

This is an important design choice.

### Minimal first implementation
For v1 of the native launcher, it is acceptable to skip single-instance logic and only focus on:

- one launcher instance
- one child Jupyter process
- proper quit behavior

### Better implementation
Track state in a user-scoped run directory:

```text
~/Library/Application Support/kymflow-pkg/run/
```

Possible files:

- `jupyter.pid`
- `jupyter.url`
- `jupyter.port`

On launch:

- if PID exists and process is alive, and port is reachable:
  - treat server as already running
  - open browser to existing URL instead of spawning a new one

This is recommended for v2, but you can choose to include it in v1 if convenient.

---

## Logging plan

Since the launcher app will not show a Terminal window, logging becomes more important.

## Recommended log file

```text
~/Library/Application Support/kymflow-pkg/logs/jupyter-app-runtime.log
```

## Recommended log contents

The native launcher should log at least:

- launcher startup
- resolved paths
- Jupyter executable path
- workspace root
- child process PID
- browser launch or reuse behavior
- quit requests
- child termination
- abnormal child exit

This will make debugging much easier.

---

## Security / trust model

This launcher app is being generated locally during install by your already distributed pkg.

That matters.

### Why this is favorable
A locally generated small app wrapper is usually a better trust model than distributing a separate unsigned app directly to users.

### Current recommendation
For the first implementation:

- generate the launcher app locally during `postinstall`
- do not add separate app signing complexity immediately
- test behavior on a second machine / second user account

### When separate app signing would matter
If you later switch to distributing a prebuilt `.app` bundle directly, that is a different trust model and should be treated like a separately distributed app artifact.

For the current locally generated launcher model, that extra step is not the first thing to solve.

---

## Implementation roadmap

## Phase 1 — define the new launcher strategy

### Objective
Freeze the design before coding.

### Tasks
- confirm that the app remains generated locally during `postinstall`
- confirm that the bundle location stays:
  ```text
  ~/Documents/KymFlow/KymFlow Jupyter.app
  ```
- confirm that the app continues to launch Jupyter rooted at:
  ```text
  ~/Documents/KymFlow
  ```
- confirm that the icon source remains:
  ```text
  resources/AppIcon.icns
  ```

### Deliverable
A stable target spec for the native launcher.

---

## Phase 2 — replace shell launcher with native executable

### Objective
Replace the shell `launch_jupyter` with a compiled Swift/AppKit binary.

### Tasks
- create a tiny Swift AppKit project or a single-file Swift executable
- compile it as the launcher executable named:
  ```text
  launch_jupyter
  ```
- embed it into:
  ```text
  KymFlow Jupyter.app/Contents/MacOS/
  ```

### Deliverable
A minimal native launcher binary that can run as the app’s executable.

---

## Phase 3 — implement the child-process launch

### Objective
Launch the installed Jupyter runtime from the native wrapper.

### Tasks
- resolve:
  ```text
  ~/Library/Application Support/kymflow-pkg/venv/bin/jupyter
  ```
- spawn:
  ```text
  jupyter lab --notebook-dir="$HOME/Documents/KymFlow"
  ```
- keep the parent app process alive

### Deliverable
A Dock-persistent native launcher that successfully starts Jupyter.

---

## Phase 4 — add quit supervision

### Objective
Make Dock/app quit terminate the child Jupyter process.

### Tasks
- intercept app termination event
- if child exists:
  - terminate gracefully
  - wait briefly
  - kill if needed
- then exit app

### Deliverable
Dock quit correctly shuts down the Jupyter server.

---

## Phase 5 — add logging

### Objective
Make the launcher debuggable without Terminal.

### Tasks
- create/open:
  ```text
  ~/Library/Application Support/kymflow-pkg/logs/jupyter-app-runtime.log
  ```
- write lifecycle entries
- optionally redirect child output

### Deliverable
Persistent runtime log for the launcher app.

---

## Phase 6 — optionally add already-running detection

### Objective
Avoid duplicate Jupyter servers.

### Tasks
- add a run directory under app support
- track PID and maybe URL/port
- on launch, detect whether the old server is still alive
- if alive:
  - open browser to it
  - skip spawning a duplicate

### Deliverable
Safer relaunch behavior.

This phase can be deferred if you want to first solve Dock persistence and quit behavior.

---

## Phase 7 — integrate with installer

### Objective
Wire the new native launcher generation into the current installer flow.

### Tasks
- update `make_jupyter_app.sh`
- stop writing a shell script to `Contents/MacOS/launch_jupyter`
- instead copy/build/install the native launcher binary there
- keep `Info.plist` and icon generation logic
- optionally keep `Open KymFlow.command` as fallback

### Deliverable
The pkg install creates the native Jupyter app wrapper automatically.

---

## Phase 8 — update smoke testing

### Objective
Verify the new launcher exists after install.

### Tasks
- update `smoke_test.sh` to assert:
  ```text
  ~/Documents/KymFlow/KymFlow Jupyter.app
  ```
- optionally assert:
  ```text
  ~/Documents/KymFlow/KymFlow Jupyter.app/Contents/MacOS/launch_jupyter
  ~/Documents/KymFlow/KymFlow Jupyter.app/Contents/Info.plist
  ```

### Deliverable
Smoke test covers the new app wrapper.

---

## File layout changes

## Existing generated bundle layout to keep

```text
~/Documents/KymFlow/KymFlow Jupyter.app/
  Contents/
    Info.plist
    MacOS/
      launch_jupyter
    Resources/
      AppIcon.icns
```

## Source tree changes expected

At minimum, expect changes to:

```text
packaging/macos-pkg/
  scripts/
    make_jupyter_app.sh        # modify
    postinstall.sh             # modify
  resources/
    AppIcon.icns               # keep using
```

Depending on how you build the Swift launcher, you may also introduce something like:

```text
packaging/macos-pkg/
  app_launcher/
    launch_jupyter.swift
```

or a small build helper for that launcher.

---

## Why this roadmap is the right next move

Because it directly addresses the real failure mode.

You already know:

- Jupyter itself launches correctly
- the browser opens
- the server stays alive

So the remaining problem is not Python or Jupyter.
It is the **launcher app process**.

A tiny native wrapper solves exactly that.

It is also the smallest possible architectural change that gets you:

- persistent Dock presence
- real quit behavior
- future app-level control

without changing the core KymFlow runtime model.

---

## Acceptance criteria

The implementation is successful when all of the following are true:

1. User double-clicks:
   ```text
   ~/Documents/KymFlow/KymFlow Jupyter.app
   ```
2. Dock icon remains visible while Jupyter is running
3. JupyterLab opens in browser
4. Jupyter server is running from the installed venv
5. User chooses **Quit** from the Dock/app menu
6. Jupyter server stops
7. App exits cleanly
8. No Terminal window is required
9. A log file exists for launcher runtime debugging

---

## Recommended next concrete development step

The next concrete step is:

- define the minimal Swift/AppKit launcher design and source file layout
- then update `make_jupyter_app.sh` and `postinstall.sh` to generate the app using that native launcher instead of the shell script

That should be the next implementation pass.
