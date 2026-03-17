# Plan: Drawer tab click-to-close (toggle right panel)

**Status:** Implemented.

## Feature request (paraphrased)

- **Current:** Left toolbar has icons (Analysis, Plotting, Metadata, etc.). Clicking an icon opens the right panel (adjusts the NiceGUI splitter) and shows that tab’s content.
- **Desired:** If the right panel is already open and the user clicks the **same** icon that is currently showing, **close** the panel. So: first click opens (and shows that tab); second click on the same icon closes the panel. Other icons still open the panel and switch tab as today.

## Current behavior (from code)

- **home_page.py:** Main splitter `value=CLOSED` (6), `limits=(CLOSED, 70)`. `ensure_open()`: if `splitter.value <= CLOSED+2` then set `splitter.value = last_open['value']` (open). Drawer is rendered with `on_tab_click=ensure_open`. So every tab click only ever opens (or leaves open); there is no close-on-same-tab.
- **drawer_view.py:** Tabs (Analysis, Plotting, …) each have `t.on('click', lambda e: on_tab_click())` — callback takes no args. So the drawer does not tell the page *which* tab was clicked.
- **Double-click** on the splitter handle toggles open/closed (`_toggle_drawer_splitter`); that is unchanged.

## Minimal implementation (KISS, DRY)

1. **DrawerView:** When a tab is clicked, call `on_tab_click(clicked_tab)` (pass the tab element that was clicked). Store a reference to the tab panels (or tabs) so the parent can read the current selection.
2. **DrawerView:** Expose `get_current_tab()` returning the currently selected tab (e.g. `tab_panels.value`).
3. **home_page:** Track which tab has the drawer open (`last_open_tab`). Do not use `get_current_tab()` at click time—the framework may update the tab panel to the clicked tab before our handler runs, so we would wrongly close when switching to a different tab.
4. **home_page** `_on_tab_click(clicked_tab)`: If splitter is open and `clicked_tab == last_open_tab` then close drawer. Else set `last_open_tab = clicked_tab` and open drawer. We only close when the same tab that had the drawer open is clicked again.

No new events or bus usage; no change to double-click handle behavior. Single place for “open vs close” logic in home_page.

## Files to touch

- **gui_v2/views/drawer_view.py:** Store `_tab_panels` (or `_tabs`) in `render()`, add `get_current_tab()`, change tab click to `on_tab_click(clicked_tab)`.
- **gui_v2/pages/home_page.py:** Implement `_on_tab_click(clicked_tab)` with toggle logic; pass it to `drawer_view.render(on_tab_click=_on_tab_click)`.

## Edge cases

- **First load:** Panel closed; any tab click opens (current behavior).
- **Panel open, different tab clicked:** Open stays, tab switches (NiceGUI default); we only close when same tab is clicked again.
- **Panel open, same tab clicked:** Close panel.

## Implementation note (fix for wrong-close on tab switch)

We track `last_open_tab` (the tab that had the drawer open) in home_page instead of using `get_current_tab()` at click time. Reason: the tab panel value may update to the clicked tab before our handler runs, so `get_current_tab() == clicked_tab` would be true when switching tabs and we would incorrectly close the drawer. With `last_open_tab`, we only close when the user clicks the same tab that we last opened with.
