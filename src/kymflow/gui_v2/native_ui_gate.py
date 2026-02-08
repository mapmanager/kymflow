# kymflow/gui_v2/native_ui_gate.py
from __future__ import annotations

from contextlib import contextmanager
import threading
import time
from typing import Iterator, Optional


class NativeUiGate:
    """A small cooperative gate to prevent overlapping pywebview operations.

    Use-case:
      - Folder dialog is open (modal-ish) -> rect polling must skip.
      - Any other webview call that is sensitive can also acquire the gate.

    Implementation notes:
      - Re-entrant within the same thread (RLock).
      - Maintains a counter so nested busy() scopes work.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._busy_count = 0
        self._reason: Optional[str] = None
        self._since: float = 0.0

    @contextmanager
    def busy(self, reason: str = "native_ui") -> Iterator[None]:
        """Mark native UI as busy; cooperative callers should skip while busy."""
        with self._lock:
            self._busy_count += 1
            # only overwrite reason/since for the outermost acquisition
            if self._busy_count == 1:
                self._reason = reason
                self._since = time.monotonic()
        try:
            yield
        finally:
            with self._lock:
                self._busy_count = max(0, self._busy_count - 1)
                if self._busy_count == 0:
                    self._reason = None
                    self._since = 0.0

    def is_busy(self) -> bool:
        with self._lock:
            return self._busy_count > 0

    def status(self) -> tuple[bool, Optional[str], float]:
        """Return (busy, reason, seconds_busy)."""
        with self._lock:
            if self._busy_count <= 0:
                return False, None, 0.0
            return True, self._reason, max(0.0, time.monotonic() - self._since)