# demo_win_size_app_v5.py
from __future__ import annotations

import asyncio
import threading
import time
from typing import Optional, Tuple

from nicegui import app, ui

Rect = Tuple[int, int, int, int]

# One timer for the lifetime of the app/session (native desktop app = one window)
_rect_polling_installed = False
_runtime_apply_installed = False

# Shutdown coordination: stop scheduling tasks once shutdown begins
SHUTTING_DOWN = False

# Keep timer handles so we can cancel them on shutdown
_rect_poll_timer = None
_apply_rect_timer = None


# ----------------------------
# Native-only helpers
# ----------------------------
def enable_confirm_close_if_native() -> None:
    """Enable OS-level 'Are you sure you want to quit?' prompt (native only)."""
    native = getattr(app, "native", None)
    if native is None:
        return  # native=False (browser)
    native.window_args["confirm_close"] = True


def set_initial_window_position_if_native(x: int, y: int) -> None:
    """Best (no-flash) way: set x/y BEFORE ui.run() so pywebview creates window at that position."""
    native = getattr(app, "native", None)
    if native is None:
        return
    native.window_args["x"] = int(x)
    native.window_args["y"] = int(y)


def set_hidden_if_native(hidden: bool) -> None:
    """Optional: try to create the native window hidden (if supported) to reduce 'move flash'."""
    native = getattr(app, "native", None)
    if native is None:
        return
    native.window_args["hidden"] = bool(hidden)


async def try_get_rect(tag: str) -> Optional[Rect]:
    """Fetch current native window rect (x, y, w, h). Returns None if unavailable."""
    native = getattr(app, "native", None)
    if native is None:
        print(f"[{tag}] app.native is None")
        return None

    win = getattr(native, "main_window", None)
    if win is None:
        print(f"[{tag}] app.native.main_window is None")
        return None

    try:
        size = await win.get_size()        # (w, h) or None
        pos = await win.get_position()     # (x, y) or None
    except Exception as e:
        print(f"[{tag}] get_size/get_position raised: {type(e).__name__}: {e}")
        return None

    if not size or not pos:
        print(f"[{tag}] size={size!r} pos={pos!r} (one is None/empty)")
        return None

    try:
        w, h = int(size[0]), int(size[1])
        x, y = int(pos[0]), int(pos[1])
    except Exception as e:
        print(f"[{tag}] coercion failed size={size!r} pos={pos!r}: {type(e).__name__}: {e}")
        return None

    return (x, y, w, h)


async def move_resize_window_if_possible(x: int, y: int, w: int, h: int) -> bool:
    """Fallback (may flash): try moving/resizing at runtime if WindowProxy exposes move/resize."""
    native = getattr(app, "native", None)
    win = getattr(native, "main_window", None) if native else None
    if win is None:
        return False

    moved = resized = False

    # Some WindowProxy methods may be sync or async depending on version/backend.
    async def _maybe_await(result):
        if asyncio.iscoroutine(result):
            return await result
        return result

    move = getattr(win, "move", None)
    if callable(move):
        try:
            await _maybe_await(move(int(x), int(y)))
            moved = True
        except Exception as e:
            print(f"[move] failed: {type(e).__name__}: {e}")

    resize = getattr(win, "resize", None)
    if callable(resize):
        try:
            await _maybe_await(resize(int(w), int(h)))
            resized = True
        except Exception as e:
            print(f"[resize] failed: {type(e).__name__}: {e}")

    return moved or resized


def on_rect_changed(rect: Rect) -> None:
    """Hook for reacting to window rect changes (print now, save-to-config later)."""
    print(f"[poll] rect changed: {rect}")


def install_shutdown_cleanup() -> None:
    """Stop timers / scheduling immediately on shutdown and print thread debug."""
    def _dump_threads(tag: str) -> None:
        threads = threading.enumerate()
        print(f"[{tag}] threads={len(threads)}")
        for t in threads:
            # Keep it compact but useful
            print(f"  - name={t.name!r} daemon={t.daemon} alive={t.is_alive()} ident={t.ident}")

    def _on_shutdown() -> None:
        global SHUTTING_DOWN
        SHUTTING_DOWN = True
        print("[shutdown] app.on_shutdown fired -> cancelling timers and stopping scheduling")

        # Cancel our timers if they exist
        global _rect_poll_timer, _apply_rect_timer
        for label, timer_obj in [("rect_poll", _rect_poll_timer), ("apply_rect", _apply_rect_timer)]:
            if timer_obj is None:
                continue
            cancel = getattr(timer_obj, "cancel", None)
            if callable(cancel):
                try:
                    cancel()
                    print(f"[shutdown] cancelled timer: {label}")
                except Exception as e:
                    print(f"[shutdown] failed to cancel timer {label}: {type(e).__name__}: {e}")

        _dump_threads("shutdown")

    app.on_shutdown(_on_shutdown)


def install_rect_polling_once(*, poll_sec: float = 0.5, debounce_sec: float = 1.0) -> None:
    """Install ONE polling timer (native only) for the lifetime of the session.

    Uses app.timer (UI-independent) so it's safe to install from main() before ui.run().
    """
    global _rect_polling_installed, _rect_poll_timer
    if _rect_polling_installed:
        return
    _rect_polling_installed = True

    last: dict[str, Optional[Rect]] = {"rect": None}
    last_emit: dict[str, float] = {"t": 0.0}

    async def _poll() -> None:
        rect = await try_get_rect("poll")
        if rect is None:
            return

        if rect == last["rect"]:
            return
        last["rect"] = rect

        now = time.monotonic()
        if now - last_emit["t"] < debounce_sec:
            return
        last_emit["t"] = now

        on_rect_changed(rect)

    def _tick() -> None:
        # Don't schedule anything once shutdown begins
        if SHUTTING_DOWN:
            return
        if getattr(app, "native", None) is None:
            return
        asyncio.create_task(_poll())

    _rect_poll_timer = app.timer(poll_sec, _tick)
    print(f"[poll] installed polling timer via app.timer (poll_sec={poll_sec}, debounce_sec={debounce_sec})")


def install_runtime_rect_apply_once(*, target_rect: Rect, delay_sec: float = 0.35) -> None:
    """Apply full (x,y,w,h) at runtime as a fallback."""
    global _runtime_apply_installed, _apply_rect_timer
    if _runtime_apply_installed:
        return
    _runtime_apply_installed = True

    x, y, w, h = target_rect
    ran = {"done": False}

    async def _apply() -> None:
        if ran["done"]:
            return
        if SHUTTING_DOWN:
            return
        # Wait until window is actually available
        native = getattr(app, "native", None)
        if native is None or getattr(native, "main_window", None) is None:
            return
        ran["done"] = True

        print(f"[apply] attempting runtime move/resize to rect={target_rect}")
        ok = await move_resize_window_if_possible(x, y, w, h)
        print(f"[apply] runtime move/resize success={ok}")

        # If we created the window hidden, try to show it now (if supported)
        win = native.main_window
        show = getattr(win, "show", None)
        if callable(show):
            try:
                r = show()
                if asyncio.iscoroutine(r):
                    await r
                print("[apply] called win.show()")
            except Exception as e:
                print(f"[apply] win.show() failed: {type(e).__name__}: {e}")

    def _tick() -> None:
        if SHUTTING_DOWN:
            return
        if getattr(app, "native", None) is None:
            return
        asyncio.create_task(_apply())

    _apply_rect_timer = app.timer(delay_sec, _tick, once=True)


# ----------------------------
# UI pages
# ----------------------------
@ui.page("/")
def index() -> None:
    ui.label("Window size/position demo v5").classes("text-xl font-semibold")
    ui.label(
        "Adds shutdown cleanup: cancels timers + stops scheduling during shutdown to avoid hangs."
    ).classes("text-sm text-grey-7")

    async def _print_now() -> None:
        rect = await try_get_rect("button")
        print(f"[button] rect={rect}")

    ui.button("Print window rect", on_click=_print_now).props("dense")
    ui.link("Go to /batch", "/batch").classes("text-sm")


@ui.page("/batch")
def batch() -> None:
    ui.label("Batch page (same window)").classes("text-xl font-semibold")
    ui.label("Polling continues (installed once for the session).").classes("text-sm text-grey-7")
    ui.link("Back to /", "/").classes("text-sm")


# ----------------------------
# Entrypoint
# ----------------------------
def main() -> None:
    _native: bool = True
    _reload: bool = False

    # Mock target rect (x, y, w, h) we want to restore (later: load from your JSON config)
    target_rect: Rect = (100, 100, 1200, 800)
    x, y, w, h = target_rect

    # Install shutdown cleanup early so it always runs
    install_shutdown_cleanup()

    if _native:
        enable_confirm_close_if_native()
        set_initial_window_position_if_native(x, y)
        set_hidden_if_native(False)

        install_rect_polling_once(poll_sec=0.5, debounce_sec=1.0)
        install_runtime_rect_apply_once(target_rect=target_rect, delay_sec=0.35)

        ui.run(
            native=True,
            reload=_reload,
            window_size=(w, h),
            title="Window Rect Demo v5",
        )
    else:
        ui.run(
            native=False,
            reload=_reload,
            title="Window Rect Demo v5 (browser)",
        )


if __name__ in {"__main__", "__mp_main__"}:
    main()