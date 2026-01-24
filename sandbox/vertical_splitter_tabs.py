from nicegui import ui

ui.page_title('Splitter + Vertical Tabs + Handle Toggle')

ui.add_css("""
/* icon-only tabs: hide label text */
.icon_only_tabs .q-tab__label { display: none; }

/* compact vertical tabs */
.icon_only_tabs .q-tab { min-height: 34px; padding: 0 6px; }
.icon_only_tabs .q-tab__icon { font-size: 16px; }
.icon_only_tabs .q-tab__content { padding: 0; }

/* one-knob sizing for ALL widgets inside the left tab panels */
.my-drawer-panel {
  font-size: 12px;          /* <- change this once to scale all panel typography */
  line-height: 1.2;
}

/* splitter handle container */
.handle_wrap {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}
""")

# Snap positions are percentages for the LEFT pane (before)
CLOSED = 6
OPEN_DEFAULT = 28
last_open = {'value': OPEN_DEFAULT}

with ui.splitter(value=CLOSED, limits=(CLOSED, 70)).classes('w-full h-screen') as splitter:

    def ensure_open() -> None:
        """If the left pane is collapsed, restore it to a reasonable open width."""
        if splitter.value <= (CLOSED + 2):
            splitter.value = last_open['value']

    # LEFT: tools (vertical tabs + panels)
    with splitter.before:
        with ui.row(wrap=False).classes('w-full h-full items-start'):
            with ui.tabs().props('vertical dense').classes('w-12 shrink-0 icon_only_tabs') as tabs:
                tab_one = ui.tab('tab_one', icon='home').tooltip('One')
                tab_two = ui.tab('tab_two', icon='science').tooltip('Two')
                tab_three = ui.tab('tab_three', icon='settings').tooltip('Three')

            # Apply my-drawer-panel HERE so all tab panel content inherits the same font sizing
            with ui.tab_panels(tabs, value=tab_one).props('vertical animated').classes(
                'flex-grow min-w-0 pl-3 pr-3 my-drawer-panel'
            ):
                with ui.tab_panel(tab_one):
                    ui.label('One').classes('text-lg font-semibold')
                    ui.input(label='Search').classes('w-full')

                with ui.tab_panel(tab_two):
                    ui.label('Two').classes('text-lg font-semibold')
                    ui.switch('Enable feature', value=True)
                    ui.slider(min=0, max=100, value=35).classes('w-full')

                with ui.tab_panel(tab_three):
                    ui.label('Three').classes('text-lg font-semibold')
                    ui.button('Do thing')

    # Auto-expand left pane when user clicks a tab icon (while minimized)
    for t in (tab_one, tab_two, tab_three):
        t.on('click', lambda e: ensure_open())

    # RIGHT: main content
    with splitter.after:
        with ui.column().classes('p-6 w-full h-full'):
            ui.label('Main content area').classes('text-2xl font-bold')
            ui.markdown('Drag the splitter, or click the handle button to snap open/closed.')

    # SEPARATOR: toggle button lives on the handle
    with splitter.separator:
        with ui.element('div').classes('handle_wrap'):
            def toggle_snap() -> None:
                # If open-ish, remember current width and close; else reopen to last width.
                if splitter.value > (CLOSED + 2):
                    last_open['value'] = splitter.value
                    splitter.value = CLOSED
                else:
                    splitter.value = last_open['value']

            ui.button(icon='chevron_left', on_click=toggle_snap).props('flat dense')

ui.run(native=True)