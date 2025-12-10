
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