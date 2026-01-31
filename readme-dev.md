
## TODO

### 20260130

- add test for total number of kym events

- add acqimage channel stats for img data, (mean, min, max), do this per roi?
  this could be core function when we (i) add/create roi?

- add version to kym flow/velocity analysis
  original in <folder name>, if loaded becomes v0.0
  on running curr kym flow analysis becomes v1.0

  on kymanalysis load velocity, look for old v0.0 in <folder name> analysis, load it and mark vel analysis as v0.0

- in kymanalysis, expand _isdirty to include
  (i) kym flow dirty
  (ii) roi dirty
  (iii) metadata dirty (acqimage), we have this?
  (iv) kym flow event dirty

- h and v ui splitter, can we turn off the v scrollbar?
  h scroll bar is usefull

- on flow analysis, hide progress when finished
- on flow analysis, round progress to 2 decimaal place

- when left tool bar is open, click the current icon to minimize

- in kym event view, on add new even
  user selects x-range
  add event
  select in table
  [todo] select new event rect in plot

### done

enclose analyze flow widget and event analysis in their own (two different) sperators

in kym flow view with window points, analyze flow, cancel, etc.
 Enclose the analyze flow 'widget' in a seperator named 'Flow Analysis'.

remove the ui label 'analysis'

Do the same for 'event analysis widget, enclose it in a seprator named 'event analysis'

remove the label 'Event Analysis'

ask, do not guess

### done

clear kym event selection when consuming detectevents

when kym event list recieves EventDetection event, it needs to cancel its current selection. we should have an api for this, it might be similar to when the same kym event view recieves a folder selected or file selected event (it might have similar code to cancel selection).

### save dialog on app quit

when we quit the app, we have some sort of handler to, fo example, set user config values

when we quit the the, first thing we need to do (before setting user config) is:

1. check if acqimagelist has any kymfile/acqfile that are dirty (like when we switch folder) and if acqimagelist is dirty, we need a dialog saying 'analysis is dirty. are you sure you want to quit'. add ok and cancel button, on cancel button we want to somehow cancel the quit.

examine code and determine if this is possible. in particular if we can 




## Fresh install

``` bash
rm -rf .venv
uv venv
uv pip install -e ".[gui]"
uv run python -m kymflow.gui.app
```

Or with uv sync

```bash
rm -rf .venv
uv sync --extra gui
uv run python -m kymflow.gui.app
```

## Install test

```bash
uv sync --extra test --extra gui
```


## Run nicegui with environment variables

src/kymflow/gui/main.py has two environment variables to contrtol the nicegui app

`KYMFLOW_GUI_RELOAD`:
 - 1 will run in reload mode
 - 0 will not (use for distributing the app)

`KYMFLOW_GUI_NATIVE`:
 - 1 will run nicegui in a native standalone browser (load folder is flakey!!!)
 - 0 will run nicegui in a browser (chrome) tab

```
KYMFLOW_GUI_NATIVE=1 uv run python -m kymflow.gui.main
```