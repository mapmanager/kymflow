"""Unit tests for batch analysis dialog lifecycle and guards."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from kymflow.core.kym_analysis_batch.types import AnalysisBatchKind, BatchFileOutcome, BatchFileResult
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.dialogs.kym_analysis_batch_dialog import KymAnalysisBatchDialog
from kymflow.gui_v2.pages.home_page import HomePage


def _make_dialog_with_mocks() -> tuple[KymAnalysisBatchDialog, list[bool]]:
    """Build a dialog with MagicMock dependencies and a list to record ``on_disposed``."""
    app_state = MagicMock()
    file_table = MagicMock()
    batch_ctrl = MagicMock()
    context = MagicMock()
    get_bp = MagicMock(return_value=(MagicMock(), None, None))
    disposed: list[bool] = []

    def _on_disposed() -> None:
        disposed.append(True)

    dlg = KymAnalysisBatchDialog(
        app_state,
        file_table,
        batch_ctrl,
        context,
        get_baseline_params=get_bp,
        on_disposed=_on_disposed,
    )
    return dlg, disposed


def test_dispose_cancels_timer_closes_deletes_and_callbacks() -> None:
    """dispose clears active flag, cancels timer, closes/deletes dialog, runs on_disposed."""
    dlg, disposed = _make_dialog_with_mocks()
    dlg._is_active = True
    timer = MagicMock()
    dlg._poll_timer = timer
    dialog_el = MagicMock()
    dlg._dialog = dialog_el
    dlg.dispose()
    assert dlg._is_active is False
    timer.cancel.assert_called_once()
    dialog_el.close.assert_called_once()
    dialog_el.delete.assert_called_once()
    assert disposed == [True]


def test_dispose_idempotent() -> None:
    """Second dispose does not double-invoke on_disposed."""
    dlg, disposed = _make_dialog_with_mocks()
    dlg._is_active = True
    dlg._poll_timer = MagicMock()
    dlg._dialog = MagicMock()
    dlg.dispose()
    dlg.dispose()
    assert len(disposed) == 1


def test_apply_file_result_row_skips_when_inactive() -> None:
    """Per-file row updates no-op after dispose (inactive)."""
    dlg, _ = _make_dialog_with_mocks()
    dlg._is_active = False
    dlg._batch_ui_running = True
    tbl = MagicMock()
    tbl.rows = []
    dlg._report_table = tbl
    r = BatchFileResult(
        kym_image=MagicMock(),
        kind=AnalysisBatchKind.KYM_EVENT,
        outcome=BatchFileOutcome.OK,
        message="ok",
    )
    dlg._apply_file_result_row(r)
    assert tbl.rows == []


def test_poll_batch_progress_skips_when_inactive() -> None:
    """Timer callback does not update progress widgets when inactive."""

    class _ProgressBar:
        def __init__(self) -> None:
            self.value = 0.5

    class _Caption:
        def __init__(self) -> None:
            self.text = "unchanged"

    dlg, _ = _make_dialog_with_mocks()
    dlg._is_active = False
    dlg._batch_ui_running = True
    bar = _ProgressBar()
    cap = _Caption()
    dlg._progress_bar = bar
    dlg._progress_caption = cap
    dlg._poll_batch_progress()
    assert bar.value == 0.5
    assert cap.text == "unchanged"


def test_set_done_chrome_skips_when_inactive() -> None:
    """Completion chrome is not applied after dispose."""

    class _Done:
        def __init__(self) -> None:
            self.visible = False
            self.text = ""

    dlg, _ = _make_dialog_with_mocks()
    dlg._is_active = False
    done = _Done()
    dlg._done_label = done
    dlg._set_done_chrome(True, [])
    assert done.visible is False
    assert done.text == ""


def test_open_batch_analysis_dialog_sets_guard_and_on_disposed_clears(bus: EventBus) -> None:
    """HomePage opens one dialog at a time; on_disposed clears re-entrancy flag."""
    from kymflow.gui_v2.app_context import AppContext

    context = AppContext()
    page = HomePage(context, bus)
    page._setup_complete = True
    page._batch_analysis_controller = MagicMock()
    dlg_instance = MagicMock()
    captured: dict = {}

    def _fake_ctor(*_a: object, **kwargs: object) -> MagicMock:
        captured.update(kwargs)
        return dlg_instance

    with patch("kymflow.gui_v2.pages.home_page.KymAnalysisBatchDialog", side_effect=_fake_ctor):
        page._open_batch_analysis_dialog(AnalysisBatchKind.KYM_EVENT)
    dlg_instance.schedule_open.assert_called_once_with(AnalysisBatchKind.KYM_EVENT)
    assert page._batch_dialog_open is True
    assert "on_disposed" in captured
    captured["on_disposed"]()
    assert page._batch_dialog_open is False


def test_open_batch_analysis_dialog_skips_when_already_open(bus: EventBus) -> None:
    """Second open while guard is set does not construct another dialog."""
    from kymflow.gui_v2.app_context import AppContext

    context = AppContext()
    page = HomePage(context, bus)
    page._setup_complete = True
    page._batch_analysis_controller = MagicMock()
    page._batch_dialog_open = True
    with patch("kymflow.gui_v2.pages.home_page.KymAnalysisBatchDialog") as mock_cls:
        page._open_batch_analysis_dialog(AnalysisBatchKind.RADON)
    mock_cls.assert_not_called()


def test_open_batch_analysis_dialog_skips_before_setup(bus: EventBus) -> None:
    """Toolbar path before _ensure_setup does nothing."""
    from kymflow.gui_v2.app_context import AppContext

    context = AppContext()
    page = HomePage(context, bus)
    page._setup_complete = False
    with patch("kymflow.gui_v2.pages.home_page.KymAnalysisBatchDialog") as mock_cls:
        page._open_batch_analysis_dialog(AnalysisBatchKind.KYM_EVENT)
    mock_cls.assert_not_called()
