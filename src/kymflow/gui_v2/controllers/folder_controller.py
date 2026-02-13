"""Controller for handling path selection events.

This module provides a controller that translates SelectPathEvent intent events
from the UI into AppState path loading operations.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional

from nicegui import ui

from kymflow.gui_v2.state import AppState
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.events_folder import SelectPathEvent, CancelSelectPathEvent
from kymflow.gui_v2.thread_job_runner import ThreadJobRunner
from kymflow.gui_v2.window_utils import set_window_title_for_path
from kymflow.core.user_config import UserConfig
from kymflow.core.utils.logging import get_logger
from kymflow.core.utils.progress import ProgressMessage

logger = get_logger(__name__)

if TYPE_CHECKING:
    from kymflow.core.image_loaders.kym_image_list import KymImageList


class FolderController:
    """Controller that applies path selection events to AppState.

    This controller handles SelectPathEvent intent events (typically from FolderSelectorView)
    and triggers AppState.load_path(), which scans the path for kymograph
    files and updates the file list.

    Flow:
        1. User selects path → FolderSelectorView emits SelectPathEvent(phase="intent")
        2. This controller receives intent event → validates and loads path
        3. On success: emits SelectPathEvent(phase="state")
        4. On cancel: emits CancelSelectPathEvent
        5. AppState scans path and updates file list
        6. AppState callback → AppStateBridge emits FileListChanged
        7. FileTableBindings receives event → updates file table

    Attributes:
        _app_state: AppState instance to update.
        _user_config: UserConfig instance for persisting path selections.
        _bus: EventBus instance for emitting state/cancel events.
    """

    def __init__(self, app_state: AppState, bus: EventBus, user_config: UserConfig | None = None) -> None:
        """Initialize folder controller.

        Subscribes to SelectPathEvent intent-phase events from the bus.

        Args:
            app_state: AppState instance to update.
            bus: EventBus instance to subscribe to.
            user_config: Optional UserConfig instance for persisting path selections.
        """
        self._app_state: AppState = app_state
        self._user_config: UserConfig | None = user_config
        self._bus: EventBus = bus
        self._thread_runner: ThreadJobRunner[tuple["KymImageList", Path]] = ThreadJobRunner()
        bus.subscribe_intent(SelectPathEvent, self._on_select_path_event)
    
    def _detect_path_type(self, path: Path) -> tuple[bool, bool, bool]:
        """Detect the type of path (file, folder, or CSV).
        
        Args:
            path: Path to check.
        
        Returns:
            Tuple of (is_file, is_folder, is_csv). Only one will be True.
            If path doesn't exist, all will be False.
        """
        is_file = path.is_file()
        is_folder = path.is_dir()
        is_csv = is_file and path.exists() and path.suffix.lower() == '.csv'
        return (is_file, is_folder, is_csv)
    
    def _check_thread_runner_available(self, current_path: Optional[str]) -> bool:
        """Check if thread runner is available for path loading.
        
        Args:
            current_path: Current path from app_state (for cancellation if busy).
        
        Returns:
            True if thread runner is available, False if busy (and emits CancelSelectPathEvent).
        """
        if self._thread_runner.is_running():
            ui.notify("A load is already in progress", type="warning")
            if current_path:
                self._bus.emit(CancelSelectPathEvent(previous_path=current_path))
            return False
        return True
    
    def _persist_path_to_config(self, path: Path, depth: int, is_file: bool, is_csv: bool) -> None:
        """Persist path selection to user config.
        
        Args:
            path: Path to persist.
            depth: Depth value (0 for files/CSV, folder depth for folders).
            is_file: True if path is a file.
            is_csv: True if path is a CSV file.
        """
        if self._user_config is not None:
            if is_csv:
                self._user_config.push_recent_csv(str(path))
            else:
                config_depth = 0 if is_file else depth
                self._user_config.push_recent_path(str(path), depth=config_depth)

    def _on_select_path_event(self, e: SelectPathEvent) -> None:
        """Handle SelectPathEvent intent event.

        Loads the specified path (folder, file, or CSV) in AppState, which will trigger file
        scanning and emit FileListChanged via the bridge.
        
        Automatically detects CSV files by checking if the path exists, is a file, and has .csv extension.
        If depth is provided in the event, sets app_state.folder_depth before loading (for folders only).
        After successful load, emits SelectPathEvent(phase="state") and persists the path to user config.
        On cancellation, emits CancelSelectPathEvent.

        Args:
            e: SelectPathEvent (phase="intent") containing the path and optional depth.
        """
        new_path = Path(e.new_path)
        current_path = str(self._app_state.folder) if self._app_state.folder else None

        # 1. Thread runner check
        if not self._check_thread_runner_available(current_path):
            return
        
        # 2. Path type detection
        is_file, is_folder, is_csv = self._detect_path_type(new_path)
        
        # Handle CSV separately (early return)
        if is_csv:
            self._handle_csv_event_from_path(new_path, current_path)
            return
        
        # 3. Validation (path exists)
        if not (is_file or is_folder):
            logger.error(f'Path does not exist: "{new_path}"')
            ui.notify(f"Path does not exist: {new_path}", type="warning")
            if current_path:
                logger.debug(f'emitting CancelSelectPathEvent for previous path: "{current_path}"')
                self._bus.emit(CancelSelectPathEvent(previous_path=current_path))
            return
        
        # 4. Depth calculation
        # For files, depth is always 0 (ignored by AcqImageList)
        # For folders, use event depth or current app_state depth
        if is_file:
            depth = 0
        else:
            depth = e.depth if e.depth is not None else self._app_state.folder_depth
            if e.depth is not None:
                self._app_state.folder_depth = depth
        
        # 5. Unsaved changes check
        if self._app_state.files and self._app_state.files.any_dirty_analysis():
            self._show_unsaved_dialog(new_path, current_path, depth)
            return
        
        # 6. Route to appropriate handler (file vs folder)
        if is_file:
            self._finally_set_path(new_path, depth, is_file)
        else:
            self._start_threaded_load(
                new_path,
                depth=depth,
                is_file=False,
                is_csv=False,
                previous_path=current_path,
            )
    
    def _handle_csv_event_from_path(self, csv_path: Path, current_path: str | None) -> None:
        """Handle CSV file loading from path.
        
        Args:
            csv_path: Path to CSV file (already validated to exist and be .csv).
            current_path: Current path from app_state (for cancellation).
        """
        # Thread runner check
        if not self._check_thread_runner_available(current_path):
            return

        # Check for unsaved changes
        if self._app_state.files and self._app_state.files.any_dirty_analysis():
            self._show_unsaved_dialog(csv_path, current_path, 0)
            return
        
        # Not dirty - proceed with CSV load (threaded)
        self._start_threaded_load(
            csv_path,
            depth=0,
            is_file=True,
            is_csv=True,
            previous_path=current_path,
        )

    def _finally_set_path(self, path: Path, depth: int, is_file: bool) -> None:
        """Finalize path switch: load folder, save config, set title, emit event.
        
        This is called by both the non-dirty path and the confirmed dirty path.
        
        Args:
            path: The path to switch to.
            depth: The depth to use (0 for files, folder depth for folders).
            is_file: True if path is a file, False if folder.
        """
        # Load the path (folder/file/CSV)
        self._app_state.load_path(path, depth=depth)
        
        # Persist to user config
        self._persist_path_to_config(path, depth, is_file, is_csv=False)
        
        # Set window title
        set_window_title_for_path(path, is_file=is_file)
        
        # Emit state event to confirm successful load
        self._bus.emit(SelectPathEvent(
            new_path=str(path),
            depth=depth,
            phase="state",
        ))

    def _start_threaded_load(
        self,
        path: Path,
        *,
        depth: int,
        is_file: bool,
        is_csv: bool,
        previous_path: Optional[str],
    ) -> None:
        """Run a threaded load with progress and cancellation."""
        progress_label = None
        progress_bar = None
        cancel_button = None

        def on_cancel_click() -> None:
            if cancel_button is not None:
                cancel_button.props("disable")
            if progress_label is not None:
                progress_label.text = "Cancelling..."
            self._thread_runner.cancel()

        with ui.dialog() as dialog, ui.card():
            ui.label("Loading files...").classes("text-lg font-semibold")
            progress_label = ui.label("Starting...").classes("text-sm")
            progress_bar = ui.linear_progress(value=0.0).classes("w-full")
            with ui.row():
                cancel_button = ui.button("Cancel", on_click=on_cancel_click)

        def on_progress(msg: ProgressMessage) -> None:
            if progress_label is not None:
                progress_label.text = self._format_progress_message(msg)
            if progress_bar is not None:
                if msg.total is not None and msg.total > 0:
                    progress_bar.value = min(1.0, msg.done / msg.total)
                else:
                    progress_bar.value = 0.0

        def on_done(result: tuple["KymImageList", Path]) -> None:
            dialog.close()
            files, selected_path = result
            self._app_state._apply_loaded_files(files, selected_path)

            # Persist to user config
            self._persist_path_to_config(path, depth, is_file, is_csv)

            set_window_title_for_path(path, is_file=is_file or is_csv)

            self._bus.emit(SelectPathEvent(
                new_path=str(path),
                depth=0 if is_file or is_csv else depth,
                phase="state",
            ))

            try:
                if is_csv:
                    ui.notify(f"Loaded CSV: {path.name}", type="positive")
                else:
                    ui.notify(f"Loaded: {path.name}", type="positive")
            except RuntimeError as e:
                if "parent element" in str(e) or "slot" in str(e).lower():
                    # UI context is gone, skip notification
                    logger.error(f"Skipping notification - UI context deleted: {e}")
                else:
                    raise

        def on_cancelled() -> None:
            dialog.close()
            try:
                ui.notify("Load cancelled", type="warning")
            except RuntimeError as e:
                if "parent element" in str(e) or "slot" in str(e).lower():
                    # UI context is gone, skip notification
                    logger.error(f"Skipping notification - UI context deleted: {e}")
                else:
                    raise
            if previous_path:
                self._bus.emit(CancelSelectPathEvent(previous_path=previous_path))

        def on_error(exc: BaseException, tb: str) -> None:
            dialog.close()
            logger.error(f"Failed to load path: {exc}", exc_info=True)
            try:
                if is_csv and isinstance(exc, ValueError):
                    ui.notify(f"CSV error: {exc}", type="negative")
                else:
                    ui.notify(f"Failed to load: {exc}", type="negative")
            except RuntimeError as e:
                if "parent element" in str(e) or "slot" in str(e).lower():
                    # UI context is gone, skip notification
                    logger.error(f"Skipping notification - UI context deleted: {e}")
                else:
                    raise
            if previous_path:
                self._bus.emit(CancelSelectPathEvent(previous_path=previous_path))

        def worker_fn(cancel_event, progress_cb):
            result = self._app_state._build_files_for_path(
                path,
                depth=depth,
                cancel_event=cancel_event,
                progress_cb=progress_cb,
            )
            if result is None:
                raise RuntimeError(f"Path is neither file nor directory: {path}")
            return result

        dialog.open()
        self._thread_runner.start(
            ui_timer_factory=lambda dt, cb: ui.timer(dt, cb),
            poll_interval_s=0.05,
            worker_fn=worker_fn,
            on_progress=on_progress,
            on_done=on_done,
            on_cancelled=on_cancelled,
            on_error=on_error,
            cancel_previous=False,
        )

    def _format_progress_message(self, msg: ProgressMessage) -> str:
        """Format ProgressMessage for user-facing UI."""
        if msg.phase == "scan":
            prefix = "Scanning"
        elif msg.phase == "read_csv":
            prefix = "Reading CSV"
        elif msg.phase == "wrap":
            prefix = "Preparing files"
        elif msg.phase == "done":
            prefix = "Done"
        else:
            prefix = msg.phase

        if msg.total is not None and msg.total > 0:
            return f"{prefix}: {msg.done}/{msg.total}"

        if msg.detail:
            return f"{prefix}: {msg.detail}"

        return prefix

    def _load_folder(self, path: Path) -> None:
        """Load path with current depth and persist to config.
        
        Deprecated: Use _on_select_path_event() directly instead.
        
        Note: This method doesn't properly handle file vs folder depth (always uses app_state.folder_depth).
        Use _on_select_path_event() which correctly handles depth for both files and folders.
        """
        is_file = path.is_file()
        depth = 0 if is_file else self._app_state.folder_depth
        self._app_state.load_path(path, depth=depth)
        if self._user_config is not None:
            config_depth = 0 if is_file else depth
            self._user_config.push_recent_path(str(path), depth=config_depth)

    def _show_unsaved_dialog(self, new_path: Path, previous_path_str: str | None, depth: int) -> None:
        """Prompt before switching paths if unsaved changes exist.
        
        Args:
            new_path: The new path to switch to.
            previous_path_str: The previous path (for revert on cancel).
            depth: The calculated depth to use (already computed from event).
        """
        # Determine destination type (CSV, file, or folder)
        if new_path.is_file() and new_path.suffix.lower() == '.csv':
            dest_path_type = "CSV"
        elif new_path.is_file():
            dest_path_type = "file"
        else:
            dest_path_type = "folder"
        
        prev_path_type = "folder"
        if previous_path_str:
            previous_path = Path(previous_path_str)
            prev_path_type = "file" if previous_path.is_file() else "folder"
        
        with ui.dialog() as dialog, ui.card():
            ui.label(f'Unsaved changes in {prev_path_type}').classes("text-lg font-semibold")
            if previous_path_str:
                ui.label(previous_path_str).classes("text-sm")
            ui.label(f"If you switch to {dest_path_type} '{new_path.name}' now, those changes will be lost."
            ).classes("text-sm")
            with ui.row():
                ui.button(
                    "Cancel",
                    on_click=lambda: self._on_dialog_cancel(dialog, previous_path_str)
                ).props("outline")
                ui.button(
                    f"Switch to {dest_path_type}",
                    on_click=lambda: self._confirm_switch_path(dialog, new_path, previous_path_str, depth),
                ).props("color=red")

        dialog.open()
    
    def _on_dialog_cancel(self, dialog, previous_path: str | None) -> None:
        """Handle dialog cancellation - emit cancellation event."""
        dialog.close()
        if previous_path:
            self._bus.emit(CancelSelectPathEvent(previous_path=previous_path))

    def _confirm_switch_path(self, dialog, path: Path, previous_path: str | None, depth: int) -> None:
        """Confirm path switch after unsaved changes warning.
        
        Args:
            dialog: The dialog to close.
            path: The new path to switch to.
            previous_path: The previous path (for revert on cancel).
            depth: The depth to use (already calculated, passed from dialog).
        """
        dialog.close()

        # Thread runner check
        if not self._check_thread_runner_available(previous_path):
            return
        
        # Check if CSV
        is_csv = path.is_file() and path.suffix.lower() == '.csv'
        
        if is_csv:
            self._start_threaded_load(
                path,
                depth=0,
                is_file=True,
                is_csv=True,
                previous_path=previous_path,
            )
            return
        
        is_file = path.is_file()
        
        # Update folder_depth if this is a folder (depth was calculated from event)
        if not is_file and depth != self._app_state.folder_depth:
            self._app_state.folder_depth = depth
        
        if is_file:
            # Use the shared finalization logic
            self._finally_set_path(path, depth, is_file)
        else:
            self._start_threaded_load(
                path,
                depth=depth,
                is_file=False,
                is_csv=False,
                previous_path=previous_path,
            )
