"""Controller for handling save events from the UI.

This module provides a controller that translates user save intents
(SaveSelected and SaveAll phase="intent") into file save operations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List

import asyncio

from nicegui import ui, run

from kymflow.core.state import TaskState
from kymflow.core.image_loaders.kym_image import KymImage

from kymflow.gui_v2.state import AppState
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.events import SaveAll, SaveSelected, FileChanged, SelectionOrigin
from kymflow.gui_v2.events_state import VelocityEventDbUpdated, FileListChanged, RadonReportUpdated
from kymflow.gui_v2.footer_status import set_footer_status
from kymflow.core.utils.logging import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


class SaveController:
    """Apply save intent events to file save operations.

    This controller handles save intent events from the UI (typically
    from the save buttons) and saves analysis results to files.

    Update Flow:
        1. User clicks "Save Selected" → FolderSelectorView emits SaveSelected(phase="intent")
        2. This controller receives event → checks file has analysis → calls save_analysis()
        3. User clicks "Save All" → FolderSelectorView emits SaveAll(phase="intent")
        4. This controller receives event → iterates files → saves those with analysis

    Attributes:
        _app_state: AppState instance to access files.
        _task_state: TaskState instance (for checking if task is running).
    """

    def __init__(self, app_state: AppState, task_state: TaskState, bus: EventBus) -> None:
        """Initialize save controller.

        Subscribes to SaveSelected and SaveAll (phase="intent") events from the bus.

        Args:
            app_state: AppState instance to access files.
            task_state: TaskState instance (for checking if task is running).
            bus: EventBus instance to subscribe to.
        """
        self._app_state: AppState = app_state
        self._task_state: TaskState = task_state
        self._bus: EventBus = bus
        bus.subscribe_intent(SaveSelected, self._on_save_selected_async)

        # abb 20260314 declan
        # subscribe to SaveAll async
        # bus.subscribe_intent(SaveAll, self._on_save_all)
        # logger.warning('abb 20260314 declan, subscribe to _on_save_all_async')
        bus.subscribe_intent(SaveAll, self._on_save_all_async)

    # def _on_save_selected(self, e: SaveSelected) -> None:
    #     """Handle save selected intent event.

    #     Saves the currently selected file if it has analysis. Shows a notification
    #     if no file is selected or no analysis is found.

    #     Args:
    #         e: SaveSelected event (phase="intent").
    #     """
    #     kf = self._app_state.selected_file
    #     if not kf:
    #         ui.notify("No file selected", color="warning")
    #         return

    #     kym_analysis = kf.get_kym_analysis()
    #     if not kym_analysis.is_dirty:
    #         ui.notify(f"Nothing to save for {kf.path.name}", color="info")
    #         return

    #     try:
    #         success = kym_analysis.save_analysis()
    #         if success:
    #             if hasattr(self._app_state.files, "update_radon_report_for_image"):
    #                 self._app_state.files.update_radon_report_for_image(kf)
    #             if hasattr(self._app_state.files, "update_velocity_event_for_image"):
    #                 self._app_state.files.update_velocity_event_for_image(kf)
    #                 self._bus.emit(VelocityEventDbUpdated())
    #             ui.notify(f"Saved {kf.path.name}", color="positive")
    #             self._app_state.refresh_file_rows()
    #         else:
    #             ui.notify(f"Nothing to save for {kf.path.name}", color="info")
    #     except Exception as exc:
    #         logger.exception(f"Error saving {kf.path.name}")
    #         ui.notify(f"Error saving {kf.path.name}: {str(exc)}", color="negative")

    # def _on_save_all(self, e: SaveAll) -> None:
    #     """Handle save all intent event.

    #     Saves all files that have analysis. Shows notifications for results.

    #     Args:
    #         e: SaveAll event (phase="intent").
    #     """
    #     if not self._app_state.files:
    #         ui.notify("No files loaded", color="warning")
    #         return

    #     saved_count = 0
    #     skipped_count = 0
    #     error_count = 0

    #     for kf in self._app_state.files:
    #         kym_analysis = kf.get_kym_analysis()
    #         if not kym_analysis.is_dirty:
    #             skipped_count += 1
    #             continue

    #         try:
    #             success = kym_analysis.save_analysis()
    #             if success:
    #                 if hasattr(self._app_state.files, "update_radon_report_for_image"):
    #                     self._app_state.files.update_radon_report_for_image(kf)
    #                 if hasattr(self._app_state.files, "update_velocity_event_for_image"):
    #                     self._app_state.files.update_velocity_event_for_image(kf)
    #                     self._bus.emit(VelocityEventDbUpdated())
    #                 saved_count += 1
    #             else:
    #                 skipped_count += 1
    #         except Exception as e:
    #             logger.exception(f"Error saving {kf.path.name}")
    #             logger.error(f'  exception is: {e}')
    #             error_count += 1
    #             # abb 20260314 declan
    #             # ui.notify(f"Error saving {kf.path.name}: {str(exc)}", color="negative")

    #     if saved_count > 0:
    #         ui.notify(f"Saved {saved_count} file(s)", color="positive")
    #         self._app_state.refresh_file_rows()
    #     if skipped_count > 0 and saved_count == 0:
    #         ui.notify(
    #             f"Skipped {skipped_count} file(s) (no changes or no analysis)",
    #             color="info",
    #         )
    #     if error_count > 0:
    #         ui.notify(f"Errors saving {error_count} file(s)", color="negative")

    # abb 20260314 declan
    async def _on_save_selected_async(self, e: SaveSelected) -> None:
        """Handle save selected intent event.

        Saves the currently selected file if it has analysis. Shows a notification
        if no file is selected or no analysis is found.

        Args:
            e: SaveSelected event (phase="intent").
        """
        kym_file = self._app_state.selected_file
        if not kym_file:
            ui.notify("No file selected", color="warning")
            return

        kym_analysis = kym_file.get_kym_analysis()
        if not kym_analysis.is_dirty:
            set_footer_status(self._bus, "Nothing to save", level="info")
            return

        try:
            self._task_state.set_running(True)  # turn off gui

            success = await run.io_bound(kym_analysis.save_analysis)

            if success:
                self._app_state.files.update_radon_report_for_image(kym_file)
                self._app_state.files.update_velocity_event_for_image(kym_file)
                self._bus.emit(RadonReportUpdated())
                self._bus.emit(VelocityEventDbUpdated())
                self._bus.emit(
                    FileChanged(
                        file=kym_file,
                        change_type="analysis",
                        origin=SelectionOrigin.EXTERNAL,
                    )
                )
                self._task_state.message = f"Saved {kym_file.path.name}"
            else:
                self._task_state.message = "Nothing to save"

        except Exception:
            logger.exception(f"Error saving {kym_file.path.name}")
            self._task_state.message = f"Error saving {kym_file.path.name}"
        finally:
            self._task_state.mark_finished()  # re-enable gui

    # abb 20260314 declan
    async def _on_save_all_async(self, e: SaveAll) -> None:
        """Handle save all intent event.

        Saves all files that have analysis. Shows notifications for results.

        Args:
            e: SaveAll event (phase="intent").
        """

        if not self._app_state.files:
            ui.notify("No files loaded", color="warning")
            return

        saved_count = 0
        skipped_count = 0
        error_count = 0
        total_files = len(self._app_state.files)

        # abb to defer radon and velocity event cache updates
        defer_cache_updates:List[KymImage] = []

        self._task_state.cancellable = False
        self._task_state.set_running(True)
        self._task_state.set_progress(0.0, f"Saving 0/{total_files} files")

        try:
            for kf in self._app_state.files:
                kym_analysis = kf.get_kym_analysis()
                if not kym_analysis.is_dirty:
                    skipped_count += 1
                else:
                    try:
                        success = await run.io_bound(kym_analysis.save_analysis)
                        if success:
                            defer_cache_updates.append(kf)
                            saved_count += 1
                        else:
                            skipped_count += 1
                    except Exception as e:
                        logger.exception(f"Error saving {kf.path.name}")
                        logger.error(f"  exception is: {e}")
                        error_count += 1

                # Update footer progress after every file (including skipped)
                processed = saved_count + skipped_count + error_count
                fraction = processed / total_files if total_files else 0.0
                self._task_state.set_progress(
                    min(1.0, fraction),
                    f"Saving {processed}/{total_files} files",
                )
                await asyncio.sleep(0)

            # abb to update radon and velocity event cache
            # logger.warning(f'---> abb calling cache update for radon and velocity event defer_cache_updates n:{len(defer_cache_updates)}')

            for kf in defer_cache_updates:
                # self._app_state.files.update_radon_report_for_image(kf)  # this saves csv
                self._app_state.files.update_radon_report_cache_only(kf)
                # self._app_state.files.update_velocity_event_for_image(kf)  # this saves csv
                self._app_state.files.update_velocity_event_cache_only(kf)
            
            # save the radon and velocity cache to csv (2 files)
            # logger.warning('saving radon and velocity csv files')
            self._app_state.files.save_radon_report_db()
            self._app_state.files.rebuild_velocity_event_db_and_save()

            # afaik, this updates our nicewidgets plotpoolplot gui?
            # self._bus.emit(RadonReportUpdated())
            self._bus.emit(VelocityEventDbUpdated())
            
            # logger.warning('---> abb DONE calling cache update for radon and velocity event')

            # Build final footer message: saved always; skipped/errors if non-zero
            parts = [f"Saved {saved_count} file(s)"]
            if skipped_count > 0:
                parts.append(f"Skipped {skipped_count}")
            if error_count > 0:
                parts.append(f"Errors {error_count}")
            final_message = " · ".join(parts)
            self._task_state.message = final_message

            logger.info(f"  {final_message}")
            if saved_count > 0:
                self._bus.emit(FileListChanged(files=list(self._app_state.files)))
        finally:
            self._task_state.mark_finished()