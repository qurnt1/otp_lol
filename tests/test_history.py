import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from src.services import history
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
            "message": "Automatic summs applied: Flash + Ignite.",
            "details": {"spell_1": "Flash", "spell_2": "Ignite", "role": "MIDDLE"},
        }

        formatted = format_history_entry(entry)

        self.assertEqual(
            formatted["detail_lines"],
            ["Summs: Flash + Ignite", "Profile: MIDDLE"],
        )

    def test_gameflow_events_have_stable_display_defaults(self):
        for event_type, action in (
            ("game_loading", "game_loading"),
            ("game_started", "game_started"),
            ("lobby_returned", "lobby_returned"),
        ):
            formatted = format_history_entry({"type": event_type, "message": "event"})
            self.assertEqual(formatted["type"], event_type)
            self.assertEqual(formatted["action"], action)
            self.assertEqual(formatted["category"], "Game")

    def test_history_serialization_failure_keeps_previous_file_and_cleans_temp(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            history_path = Path(tmpdir) / "history.json"
            history_path.write_text('[{"message": "previous"}]', encoding="utf-8")

            with patch.object(history, "HISTORY_PATH", str(history_path)), patch.object(
                history.json, "dump", side_effect=ValueError("serialization failed")
            ):
                with self.assertRaises(ValueError):
                    history._write_history([{"message": "new"}])

            self.assertEqual(history_path.read_text(encoding="utf-8"), '[{"message": "previous"}]')
            self.assertEqual(list(Path(tmpdir).glob(".*.tmp")), [])

    def test_history_replace_failure_keeps_previous_file_and_cleans_temp(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            history_path = Path(tmpdir) / "history.json"
            history_path.write_text('[{"message": "previous"}]', encoding="utf-8")

            with patch.object(history, "HISTORY_PATH", str(history_path)), patch(
                "src.atomic_io.os.replace", side_effect=OSError("replace failed")
            ):
                with self.assertRaises(OSError):
                    history._write_history([{"message": "new"}])

            self.assertEqual(history_path.read_text(encoding="utf-8"), '[{"message": "previous"}]')
            self.assertEqual(list(Path(tmpdir).glob(".*.tmp")), [])

    def test_corrupt_history_is_backed_up_before_new_event_is_written(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            history_path = Path(tmpdir) / "history.json"
            history_path.write_text("{ invalid json", encoding="utf-8")

            with patch.object(history, "HISTORY_PATH", str(history_path)):
                self.assertEqual(history._read_history(), [])
                history.log_history_event("pick", "new event")

            self.assertEqual(Path(f"{history_path}.bak").read_text(encoding="utf-8"), "{ invalid json")
            payload = json.loads(history_path.read_text(encoding="utf-8"))
            self.assertEqual(payload[-1]["message"], "new event")

    def test_concurrent_history_writes_do_not_lose_events(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            history_path = Path(tmpdir) / "history.json"
            with patch.object(history, "HISTORY_PATH", str(history_path)):
                with ThreadPoolExecutor(max_workers=8) as pool:
                    list(pool.map(lambda index: history.log_history_event("pick", f"event-{index}"), range(50)))

            payload = json.loads(history_path.read_text(encoding="utf-8"))
            self.assertEqual(len(payload), 50)
            self.assertEqual({entry["message"] for entry in payload}, {f"event-{index}" for index in range(50)})


if __name__ == "__main__":
    unittest.main()
