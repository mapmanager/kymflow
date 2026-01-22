"""Tests for navigation helpers."""

from __future__ import annotations

from types import SimpleNamespace

from kymflow.gui_v2 import navigation


class DummyContainer:
    def classes(self, *_args, **_kwargs):
        return self

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _tb):
        return False


class DummyButton:
    def __init__(self, *_args, **kwargs):
        self.on_click = kwargs.get("on_click")
        self.icon = kwargs.get("icon")
        self._props: list[str] = []
        self.disabled = False

    def props(self, value: str):
        self._props.append(value)
        return self

    def tooltip(self, *_args, **_kwargs):
        return self

    def disable(self):
        self.disabled = True
        return self


class DummyImage:
    def classes(self, *_args, **_kwargs):
        return self

    def on(self, *_args, **_kwargs):
        return self

    def tooltip(self, *_args, **_kwargs):
        return self


def test_inject_global_styles_adds_css(monkeypatch) -> None:
    """inject_global_styles should add CSS via ui.add_head_html."""
    captured = {}

    def add_head_html(css: str) -> None:
        captured["css"] = css

    monkeypatch.setattr(navigation.ui, "add_head_html", add_head_html)

    navigation.inject_global_styles()

    assert "q-expansion-item__container" in captured["css"]


def test_build_header_toggle_updates_icon(monkeypatch) -> None:
    """Theme toggle should update the icon after toggling."""
    buttons: list[DummyButton] = []

    def button_stub(*_args, **kwargs):
        btn = DummyButton(**kwargs)
        buttons.append(btn)
        return btn

    ui_stub = SimpleNamespace(
        header=lambda: DummyContainer(),
        row=lambda: DummyContainer(),
        button=button_stub,
        label=lambda *_args, **_kwargs: SimpleNamespace(classes=lambda *_a, **_k: None),
        image=lambda *_args, **_kwargs: DummyImage(),
        run_javascript=lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(navigation, "ui", ui_stub)

    class DummyContext:
        def __init__(self):
            self.toggle_calls = 0

        def toggle_theme(self, dark_mode):
            self.toggle_calls += 1
            dark_mode.value = not dark_mode.value

    context = DummyContext()
    dark_mode = SimpleNamespace(value=True)

    navigation.build_header(context, dark_mode)

    theme_button = next(
        btn for btn in buttons if btn.icon in {"light_mode", "dark_mode"}
    )
    theme_button.on_click()

    assert context.toggle_calls == 1
    assert any("icon=dark_mode" in value for value in theme_button._props)
