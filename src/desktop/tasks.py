"""Small Qt worker pool that always delivers callbacks on the GUI thread."""

import logging
import uuid
import weakref
from collections.abc import Callable
from typing import Any

from PyQt6 import sip
from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal, pyqtSlot


def guarded_callback(owner: QObject, method_name: str) -> Callable[[Any], None]:
    """Return a callback that ignores results after its Qt receiver is deleted."""
    owner_ref = weakref.ref(owner)

    def callback(value: Any) -> None:
        target = owner_ref()
        if target is not None and not sip.isdeleted(target):
            getattr(target, method_name)(value)

    return callback


class _WorkerSignals(QObject):
    succeeded = pyqtSignal(str, object)
    failed = pyqtSignal(str, str)
    finished = pyqtSignal(str)


class _Worker(QRunnable):
    def __init__(self, task_id: str, function: Callable[[], Any]) -> None:
        super().__init__()
        self.task_id = task_id
        self.function = function
        self.signals = _WorkerSignals()

    def run(self) -> None:
        try:
            self.signals.succeeded.emit(self.task_id, self.function())
        except Exception as exc:
            logging.exception("Desktop background task failed")
            self.signals.failed.emit(self.task_id, str(exc))
        finally:
            self.signals.finished.emit(self.task_id)


class TaskRunner(QObject):
    """Run blocking adapters without letting them touch widgets off-thread."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._pool = QThreadPool.globalInstance()
        self._callbacks: dict[str, tuple[Callable[[Any], None], Callable[[str], None] | None]] = {}
        self._workers: dict[str, _Worker] = {}

    def submit(
        self,
        function: Callable[[], Any],
        on_success: Callable[[Any], None],
        on_error: Callable[[str], None] | None = None,
    ) -> str:
        task_id = uuid.uuid4().hex
        worker = _Worker(task_id, function)
        worker.signals.succeeded.connect(self._handle_success)
        worker.signals.failed.connect(self._handle_failure)
        worker.signals.finished.connect(self._handle_finished)
        self._callbacks[task_id] = (on_success, on_error)
        self._workers[task_id] = worker
        self._pool.start(worker)
        return task_id

    @pyqtSlot(str, object)
    def _handle_success(self, task_id: str, result: Any) -> None:
        callbacks = self._callbacks.get(task_id)
        if callbacks:
            callbacks[0](result)

    @pyqtSlot(str, str)
    def _handle_failure(self, task_id: str, message: str) -> None:
        callbacks = self._callbacks.get(task_id)
        if callbacks and callbacks[1]:
            callbacks[1](message)

    @pyqtSlot(str)
    def _handle_finished(self, task_id: str) -> None:
        self._callbacks.pop(task_id, None)
        self._workers.pop(task_id, None)

    def shutdown(self) -> None:
        self._callbacks.clear()
