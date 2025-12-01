
## Fresh install

``` bash
rm -rf .venv
uv venv
uv pip install -e ".[gui]"
uv run python -m kymflow.kymflow_gui.main
```

Or with uv sync

```bash
rm -rf .venv
uv sync --extra gui
uv run python -m kymflow.kymflow_gui.main
```

