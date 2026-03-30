# KymFlow Windows Distribution Plan — Developer README

_Last updated: 2026-03-29T00:09:13.334991+00:00_

## Goal

This document outlines practical options for distributing KymFlow to Windows end users in a way that mirrors the recent macOS installer work:

1. Build a self-contained Windows application artifact on a local Windows machine.
2. Wrap that artifact in a Windows installer when appropriate.
3. Sign the installer or executable for end-user trust.
4. Distribute the resulting installer to end users through standard channels.

This README is intentionally strategic and workflow-oriented. It is not yet a drop-in implementation for the current repository.

---

## Recommendation summary

For KymFlow as it exists today, the most practical Windows path is:

- build on **Windows**
- package the Python/Jupyter application as a self-contained Windows app using either:
  - **PyInstaller** for fastest path, or
  - **Nuitka** for a more optimized compiled build
- wrap the output in an installer using:
  - **Inno Setup** for a simple single `.exe` installer, or
  - **WiX** if you later want a more enterprise-style MSI workflow
- sign the final `.exe` or installer with Windows code signing tools

For a Python app with a local runtime and a launcher-style workflow, the simplest milestone path is:

1. **PyInstaller or Nuitka**
2. **Inno Setup**
3. **SignTool**
4. distribute the signed installer

---

## Build environment options

## Option A — Build directly on a Windows machine

This is the simplest and most reliable option.

Why:
- Windows packaging tools are native to Windows
- code signing with SignTool is native to Windows
- installer authors such as Inno Setup and WiX are Windows-first

Recommended local build machine setup:
- Windows 11 or recent Windows 10
- Python matching your project needs
- build tool:
  - PyInstaller or Nuitka
- installer tool:
  - Inno Setup or WiX
- signing tools:
  - SignTool from the Windows SDK / Visual Studio tooling

This should be the default plan if you want the fewest surprises.

---

## Option B — Build on macOS using a Windows VM

If your main machine is macOS, the practical local-build option is usually:

- run a Windows VM
- build the Windows executable inside the VM
- sign it inside the VM
- export the final installer

This is usually easier than fighting cross-platform packaging gaps.

Recommended VM choices:
- Parallels Desktop
- VMware Fusion
- a separate Windows mini PC or laptop

---

## Option C — Build on CI later

Once the local workflow is stable, you can later move the Windows build to:

- GitHub Actions Windows runners
- another Windows CI host

That is useful later, but it is not the best first step if you are still shaping the packaging process.

---

## Tooling options for the application artifact

## 1. PyInstaller

### What it is
PyInstaller bundles a Python application and its dependencies so it can run without a separately installed Python interpreter. It supports one-folder and one-file style outputs. PyInstaller also documents that if you want to distribute for more than one OS, you should build on each target platform separately. citeturn804954search0turn804954search8turn804954search12

### Why it is attractive
- fastest path to a usable Windows build
- widely used in Python desktop distribution
- good fit for “make this Python app runnable by end users”

### Tradeoffs
- hidden imports and data files often need tuning
- one-file mode is convenient but sometimes slower to start
- antivirus false positives can happen with one-file style bootloaders

### Best use here
Use PyInstaller first if your goal is:
- get a Windows artifact working quickly
- learn what runtime files KymFlow really needs
- prove the end-to-end Windows packaging flow

---

## 2. Nuitka

### What it is
Nuitka is a Python compiler that can create standalone or onefile distributions and is designed to build executables that run without a separate Python installation. citeturn804954search1turn804954search13turn804954search21

### Why it is attractive
- often a stronger long-term production option than raw bundling
- can reduce “obviously Python app” feel
- can be a better fit if you want a polished compiled deliverable

### Tradeoffs
- more moving parts than PyInstaller
- can require more iteration to package correctly
- build times may be longer

### Best use here
Move to Nuitka after PyInstaller if:
- you want a more production-style executable
- startup/performance/packaging polish matters more
- the basic Windows workflow is already proven

---

## 3. Briefcase

### What it is
Briefcase supports Windows output formats including Windows app folders, Visual Studio projects, and MSI packaging. citeturn804954search2turn804954search6turn804954search10turn804954search14

### Why it may be less ideal here right now
Briefcase is attractive when you are leaning into a more “native app packaging” model. For KymFlow’s current path—where you already have a Python-oriented packaging mindset and may want to preserve a local runtime/workspace model—it is probably not the fastest next move.

### Best use here
Treat Briefcase as a secondary path, not the first Windows milestone.

---

## Installer options

## 1. Inno Setup

### What it is
Inno Setup is a long-standing Windows installer builder and supports creation of a single installer `.exe`. citeturn804954search3turn804954search23turn804954search15

### Why it matches your current macOS work
It maps well onto the installer thinking you already developed:
- staged payload
- post-install setup
- user-visible installation flow
- a single distributable installer file

### Likely fit for KymFlow
Very good first Windows installer choice.

### Why
- fast to get working
- produces a friendly installer exe
- good for per-user installs and simple setup logic
- easier than WiX for early iterations

---

## 2. WiX Toolset

### What it is
WiX is a Windows installer toolset for creating Windows Installer-based packages and is widely used for MSI-based workflows. citeturn492985search2turn492985search14turn492985search11

### Why you may want it later
- more enterprise-style installer story
- stronger MSI ecosystem
- better if you later need richer upgrade logic, repair flows, or corporate deployment

### Why not first
It is usually more complex than Inno Setup for a first working distribution.

---

## 3. MSIX

### What it is
MSIX is Microsoft’s modern Windows app packaging format. Microsoft describes it as a modern packaging experience for Windows apps, and the MSIX Packaging Tool can repackage existing desktop installers such as MSI or EXE into MSIX. citeturn492985search0turn492985search3turn492985search9turn492985search21

### Why it is interesting
- modern Windows packaging story
- clean install/uninstall model
- good if you later want more official Windows packaging integration

### Why not first
For your current stage, it is probably a second-phase refinement after you already have:
- a working executable
- a working installer
- a clear local data/workspace model

---

## Signing on Windows

### SignTool
Microsoft’s SignTool is the standard command-line tool for signing files, verifying signatures, and timestamping signatures. citeturn492985search1turn492985search7turn492985search13turn492985search16

### What you would sign
Depending on the chosen workflow:
- the packaged executable
- the installer exe
- possibly both

### Why this matters
Unsigned Windows executables and installers create trust friction for end users. If you are about to distribute to external users, code signing is the Windows equivalent of the trust work you just completed on macOS.

---

## Practical Windows path for KymFlow

## Recommended Phase 1
- build on Windows
- package KymFlow with **PyInstaller**
- wrap it with **Inno Setup**
- sign the installer with **SignTool**
- distribute the signed installer

This is the most practical “get to end users” plan.

## Recommended Phase 2
- try **Nuitka** as a replacement for PyInstaller if you want a more polished executable
- keep Inno Setup unless you hit a clear limitation
- evaluate MSIX only after the basic installer path is already stable

---

## Local-machine workflow options

## Workflow 1 — fastest path
- Windows machine
- PyInstaller
- Inno Setup
- SignTool

## Workflow 2 — more polished executable
- Windows machine
- Nuitka
- Inno Setup
- SignTool

## Workflow 3 — more enterprise packaging
- Windows machine
- PyInstaller or Nuitka
- WiX
- SignTool

## Workflow 4 — future Microsoft-native packaging
- first build EXE/MSI/installer
- then repackage to MSIX if needed

---

## Distribution to end users

Once you have a signed Windows installer or executable, common distribution options are:

- Dropbox shared link
- website download page
- GitHub Releases
- institutional file server
- customer-specific distribution portal

The immediate practical equivalents to what you just did on macOS are:
- upload signed installer to Dropbox
- share download link with end users
- provide a short install guide

If you later want more polish:
- put the installer on a dedicated downloads page
- publish release notes
- maintain versioned installers

---

## Suggested first Windows milestone

### Objective
Get a Windows end user from download to first launch successfully.

### Milestone output
One signed Windows installer that:
- installs KymFlow locally
- creates the required local runtime and workspace
- provides a Start Menu shortcut or desktop shortcut
- launches the app cleanly

### Suggested implementation choice
- **PyInstaller** for the application artifact
- **Inno Setup** for the installer
- **SignTool** for signing

---

## What maps from the macOS installer work

The following concepts transfer well from your macOS work:

- staged payload
- installer-managed vs user-managed content
- post-install setup logic
- launcher creation
- build script vs notarization/signing separation
- README-driven operational documentation

What changes on Windows:
- packaging tools
- signing tools
- installer format
- trust flow

---

## Proposed Windows packaging tree (draft)

```text
kymflow/
  packaging/
    windows-exe/
      build_exe.bat or build_exe.ps1
      build_installer.iss or build_installer.ps1
      sign_installer.bat or sign_installer.ps1
      README-windows.md
      resources/
      payload/         # generated
      build/           # generated
      dist/            # generated
```

This is only a proposed structure for the next phase.

---

## Recommended next 4 steps

1. Decide the Phase-1 stack:
   - PyInstaller + Inno Setup
   - or Nuitka + Inno Setup

2. Set up a Windows local build environment:
   - physical machine or VM
   - Python
   - chosen packager
   - chosen installer tool
   - SignTool availability

3. Create the first build script:
   - produce a self-contained Windows app artifact

4. Wrap that artifact in an installer:
   - build installer
   - sign it
   - test install on a clean Windows machine

---

## Bottom line

For KymFlow, the best next Windows plan is:

- **Build on Windows**
- **Start with PyInstaller**
- **Use Inno Setup to create a single installer EXE**
- **Sign with SignTool**
- **Distribute the signed installer**

Then, if needed:
- move from PyInstaller to Nuitka
- move from Inno Setup to WiX or MSIX only if the simpler path becomes limiting
