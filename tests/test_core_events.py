import unittest
from dataclasses import FrozenInstanceError

from src.core.events import ChampionPicked, Connected, CoreEvent, Disconnected, RuntimeEvent, SpellsApplied


class CoreEventTests(unittest.TestCase):
    def test_connected_is_a_core_runtime_event(self):
        event = Connected()
        self.assertIsInstance(event, CoreEvent)
        self.assertIsInstance(event, RuntimeEvent)

    def test_disconnect_event_preserves_fields(self):
        event = Disconnected(transient=True, reason="scan_failed")
        self.assertTrue(event.transient)
        self.assertEqual(event.reason, "scan_failed")

    def test_spells_event_has_named_fields(self):
        event = SpellsApplied("Flash", "Teleport")
        self.assertEqual((event.first, event.second), ("Flash", "Teleport"))

    def test_events_are_immutable(self):
        event = ChampionPicked("Lux")
        with self.assertRaises(FrozenInstanceError):
            event.champion = "Garen"


if __name__ == "__main__":
    unittest.main()
