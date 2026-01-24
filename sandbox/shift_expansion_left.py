from nicegui import ui

ui.page_title('Expansion header shift (native-safe, with CSS layers)')

# NiceGUI v3 uses CSS cascade layers (@layer). If you add plain CSS, Quasar/NiceGUI
# styles in later layers can win and your rule appears to "do nothing".
# Put your custom class into a late layer (e.g. "overrides") so it reliably applies.
ui.add_css("""
@layer overrides {
  /* Reusable knob: apply this class to the EXPANSION HEADER via header-class */
  .my-expansion-header-shift-left {
    margin-left: -24px !important;  /* adjust: -8px, -12px, -16px, -24px */
  }
}
""")

with ui.column().classes('p-6 gap-4'):

    ui.label('Default expansion').classes('text-lg font-semibold')
    with ui.expansion('Default Header', value=True).classes('w-full'):
        ui.label('Body content')

    ui.separator()

    ui.label('Shifted header via header-class').classes('text-lg font-semibold')
    # IMPORTANT: header-class applies the class to the Quasar header element itself,
    # avoiding brittle selectors like ".q-expansion-item__header".
    with ui.expansion('Shifted Header', value=True) \
            .props('header-class="my-expansion-header-shift-left"') \
            .classes('w-full'):
        ui.label('Body content')

ui.run(native=True)