# how-to-add-logging.md

This is a practical recipe for adding Python logging to a headless library (a package that is imported by other apps).

## Goals

- Library code can emit useful logs (`logger.debug/info/warning/...`).
- Importing the library **never** changes the host application's logging configuration.
- Host applications can opt-in to configure formatting/level/handlers.
- CLI tools and examples inside the repo can configure logging for themselves.

## 1) Library-side best practice

### Use module loggers

In each module:

```python
import logging
logger = logging.getLogger(__name__)
```

### Add a `NullHandler` at package import

In your top-level package `__init__.py`:

```python
import logging
logging.getLogger(__name__).addHandler(logging.NullHandler())
```

Why: prevents the "No handler could be found" warning while still not configuring global logging.

### Do **not** call `basicConfig()` in a library

Never call `logging.basicConfig(...)` from package import paths. That overrides the application's logging.

## 2) Provide an optional helper for apps

Create a helper module (example: `acqstore/logging_utils.py` or `acqstore/utils/logging.py`) that apps can call.

Recommended API:

- `configure_logging(level: str | int = "INFO", *, fmt: str | None = None, datefmt: str | None = None, force: bool = False) -> None`
- `set_log_level(level: str | int) -> None` (set your package logger level only)

Implementation notes:

- Configure **your package logger** (e.g. `logging.getLogger("kymflow_zarr")`) rather than the root logger.
- Optionally allow `force=True` to attach a handler even if one exists.
- Consider environment override for convenience:
  - `ACQSTORE_LOG_LEVEL=DEBUG` (or use your actual package name).

## 3) Example: configure in a script

```python
from kymflow_zarr.logging_utils import configure_logging

configure_logging("DEBUG")

# now import/use the rest
from kymflow_zarr.dataset import ZarrDataset
```

## 4) CLI / examples

Examples and CLI entrypoints *should* configure logging (because they are applications):

- Call `configure_logging()` at startup.
- Add a `--log-level` option (or env var).

## 5) Tests

- Library imports should not mutate root handlers.
- A smoke test can assert that calling `configure_logging()` results in at least one handler attached to the package logger.

## 6) Common pitfalls

- **Setting the root logger level in a library** → breaks host apps.
- **Multiple handlers** attached repeatedly → duplicate log lines.
- **Overly chatty info logs** in hot loops → use `debug` for per-record/per-pixel details.
