from nicegui import ui, native

@ui.page('/')
def main() -> None:
    ui.label('Hello from minimal NiceGUI native app')
    ui.button('Click me', on_click=lambda: ui.notify('clicked'))

if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        native=True,
        reload=False,
        port=native.find_open_port(),
        title='NotarySmokeNiceGUI',
    )