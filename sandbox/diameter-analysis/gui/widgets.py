from __future__ import annotations

from dataclasses import is_dataclass, fields
from enum import Enum
from typing import Any, Callable, get_origin, get_args, Union

from nicegui import ui


def _field_label(name: str) -> str:
    return name.replace("_", " ")


def _unwrap_optional(tp: Any) -> Any:
    origin = get_origin(tp)
    if origin is Union:
        args = [a for a in get_args(tp) if a is not type(None)]
        return args[0] if len(args) == 1 else tp
    return tp


def _select_value(args: Any) -> Any:
    # NiceGUI/Quasar may send dicts like {'value': ..., 'label': ...}
    if isinstance(args, dict) and "value" in args:
        return args["value"]
    return args


def _coerce_enum(enum_cls: type[Enum], raw: Any) -> Enum:
    v = _select_value(raw)

    # If Quasar emits index integers (0,1,...) map by enum order.
    if isinstance(v, int):
        members = list(enum_cls)
        if 0 <= v < len(members):
            return members[v]

    # Otherwise, expect v is the Enum.value (typically a string)
    return enum_cls(v)  # type: ignore[arg-type]


def dataclass_editor_card(
    obj: Any,
    *,
    title: str,
    on_change: Callable[[str, Any], None],
    header_actions: Callable[[], None] | None = None,
    dense: bool = True,
) -> ui.card:
    if not is_dataclass(obj):
        raise TypeError("dataclass_editor_card expects a dataclass instance")

    with ui.card().classes("w-full"):
        with ui.row().classes("w-full items-center justify-between"):
            ui.label(title).classes("text-lg font-semibold")
            if header_actions is not None:
                with ui.row().classes("items-center gap-2"):
                    header_actions()
        motion_fields = {"max_edge_shift_um", "max_diameter_change_um", "max_center_shift_um"}
        motion_controls: list[Any] = []

        def _set_motion_controls_enabled(enabled: bool) -> None:
            for ctl in motion_controls:
                try:
                    if enabled:
                        ctl.enable()
                    else:
                        ctl.disable()
                except Exception:
                    pass

        with ui.grid(columns=2).classes("w-full gap-3"):
            for f in fields(obj):
                name = f.name
                tp = _unwrap_optional(f.type)
                value = getattr(obj, name)

                ui.label(_field_label(name)).classes("text-sm text-gray-600")

                if isinstance(value, bool) or tp is bool:
                    w = ui.switch(value=bool(value))
                    if name == "enable_motion_constraints":
                        def _on_motion_toggle(e, n=name) -> None:
                            enabled = bool(_select_value(e.args))
                            on_change(n, enabled)
                            _set_motion_controls_enabled(enabled)

                        w.on("update:model-value", _on_motion_toggle)
                    else:
                        w.on(
                            "update:model-value",
                            lambda e, n=name: on_change(n, bool(_select_value(e.args))),
                        )
                elif isinstance(value, int) or tp is int:
                    w = ui.number(value=int(value), step=1)
                    w.on(
                        "update:model-value",
                        lambda e, n=name: on_change(
                            n,
                            int(_select_value(e.args)) if _select_value(e.args) is not None else 0,
                        ),
                    )
                elif isinstance(value, float) or tp is float:
                    w = ui.number(value=float(value), step=0.01)
                    w.on(
                        "update:model-value",
                        lambda e, n=name: on_change(
                            n,
                            float(_select_value(e.args)) if _select_value(e.args) is not None else 0.0,
                        ),
                    )
                elif isinstance(value, Enum) or (isinstance(tp, type) and issubclass(tp, Enum)):
                    enum_cls: type[Enum] = type(value) if isinstance(value, Enum) else tp  # type: ignore[assignment]

                    # Use list of enum values for maximum NiceGUI compatibility.
                    # NiceGUI may emit index ints or the selected value; we handle both in _coerce_enum().
                    options = [e.value for e in enum_cls]
                    current = value.value if isinstance(value, Enum) else None

                    dd = ui.select(options=options, value=current)

                    dd.on(
                        "update:model-value",
                        lambda e, n=name, ec=enum_cls: on_change(n, _coerce_enum(ec, e.args)),
                    )
                    w = dd
                else:
                    w = ui.input(value="" if value is None else str(value))
                    w.on("update:model-value", lambda e, n=name: on_change(n, _select_value(e.args)))

                if dense:
                    w.classes("w-full")
                if name in motion_fields:
                    motion_controls.append(w)
                    if hasattr(obj, "enable_motion_constraints"):
                        _set_motion_controls_enabled(bool(getattr(obj, "enable_motion_constraints")))

        return ui.card()
