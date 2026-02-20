# demo_entry_options.py
"""
NiceGUI demo: entry widgets backed by pandas unique() options.

What this shows:
1) A "pick from existing" control using ui.select(options=unique_values)
   - user can search/filter by typing, but cannot create new values.
2) A "pick OR type new" control using ui.select(...) with Quasar's `use-input`
   and `new-value-mode=add-unique`
   - user can type a new value and press Enter to add it to options.

Run:
  uv run python demo_entry_options.py

Notes:
- NiceGUI does not require pandas for ui.select itself; pandas is used only to
  demonstrate generating options via df['col'].unique().
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional

import pandas as pd
from nicegui import ui


@dataclass
class AppState:
    """Holds shared option state for both selects."""
    options: List[str]


def build_demo_df() -> pd.DataFrame:
    """Create a tiny DataFrame with a categorical column."""
    return pd.DataFrame(
        {
            "condition": [
                "control",
                "saline",
                "drugA",
                "drugB",
                "control",
                "saline",
                "washout",
            ]
        }
    )


def reset_from_df(df: pd.DataFrame, state: AppState, sync: Callable[[], None]) -> None:
    """Reset the shared options list from the DataFrame's unique values."""
    state.options = sorted(df["condition"].dropna().astype(str).unique().tolist())
    sync()
    print(f"[reset] options={state.options!r}")


@ui.page("/")
def home() -> None:
    ui.page_title("Entry options demo (pandas unique -> ui.select)")

    df = build_demo_df()
    opts = sorted(df["condition"].dropna().astype(str).unique().tolist())
    state = AppState(options=opts)

    ui.label("Entry options from a DataFrame column").classes("text-xl font-semibold")
    ui.markdown(
        "We take `df['condition'].unique()` to build preset options.\n\n"
        "- **Top**: choose from existing options only.\n"
        "- **Bottom**: choose from options *or* type a new value (press Enter)."
    ).classes("text-sm text-gray-700")

    # ---- (1) Existing-only select -------------------------------------------------
    with ui.card().classes("w-full max-w-3xl"):
        ui.label("1) Preset options only (cannot create new)").classes("font-semibold")

        select_existing = ui.select(
            options=state.options,
            label="Condition (existing only)",
            value=state.options[0] if state.options else None,
        ).classes("w-full")

        # Quasar: allow typing to FILTER options; still does not create new values
        select_existing.props("use-input input-debounce=0 hide-selected fill-input")

        out_existing = ui.label("").classes("text-sm text-gray-600")

        def _on_existing_change(_: Optional[object] = None) -> None:
            out_existing.text = f"Selected (existing): {select_existing.value!r}"
            print(f"[existing] value={select_existing.value!r}")

        select_existing.on("update:modelValue", _on_existing_change)
        _on_existing_change()

    # ---- (2) Flexible select (existing + new) -------------------------------------
    with ui.card().classes("w-full max-w-3xl"):
        ui.label("2) Preset options + allow typing new").classes("font-semibold")

        select_flexible = ui.select(
            options=state.options,
            label="Condition (existing or new)",
            value=state.options[0] if state.options else None,
        ).classes("w-full")

        # Quasar: allow typing AND accept new values (press Enter)
        select_flexible.props(
            "use-input input-debounce=0 new-value-mode=add-unique hide-selected fill-input"
        )

        out_flexible = ui.label("").classes("text-sm text-gray-600")

        def _sync_options() -> None:
            # Keep both selects in sync with shared options
            select_existing.options = state.options
            select_flexible.options = state.options
            select_existing.update()
            select_flexible.update()

        def _on_flexible_change(_: Optional[object] = None) -> None:
            v = select_flexible.value
            if isinstance(v, str):
                vv = v.strip()
                # When user types a NEW value and presses Enter, Quasar emits it as modelValue.
                if vv and vv not in state.options:
                    state.options.append(vv)
                    state.options.sort()
                    print(f"[flex] added new option: {vv!r} -> total={len(state.options)}")
                    _sync_options()

            out_flexible.text = f"Selected (flexible): {select_flexible.value!r}"
            print(f"[flex] value={select_flexible.value!r}")

        select_flexible.on("update:modelValue", _on_flexible_change)
        _on_flexible_change()

        with ui.row().classes("gap-2"):
            ui.button("Print current options", on_click=lambda: print(f"[options] {state.options!r}"))
            ui.button(
                "Reset options from df.unique()",
                on_click=lambda: reset_from_df(df, state, _sync_options),
            ).props("outline")

    ui.separator()
    ui.label("DataFrame used").classes("font-semibold")
    ui.markdown(f"```text\n{df.to_string(index=False)}\n```").classes("text-sm")


def main() -> None:
    ui.run(reload=False, native=True)


if __name__ == "__main__":
    main()
