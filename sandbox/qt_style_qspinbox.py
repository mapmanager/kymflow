# filename: qt_style_qspinbox.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional, Literal

from nicegui import ui


SpinBoxSize = Literal["xs", "sm", "md", "lg"]


@dataclass
class SpinBoxConfig:
    """Configuration for a Qt-style compact spinbox widget.

    This config intentionally exposes only *stable* NiceGUI/Quasar APIs
    plus a small, well-scoped amount of CSS for height control.

    Attributes:
        size: Overall widget size preset ("xs", "sm", "md", "lg").
        label_width_px: Optional override for label width.
        input_width_px: Optional override for input width.
        commit_on_enter: Commit on Enter/Return.
        commit_on_blur: Commit on blur (Tab away / click away).
        live_update: If True, fire callbacks while typing.
    """
    size: SpinBoxSize = "sm"
    label_width_px: Optional[int] = None
    input_width_px: Optional[int] = None
    commit_on_enter: bool = True
    commit_on_blur: bool = True
    live_update: bool = False


# ---------------------------
# Size presets (single source of truth)
# ---------------------------

_SIZE_PRESETS: dict[SpinBoxSize, dict[str, Any]] = {
    "xs": {
        "label_width_px": 110,
        "input_width_px": 80,
        "font_class": "text-xs",
        "dense": True,
        "min_height_px": 24,
    },
    "sm": {
        "label_width_px": 140,
        "input_width_px": 110,
        "font_class": "text-sm",
        "dense": True,
        "min_height_px": 28,
    },
    "md": {
        "label_width_px": 170,
        "input_width_px": 140,
        "font_class": "text-base",
        "dense": False,
        "min_height_px": 36,
    },
    "lg": {
        "label_width_px": 200,
        "input_width_px": 170,
        "font_class": "text-lg",
        "dense": False,
        "min_height_px": 42,
    },
}


class QtStyleQSpinBox:
    """A compact, Qt-style numeric input for NiceGUI.

    Layout:
        Label | [ value ]

    Behavior:
        - No live updates unless explicitly enabled
        - Commit + fire on Enter and/or blur
        - Native number spinner arrows on hover
        - Keyboard-friendly (Tab, Enter, arrows)

    Styling philosophy:
        - Uses Quasar public props where possible (dense, outlined)
        - Uses Tailwind classes for width + font size
        - Uses ONE scoped CSS rule for vertical height control
    """

    def __init__(
        self,
        label: str,
        *,
        value: float = 0.0,
        step: float = 1.0,
        min_value: float | None = None,
        max_value: float | None = None,
        decimals: int | None = None,
        config: SpinBoxConfig | None = None,
    ) -> None:
        self._label_text = label
        self._step = float(step)
        self._min = min_value
        self._max = max_value
        self._decimals = decimals
        self._config = config or SpinBoxConfig()

        self._value = float(value)
        self._on_change: Optional[Callable[[float], None]] = None

        self._row: Optional[ui.row] = None
        self._label: Optional[ui.label] = None
        self._input: Optional[ui.input] = None

        self._build()
        self.set_value(self._value, notify=False)

    # ---------------------------
    # Public API
    # ---------------------------

    def on_change(self, handler: Callable[[float], None]) -> "QtStyleQSpinBox":
        """Register a callback fired when the value is committed."""
        self._on_change = handler
        return self

    def set_value(self, value: float, *, notify: bool = True) -> None:
        """Set the value programmatically."""
        v = self._round_if_needed(self._clamp(value))
        self._value = v
        if self._input:
            self._input.set_value(self._format_value(v))
        if notify and self._on_change:
            self._on_change(v)

    # ---------------------------
    # UI construction
    # ---------------------------

    def _build(self) -> None:
        preset = _SIZE_PRESETS[self._config.size]

        label_width = self._config.label_width_px or preset["label_width_px"]
        input_width = self._config.input_width_px or preset["input_width_px"]

        # with ui.row().classes("items-center gap-2"):
        with ui.row().classes("items-center gap-1"):
            self._label = ui.label(self._label_text).classes(
                f"{preset['font_class']} w-[{label_width}px]"
            )

            props = self._input_props(dense=preset["dense"])
            self._input = ui.input(value=self._format_value(self._value)).props(props).classes(
                f"{preset['font_class']} w-[{input_width}px] qt-spinbox-{self._config.size}"
            )

            if self._config.commit_on_enter:
                self._input.on("keydown.enter", self._on_commit)

            if self._config.commit_on_blur:
                self._input.on("blur", self._on_commit)

            if self._config.live_update:
                self._input.on("update:model-value", self._on_live_update)

        # Scoped CSS per size (small, controlled, unlikely to break)
        ui.add_css(
            f"""
.qt-spinbox-{self._config.size} .q-field__control {{
    min-height: {preset['min_height_px']}px;
}}
.qt-spinbox-{self._config.size} .q-field__native {{
    padding: 0;
}}
"""
        )

    def _input_props(self, *, dense: bool) -> str:
        tokens = []
        if dense:
            tokens.append("dense")
        tokens.extend(
            [
                "outlined",
                "hide-bottom-space",
                'type="number"',
                'inputmode="decimal"',
                f'step="{self._step}"',
            ]
        )
        if self._min is not None:
            tokens.append(f'min="{self._min}"')
        if self._max is not None:
            tokens.append(f'max="{self._max}"')
        return " ".join(tokens)

    # ---------------------------
    # Event handlers
    # ---------------------------

    def _on_commit(self, _e: Any) -> None:
        if not self._input:
            return
        text = self._input.value or ""
        v = self._round_if_needed(self._clamp(self._parse(text)))
        changed = v != self._value
        self._value = v
        self._input.set_value(self._format_value(v))
        if changed and self._on_change:
            self._on_change(v)

    def _on_live_update(self, e: Any) -> None:
        raw = getattr(e, "args", None)
        try:
            v = float(raw)
        except Exception:
            return
        self._value = self._clamp(v)
        if self._on_change:
            self._on_change(self._value)

    # ---------------------------
    # Helpers
    # ---------------------------

    def _parse(self, text: str) -> float:
        try:
            return float(text)
        except Exception:
            return self._value

    def _clamp(self, value: float) -> float:
        if self._min is not None:
            value = max(self._min, value)
        if self._max is not None:
            value = min(self._max, value)
        return value

    def _round_if_needed(self, value: float) -> float:
        return round(value, self._decimals) if self._decimals is not None else value

    def _format_value(self, value: float) -> str:
        if self._decimals is None:
            return str(value)
        return f"{value:.{self._decimals}f}"


# ---------------------------
# Demo
# ---------------------------

def onMyChange(v: float) -> None:
    print(f"[SpinBox] committed value = {v}")


def build_demo_ui() -> None:
    ui.label("Qt-style QSpinBox size demo").classes("text-base font-medium mb-4")

    # Example 1: EXTRA SMALL, very compact (e.g. dense parameter tables)
    QtStyleQSpinBox(
        "Threshold",
        value=3.0,
        step=0.5,
        min_value=0.0,
        max_value=10.0,
        decimals=2,
        config=SpinBoxConfig(
            size="xs",                 # 👈 smallest preset
            live_update=False,         # commit-only
        ),
    ).on_change(onMyChange)

    # Example 2: MEDIUM, more readable (e.g. main control panel)
    QtStyleQSpinBox(
        "Gain",
        value=1.0,
        step=0.1,
        min_value=0.0,
        max_value=5.0,
        decimals=2,
        config=SpinBoxConfig(
            size="xs",                 # 👈 larger preset
            live_update=False,
            input_width_px=160,        # 👈 manual override still works
        ),
    ).on_change(onMyChange)

    ui.input("Next field (Tab test)").props("outlined").classes("w-80 mt-4")

    _tmp = ui.add_body_html("""
    <div style="padding:10px">
    <label>Plain HTML number: </label>
    <input type="number" value="3" min="1" step="1" style="width:80px">
    </div>
    """)

# build_demo_ui()

if __name__ in {"__main__", "__mp_main__"}:
    build_demo_ui()
    ui.run()