import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Event

from src.application.settings_store import SettingsStore


class SettingsStoreTests(unittest.TestCase):
    def setUp(self):
        self.initial_params = {
            "pick_slots": {"pick_1": {"spell_1": "Flash"}},
            "ignored_update_version": "",
        }

    def create_store(self, *, saver=lambda _params: True):
        return SettingsStore(loader=lambda: self.initial_params, saver=saver)

    def test_snapshot_returns_deep_independent_copy(self):
        store = self.create_store()
        snapshot = store.snapshot()
        snapshot["pick_slots"]["pick_1"]["spell_1"] = "Ignite"
        self.assertEqual(store.snapshot()["pick_slots"]["pick_1"]["spell_1"], "Flash")

    def test_update_copies_mutable_value_before_storing(self):
        store = self.create_store()
        pick_slots = {"pick_1": {"spell_1": "Ghost"}}
        store.update("pick_slots", pick_slots)
        pick_slots["pick_1"]["spell_1"] = "Teleport"
        self.assertEqual(store.snapshot()["pick_slots"]["pick_1"]["spell_1"], "Ghost")

    def test_update_many_replaces_related_values_atomically(self):
        store = self.create_store()
        store.update_many({"presets_enabled": False, "auto_pick_enabled": False})
        snapshot = store.snapshot()
        self.assertFalse(snapshot["presets_enabled"])
        self.assertFalse(snapshot["auto_pick_enabled"])

    def test_replace_swaps_complete_snapshot_without_aliasing(self):
        store = self.create_store()
        imported = {"theme": "flatly", "pick_slots": {"pick_1": {"spell_1": "Ghost"}}}
        store.replace(imported)
        imported["pick_slots"]["pick_1"]["spell_1"] = "Smite"
        self.assertEqual(
            store.snapshot(),
            {"theme": "flatly", "pick_slots": {"pick_1": {"spell_1": "Ghost"}}},
        )

    def test_concurrent_reads_and_writes_keep_state_consistent(self):
        store = self.create_store()

        def worker(index):
            for iteration in range(100):
                store.update("pick_slots", {"pick_1": {"spell_1": f"spell-{index}-{iteration}"}})
                store.snapshot()["pick_slots"]["pick_1"]["spell_1"] = "local-only"

        with ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(worker, range(6)))
        self.assertTrue(store.snapshot()["pick_slots"]["pick_1"]["spell_1"].startswith("spell-"))

    def test_save_does_not_hold_state_lock(self):
        save_started = Event()
        release_save = Event()

        def save(params):
            save_started.set()
            release_save.wait(timeout=2)
            return params["pick_slots"]["pick_1"]["spell_1"] == "Flash"

        store = self.create_store(saver=save)
        saver = threading.Thread(target=store.save)
        saver.start()
        self.assertTrue(save_started.wait(timeout=2))
        store.update("ignored_update_version", "12.0")
        release_save.set()
        saver.join(timeout=2)
        self.assertFalse(saver.is_alive())


if __name__ == "__main__":
    unittest.main()
