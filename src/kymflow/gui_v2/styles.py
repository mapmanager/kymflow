from nicegui import ui

def install_global_styles() -> None:
    ui.add_css("""
    /* KymFlow: unified expansion header alignment */
    .kym-expansion-header {
        padding-left: 0 !important;
        margin-left: -12px !important;
    }

    .kym-expansion-header .q-item__section--avatar {
        min-width: 28px !important;
        padding-right: 4px !important;
    }
    """)

def kym_expansion(title: str, *, value: bool = False):
    return ui.expansion(title, value=value).props('header-class="kym-expansion-header"')