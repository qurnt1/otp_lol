import unittest
from dataclasses import FrozenInstanceError

from src.core.events import (
    ChampionPicked,
    Connected,
    CoreEvent,
    Disconnected,
    GameLoading,
    GameStarted,
    ProfileUpdated,
    RankedEntry,
    ReturnedToLobby,
    RuntimeEvent,
    SpellsApplied,
)


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

    def test_gameflow_events_are_core_runtime_events(self):
        for event in (GameLoading(), GameStarted(), ReturnedToLobby()):
            self.assertIsInstance(event, CoreEvent)
            self.assertIsInstance(event, RuntimeEvent)

    def test_profile_event_carries_only_typed_lcu_values(self):
        ranked = RankedEntry("RANKED_SOLO_5x5", "GOLD", "II", 75, 20, 15, False)
        event = ProfileUpdated("TestPlayer#EUW", 123, "puuid", 42, 125, (ranked,))

        self.assertIsInstance(event, CoreEvent)
        self.assertEqual(event.profile_icon_id, 42)
        self.assertEqual(event.ranked_entries, (ranked,))

    def test_profile_event_defaults_missing_rank_data_to_empty(self):
        event = ProfileUpdated("TestPlayer#EUW", 123, "puuid", None, None)

        self.assertIsNone(event.profile_icon_id)
        self.assertIsNone(event.summoner_level)
        self.assertEqual(event.ranked_entries, ())

    def test_events_are_immutable(self):
        event = ChampionPicked("Lux")
        with self.assertRaises(FrozenInstanceError):
            event.champion = "Garen"


if __name__ == "__main__":
    unittest.main()
