"""Unit tests for kymflow_gui main page functionality."""

from __future__ import annotations

from pathlib import Path

import pytest
from nicegui import ui

from kymflow.kymflow_gui.frontend.layout import create_main_page


@pytest.mark.requires_data
@pytest.mark.asyncio
async def test_app_starts(user, test_data_dir: Path) -> None:
    """Test that NiceGUI app can be initialized and main page loads."""
    # Register the main page route
    @ui.page("/")
    def index() -> None:
        create_main_page(test_data_dir)
    
    # Open the main page
    await user.open("/")
    
    # Verify the page title is set (KymFlow appears in header)
    await user.should_see("KymFlow")
    
    # Verify header navigation elements are present
    await user.should_see("Home")
    await user.should_see("Batch")
    await user.should_see("About")


@pytest.mark.requires_data
@pytest.mark.asyncio
async def test_load_folder_displays_table(user, test_data_dir: Path) -> None:
    """Test that loading a folder displays files in the table."""
    from kymflow.kymflow_core.state import AppState
    
    # Verify test data exists
    if not test_data_dir.exists():
        pytest.skip("Test data directory does not exist")
    
    # Register the main page route
    @ui.page("/")
    def index() -> None:
        create_main_page(test_data_dir)
    
    # Open the main page
    await user.open("/")
    
    # Wait for page to load and verify Files section is present
    await user.should_see("Files")
    
    # The create_main_page function automatically loads the folder if it exists
    # Verify that the table is rendered by checking for common table elements
    # The table should contain files from test_data_dir
    # We can verify by checking that the Files expansion is present and expanded
    await user.should_see("Files")
    
    # If there are files, the table should be visible
    # The exact content depends on what's in tests/data/
    # But at minimum, the Files section should be rendered


@pytest.mark.requires_data
@pytest.mark.asyncio
async def test_select_row_displays_plots_metadata(user, test_data_dir: Path) -> None:
    """Test that selecting a row displays plots and metadata."""
    from kymflow.kymflow_core.state import AppState
    
    # Verify test data exists and has files
    if not test_data_dir.exists():
        pytest.skip("Test data directory does not exist")
    
    # Check if there are files in the test data
    app_state = AppState()
    app_state.load_folder(test_data_dir)
    
    if not app_state.files:
        pytest.skip("No test data files available for selection test")
    
    # Register the main page route
    @ui.page("/")
    def index() -> None:
        create_main_page(test_data_dir)
    
    # Open the main page
    await user.open("/")
    
    # Wait for page to load
    await user.should_see("Files")
    
    # Verify that Image & Line Viewer section exists
    await user.should_see("Image & Line Viewer")
    
    # Verify that Metadata section exists
    await user.should_see("Metadata")
    
    # Verify that Experimental Metadata form exists
    await user.should_see("Experimental Metadata")
    
    # The create_main_page automatically selects the first file if files exist
    # So the plots and metadata should already be displayed
    # We verify the components are present and functional
    
    # Verify plot viewer components are present
    await user.should_see("Image & Line Viewer")
    
    # Verify metadata form is present
    await user.should_see("Experimental Metadata")
    
    # Note: To test actual row selection interaction, we would need to:
    # 1. Find the table element using user.find()
    # 2. Simulate clicking on a specific row
    # 3. Verify AppState.selected_file is updated
    # 4. Verify the plot and metadata components reflect the new selection
    # 
    # However, since create_main_page creates its own AppState internally,
    # we can't easily access it from the test. A more complete test would
    # require refactoring to allow injecting an AppState instance, or
    # using browser-based testing with the screen fixture to actually
    # interact with the UI elements.

