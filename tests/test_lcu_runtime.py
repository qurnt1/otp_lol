import asyncio
import io
import logging
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src.config import EP_GAMEFLOW
from src.core.datadragon import DataDragon
from src.core.websocket import WebSocketManager, _LcuDriverMalformedJsonFilter
from src.domain.events import EventBroker
from src.lcu.runtime import LcuRuntime


class LcuDriverMalformedJsonFilterTests(unittest.TestCase):
    def test_empty_frames_are_ignored_and_invalid_payloads_are_safely_logged(self):
        log_filter = _LcuDriverMalformedJsonFilter()
        empty_frame = logging.LogRecord(
            "lcu_driver.connection",
            logging.WARNING,
            "connection.py",
            190,
            log_filter._MESSAGE,
            ("",),
            None,
        )
        invalid_frame = logging.LogRecord(
            "lcu_driver.connection",
            logging.WARNING,
            "connection.py",
            190,
            log_filter._MESSAGE,
            ("not-json-payload",),
            None,
        )

        self.assertFalse(log_filter.filter(empty_frame))
        self.assertTrue(log_filter.filter(invalid_frame))
        self.assertEqual(invalid_frame.getMessage(), log_filter._SAFE_MESSAGE)
        self.assertNotIn("not-json-payload", invalid_frame.getMessage())

    def test_empty_frame_does_not_trigger_the_drivers_logging_format_error(self):
        driver_logger = logging.getLogger("lcu_driver.connection")
        output = io.StringIO()
        handler = logging.StreamHandler(output)
        handler.setFormatter(logging.Formatter("%(message)s"))
        log_filter = _LcuDriverMalformedJsonFilter()
        previous_level = driver_logger.level
        previous_propagate = driver_logger.propagate
        driver_logger.addFilter(log_filter)
        driver_logger.addHandler(handler)
        driver_logger.setLevel(logging.WARNING)
        driver_logger.propagate = False
        try:
            driver_logger.warning(log_filter._MESSAGE, "")
            driver_logger.warning(log_filter._MESSAGE, "malformed-payload")
        finally:
            driver_logger.removeFilter(log_filter)
            driver_logger.removeHandler(handler)
            driver_logger.setLevel(previous_level)
            driver_logger.propagate = previous_propagate

        self.assertEqual(output.getvalue().splitlines(), [log_filter._SAFE_MESSAGE])

    def test_filter_is_installed_before_the_lcu_worker_starts(self):
        manager = WebSocketManager(lambda *_: None, None, lambda: {})
        driver_logger = logging.getLogger("lcu_driver.connection")

        def create_thread(*args, **kwargs):
            self.assertEqual(
                sum(isinstance(existing, _LcuDriverMalformedJsonFilter) for existing in driver_logger.filters),
                1,
            )
            return SimpleNamespace(start=lambda: None)

        with (
            patch("src.core.websocket.Connector", object()),
            patch("src.core.websocket.Thread", side_effect=create_thread) as thread_factory,
            patch.object(driver_logger, "filters", []),
        ):
            manager.start()

        thread_factory.assert_called_once()


class FakeManager:
    def __init__(self, event_callback, dd, get_params, update_param, persist_detected_account=None):
        self.event_callback = event_callback
        self.get_params = get_params
        self.persist_detected_account = persist_detected_account
        self.loop = None
        self.connection = None
        self.state = SimpleNamespace(current_queue_id=0, current_phase="None", assigned_position="")
        self.is_active = False

    def get_riot_id(self):
        return None

    def get_platform_for_websites(self):
        return ""

    async def _fetch_current_rune_page_async(self):
        return {"id": 42}

    async def _set_rune_page_via_perks_async(self, page_data):
        return page_data["id"] == 42

    async def _create_rune_page_async(self, page_data):
        return 43

    async def _delete_rune_page_async(self, page_id):
        return page_id == 43

    async def _set_spells(self, params, slot_key=None):
        return None

    async def _set_skin(self, params, slot_key=None):
        return None

    async def _set_rune_page(self, params, slot_key=None):
        return None

    async def _lock_in_champion(self, action_id, champion_id, action_type="pick"):
        return action_id == 7 and champion_id == 86 and action_type == "pick"


class LcuRuntimeAsyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_existing_websocket_subscriptions_forward_diagnostic_event_metadata(self):
        observed = []
        manager = object.__new__(WebSocketManager)
        manager.diagnostic_event_callback = lambda *event: observed.append(event)

        manager._observe_lcu_event(
            SimpleNamespace(
                uri="/lol-gameflow/v1/gameflow-phase",
                type="Update",
                data={"phase": "InProgress"},
            )
        )

        self.assertEqual(
            observed,
            [("/lol-gameflow/v1/gameflow-phase", "Update", {"phase": "InProgress"})],
        )

    async def test_structural_events_are_followed_by_a_runtime_snapshot(self):
        broker = EventBroker()
        subscription = broker.subscribe()
        runtime = LcuRuntime(
            data_dragon=DataDragon(),
            get_params=lambda: {"presets_enabled": False},
            update_param=None,
            broker=broker,
            manager_type=FakeManager,
        )

        runtime._publish_event("phase_change", "ChampSelect")

        event = await subscription.next_event()
        snapshot = await subscription.next_event()
        subscription.close()
        self.assertEqual(event.type, "phase_change")
        self.assertEqual(snapshot.type, "runtime_snapshot")
        self.assertFalse(snapshot.data["connected"])

    async def test_submit_does_not_block_fastapi_loop_while_lcu_runs(self):
        runtime = LcuRuntime(
            data_dragon=DataDragon(),
            get_params=lambda: {},
            update_param=None,
            broker=EventBroker(),
            manager_type=FakeManager,
        )
        worker_loop = asyncio.new_event_loop()
        worker_thread = threading.Thread(target=worker_loop.run_forever)
        worker_thread.start()
        runtime.manager.loop = worker_loop
        ticked = asyncio.Event()

        async def worker_operation():
            await asyncio.sleep(0.05)
            return "completed"

        async def api_tick():
            await asyncio.sleep(0.01)
            ticked.set()

        tick_task = asyncio.create_task(api_tick())
        try:
            result = await runtime._submit(worker_operation)
            self.assertEqual(result, "completed")
            self.assertTrue(ticked.is_set())
        finally:
            await tick_task
            worker_loop.call_soon_threadsafe(worker_loop.stop)
            worker_thread.join(timeout=1)
            worker_loop.close()

    async def test_async_runtime_facade_exposes_lcu_operations(self):
        runtime = LcuRuntime(
            data_dragon=DataDragon(),
            get_params=lambda: {},
            update_param=None,
            broker=EventBroker(),
            manager_type=FakeManager,
        )
        worker_loop = asyncio.new_event_loop()
        worker_thread = threading.Thread(target=worker_loop.run_forever)
        worker_thread.start()
        runtime.manager.loop = worker_loop
        try:
            self.assertEqual(await runtime.fetch_current_rune_page(), {"id": 42})
            self.assertTrue(await runtime.set_rune_page({"id": 42}))
            self.assertEqual(await runtime.create_rune_page({"name": "Test"}), 43)
            self.assertTrue(await runtime.delete_rune_page(43))
            self.assertTrue(await runtime.lock_in_champion(7, 86))
            with self.assertRaises(ValueError):
                await runtime.lock_in_champion(7, 86, action_type="invalid")
        finally:
            worker_loop.call_soon_threadsafe(worker_loop.stop)
            worker_thread.join(timeout=1)
            worker_loop.close()

    async def test_requests_use_the_existing_manager_connection_loop(self):
        class FakeResponse:
            status = 200
            headers = {"Content-Type": "application/json"}

            async def read(self):
                return b'{"phase":"InProgress"}'

        class FakeConnection:
            def __init__(self):
                self.calls = []

            async def request(self, method, path):
                self.calls.append((method, path))
                return FakeResponse()

        runtime = LcuRuntime(
            data_dragon=DataDragon(),
            get_params=lambda: {},
            update_param=None,
            broker=EventBroker(),
            manager_type=FakeManager,
        )
        connection = FakeConnection()
        runtime.manager.connection = connection
        worker_loop = asyncio.new_event_loop()
        worker_thread = threading.Thread(target=worker_loop.run_forever)
        worker_thread.start()
        runtime.manager.loop = worker_loop
        try:
            response = await runtime.request_json("/lol-gameflow/v1/gameflow-phase")
            self.assertTrue(response.ok)
            self.assertEqual(response.payload, {"phase": "InProgress"})
            self.assertEqual(connection.calls, [("get", "/lol-gameflow/v1/gameflow-phase")])
        finally:
            worker_loop.call_soon_threadsafe(worker_loop.stop)
            worker_thread.join(timeout=1)
            worker_loop.close()


class LcuDiagnosticObserverIsolationTests(unittest.TestCase):
    def test_observer_failure_does_not_interrupt_registered_gameflow_handler(self):
        published = []
        handlers = {}
        manager = WebSocketManager(
            event_callback=lambda event_type, data: published.append((event_type, data)),
            dd=DataDragon(),
            get_params=dict,
        )

        def failing_observer(*_event):
            raise RuntimeError("diagnostics unavailable")

        manager.diagnostic_event_callback = failing_observer

        class FakeWebSocket:
            def register(self, endpoint):
                def capture(handler):
                    handlers[endpoint] = handler
                    return handler

                return capture

        class FakeConnector:
            def __init__(self, *, loop):
                self.ws = FakeWebSocket()

            def ready(self, handler):
                return handler

            def close(self, handler):
                return handler

            def start(self):
                manager._stop_event.set()

        with patch("src.core.websocket.Connector", FakeConnector):
            manager._ws_loop()

        asyncio.run(
            handlers[EP_GAMEFLOW](
                None,
                SimpleNamespace(
                    uri=EP_GAMEFLOW,
                    type="Update",
                    data="ReadyCheck",
                ),
            )
        )

        self.assertEqual(published, [(manager.EVENT_PHASE_CHANGE, "ReadyCheck")])
        self.assertEqual(manager.state.current_phase, "ReadyCheck")


if __name__ == "__main__":
    unittest.main()
