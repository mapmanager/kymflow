
## Fresh install

``` bash
rm -rf .venv
uv venv
uv pip install -e ".[gui]"
uv run python -m kymflow.gui.main
```

Or with uv sync

```bash
rm -rf .venv
uv sync --extra gui
uv run python -m kymflow.gui.main
```

## Install test

```bash
uv sync --extra test --extra gui
```
