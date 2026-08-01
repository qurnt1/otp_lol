"""Thread-safe Qt bridge for runtime events."""

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from ..core.events import RuntimeEvent


class CoreEventBridge(QObject):
    """Forward immutable runtime events to receivers in their Qt thread."""

    event_received = pyqtSignal(object)

    @pyqtSlot(object)
    def publish(self, event: RuntimeEvent) -> None:
        if not isinstance(event, RuntimeEvent):
            raise TypeError("CoreEventBridge only accepts RuntimeEvent instances")
        self.event_received.emit(event)
