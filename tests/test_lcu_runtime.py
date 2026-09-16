import asyncio
import threading
import unittest
from types import SimpleNamespace

from src.core.datadragon import DataDragon
from src.domain.events import EventBroker
from src.lcu.runtime import LcuRuntime


class FakeManager:
    def __init__(self, event_callback, dd, get_params, update_param):
        self.event_callback = event_callback
        self.get_params = get_params
        self.loop = None
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


if __name__ == "__main__":
    unittest.main()
