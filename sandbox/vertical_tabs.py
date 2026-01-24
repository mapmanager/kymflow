from nicegui import ui

ui.page_title('Drawer + Vertical Tabs (compact)')

# Compact vertical tabs:
# - hide labels (icon-only)
# - shrink icon size
# - shrink tab padding/height so the column can be narrower
ui.add_css("""
/* icon-only tabs: hide label text */
.icon_only_tabs .q-tab__label { display: none; }

/* make the vertical tab buttons smaller (padding/height) */
.icon_only_tabs .q-tab {
  min-height: 34px;           /* default is larger; lower = tighter */
  padding: 0 6px;             /* reduce horizontal padding */
}

/* make the icons smaller */
.icon_only_tabs .q-tab__icon {
  font-size: 16px;            /* default often ~24px */
}

/* optional: reduce the inner content spacing a bit */
.icon_only_tabs .q-tab__content {
  padding: 0;
}
""")

# Top-level drawer (left)
with ui.drawer(side='left', value=True) \
    .props('behavior=desktop bordered') \
    .classes('w-[78rem] p-4 overflow-auto') as drawer:
    # Inside the drawer, we lay out: [icons] [panels] in a row
    with ui.row(wrap=False).classes('w-full items-start'):
        # Narrower tab column now that tabs are physically smaller
        with ui.tabs().props('vertical dense').classes('w-12 shrink-0 icon_only_tabs') as tabs:
            tab_one = ui.tab('tab_one', icon='home').tooltip('One')
            tab_two = ui.tab('tab_two', icon='science').tooltip('Two')
            tab_three = ui.tab('tab_three', icon='settings').tooltip('Three')

        # Panels: fill the remaining space
        with ui.tab_panels(tabs, value=tab_one).props('vertical animated').classes('flex-grow min-w-0 pl-3'):
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

# Top-level header with a simple drawer toggle
with ui.header().classes('items-center'):
    ui.button(icon='menu', on_click=drawer.toggle).props('flat')
    ui.label('My App').classes('text-lg font-semibold')

# Main content (top-level)
with ui.column().classes('p-6'):
    ui.label('Main content area').classes('text-2xl font-bold')
    ui.markdown('Click the menu icon to hide/show the left drawer.')

ui.run(native=True)  # set native=False if desired; same layout works