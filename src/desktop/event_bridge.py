"""Thread-safe Qt bridge for runtime events."""

from PySide6.QtCore import QObject, Signal, Slot

from ..core.events import RuntimeEvent


class CoreEventBridge(QObject):
    """Forward immutable runtime events to receivers in their Qt thread."""

    event_received = Signal(object)

    @Slot(object)
    def publish(self, event: RuntimeEvent) -> None:
        if not isinstance(event, RuntimeEvent):
            raise TypeError("CoreEventBridge only accepts RuntimeEvent instances")
        self.event_received.emit(event)
