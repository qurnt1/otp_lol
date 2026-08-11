import unittest
from threading import Thread

from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QApplication

from src.core.events import ChampionPicked
from src.desktop.event_bridge import CoreEventBridge


class ThreadRecordingReceiver(QObject):
    handled = Signal()

    def __init__(self):
        super().__init__()
        self.execution_thread = None

    @Slot(object)
    def handle(self, _event):
        self.execution_thread = QThread.currentThread()
        self.handled.emit()


class CoreEventBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt_application = QApplication.instance() or QApplication([])

    def test_publish_emits_same_event(self):
        bridge = CoreEventBridge()
        spy = QSignalSpy(bridge.event_received)
        event = ChampionPicked("Lux")
        bridge.publish(event)
        self.assertEqual(spy.count(), 1)
        self.assertIs(spy.at(0)[0], event)

    def test_publish_rejects_untyped_payloads(self):
        bridge = CoreEventBridge()
        with self.assertRaises(TypeError):
            bridge.publish(("connected", None))

    def test_worker_event_is_handled_in_qt_thread(self):
        bridge = CoreEventBridge()
        receiver = ThreadRecordingReceiver()
        bridge.event_received.connect(receiver.handle, Qt.ConnectionType.QueuedConnection)
        handled_spy = QSignalSpy(receiver.handled)
        worker = Thread(target=bridge.publish, args=(ChampionPicked("Lux"),))
        worker.start()
        worker.join(timeout=1)
        self.assertFalse(worker.is_alive())
        self.assertTrue(handled_spy.wait(1000))
        self.assertIs(receiver.execution_thread, self.qt_application.thread())


if __name__ == "__main__":
    unittest.main()
