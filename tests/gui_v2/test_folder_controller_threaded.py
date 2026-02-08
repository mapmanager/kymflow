from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
import threading
from unittest.mock import MagicMock, patch

from kymflow.core.image_loaders.acq_image_list import AcqImageList
from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.gui_v2.bus import BusConfig, EventBus
from kymflow.gui_v2.controllers.folder_controller import FolderController
from kymflow.gui_v2.events_folder import CancelSelectPathEvent, SelectPathEvent
from kymflow.gui_v2.state import AppState


class _Ctx:
    def __init__(self, obj) -> None:
        self._obj = obj

    def __enter__(self):
        return self._obj

    def __exit__(self, exc_type, exc, tb):
        return False


@dataclass
class _DummyDialog:
    opened: bool = False

    def open(self) -> None:
        self.opened = True

    def close(self) -> None:
        self.opened = False


def _mock_ui(monkeypatch) -> None:
    dialog_obj = _DummyDialog()

    def _dialog():
        return _Ctx(dialog_obj)

    def _card():
        return _Ctx(MagicMock())

    def _row():
        return _Ctx(MagicMock())

    def _label(*args, **kwargs):
        obj = MagicMock()
        obj.text = args[0] if args else ""
        obj.classes.return_value = obj
        return obj

    def _linear_progress(*args, **kwargs):
        obj = MagicMock()
        obj.value = kwargs.get("value", 0.0)
        obj.visible = True
        obj.classes.return_value = obj
        return obj

    def _button(*args, **kwargs):
        obj = MagicMock()
        obj.props.return_value = obj
        return obj

    def _timer(*args, **kwargs):
        return MagicMock()

    ui_mock = SimpleNamespace(
        dialog=_dialog,
        card=_card,
        row=_row,
        label=_label,
        linear_progress=_linear_progress,
        button=_button,
        timer=_timer,
        notify=MagicMock(),
    )

    monkeypatch.setattr("kymflow.gui_v2.controllers.folder_controller.ui", ui_mock)


def test_start_threaded_load_done_applies_state_and_emits(monkeypatch) -> None:
    _mock_ui(monkeypatch)

    app_state = AppState()
    bus = EventBus(client_id="test-client", config=BusConfig(trace=False))
    user_config = MagicMock()
    controller = FolderController(app_state, bus, user_config=user_config)

    path = Path("/fake/folder")
    files = AcqImageList(path=None, image_cls=KymImage, file_extension=".tif", depth=1)

    with patch.object(app_state, "_build_files_for_path", return_value=(files, path)) as mock_build:
        with patch.object(app_state, "_apply_loaded_files") as mock_apply:
            with patch("kymflow.gui_v2.controllers.folder_controller.set_window_title_for_path") as mock_title:
                def start_stub(**kwargs):
                    cancel_event = threading.Event()
                    result = kwargs["worker_fn"](cancel_event, lambda _msg: None)
                    kwargs["on_done"](result)
                    return 1

                controller._thread_runner.start = start_stub  # type: ignore[assignment]

                emitted = []
                bus.subscribe(SelectPathEvent, lambda e: emitted.append(e))

                controller._start_threaded_load(
                    path,
                    depth=2,
                    is_file=False,
                    is_csv=False,
                    previous_path=None,
                )

                mock_build.assert_called_once()
                mock_apply.assert_called_once_with(files, path)
                mock_title.assert_called_once()
                user_config.push_recent_path.assert_called_once_with(str(path), depth=2)

                assert len(emitted) == 1
                assert emitted[0].phase == "state"


def test_start_threaded_load_csv_persists_recent_csv(monkeypatch) -> None:
    _mock_ui(monkeypatch)

    app_state = AppState()
    bus = EventBus(client_id="test-client", config=BusConfig(trace=False))
    user_config = MagicMock()
    controller = FolderController(app_state, bus, user_config=user_config)

    path = Path("/fake/files.csv")
    files = AcqImageList(path=None, image_cls=KymImage, file_extension=".tif", depth=1)

    with patch.object(app_state, "_build_files_for_path", return_value=(files, path)):
        with patch.object(app_state, "_apply_loaded_files"):
            with patch("kymflow.gui_v2.controllers.folder_controller.set_window_title_for_path"):
                def start_stub(**kwargs):
                    cancel_event = threading.Event()
                    result = kwargs["worker_fn"](cancel_event, lambda _msg: None)
                    kwargs["on_done"](result)
                    return 1

                controller._thread_runner.start = start_stub  # type: ignore[assignment]

                emitted = []
                bus.subscribe(SelectPathEvent, lambda e: emitted.append(e))

                controller._start_threaded_load(
                    path,
                    depth=0,
                    is_file=True,
                    is_csv=True,
                    previous_path=None,
                )

                user_config.push_recent_csv.assert_called_once_with(str(path))
                assert len(emitted) == 1
                assert emitted[0].depth == 0


def test_start_threaded_load_cancelled_emits_cancel(monkeypatch) -> None:
    _mock_ui(monkeypatch)

    app_state = AppState()
    bus = EventBus(client_id="test-client", config=BusConfig(trace=False))
    controller = FolderController(app_state, bus, user_config=None)

    emitted = []
    bus.subscribe(CancelSelectPathEvent, lambda e: emitted.append(e))

    def start_stub(**kwargs):
        kwargs["on_cancelled"]()
        return 1

    controller._thread_runner.start = start_stub  # type: ignore[assignment]

    controller._start_threaded_load(
        Path("/fake/folder"),
        depth=1,
        is_file=False,
        is_csv=False,
        previous_path="/prev",
    )

    assert len(emitted) == 1
    assert emitted[0].previous_path == "/prev"
