# test_logging.py
import logging
from nicegui import ui

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


@ui.page("/")
def index():
    log.info("building page")
    ui.button("Click me", on_click=lambda: log.info("button clicked"))


ui.run()
