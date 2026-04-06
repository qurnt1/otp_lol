import unittest

from src.services.history import format_history_entry


class HistoryFormattingTests(unittest.TestCase):
    def test_format_history_entry_handles_legacy_payload(self):
        entry = {
            "timestamp": "2026-04-05T21:34:08+02:00",
            "type": "pick",
            "message": "Pick automatique sur Garen.",
            "details": {"champion_id": 86},
        }

        formatted = format_history_entry(entry)

        self.assertEqual(formatted["time"], "21:34:08")
        self.assertEqual(formatted["level"], "success")
        self.assertEqual(formatted["level_label"], "Success")
        self.assertEqual(formatted["message"], "Pick automatique sur Garen.")
        self.assertEqual(formatted["detail_lines"], [])

    def test_format_history_entry_builds_human_readable_details(self):
        entry = {
            "timestamp": "2026-04-05T21:34:08+02:00",
            "type": "spells",
            "level": "success",
            "message": "Automatic spells applied: Flash + Ignite.",
            "details": {"spell_1": "Flash", "spell_2": "Ignite", "role": "MIDDLE"},
        }

        formatted = format_history_entry(entry)

        self.assertEqual(
            formatted["detail_lines"],
            ["Spells: Flash + Ignite", "Profile: MIDDLE"],
        )


if __name__ == "__main__":
    unittest.main()
