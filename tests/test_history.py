import json
import os
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from src.services import history
from src.services.history import MAX_HISTORY_ENTRIES, format_history_entry


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


class HistoryPersistenceTests(unittest.TestCase):
    def test_write_history_keeps_bounded_json_format(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            history_path = os.path.join(temp_dir, "history.json")
            with patch.object(history, "HISTORY_PATH", history_path):
                entries = [{"index": index} for index in range(MAX_HISTORY_ENTRIES + 7)]

                history._write_history(entries)

                with open(history_path, "r", encoding="utf-8") as history_file:
                    persisted = json.load(history_file)

        self.assertIsInstance(persisted, list)
        self.assertEqual(len(persisted), MAX_HISTORY_ENTRIES)
        self.assertEqual(persisted[0], {"index": 7})
        self.assertEqual(persisted[-1], {"index": MAX_HISTORY_ENTRIES + 6})

    def test_write_history_replaces_file_atomically_in_same_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            history_path = os.path.join(temp_dir, "history.json")
            with patch.object(history, "HISTORY_PATH", history_path):
                original_replace = os.replace
                with patch.object(history.os, "replace", wraps=original_replace) as replace_mock:
                    history._write_history([{"message": "persisted"}])

                temporary_path, destination_path = replace_mock.call_args.args
                self.assertEqual(destination_path, history_path)
                self.assertEqual(
                    os.path.normcase(os.path.dirname(temporary_path)),
                    os.path.normcase(temp_dir),
                )
                self.assertFalse(os.path.exists(temporary_path))
                self.assertEqual(history._read_history(), [{"message": "persisted"}])

    def test_atomic_write_failure_keeps_previous_history_and_cleans_temp_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            history_path = os.path.join(temp_dir, "history.json")
            with patch.object(history, "HISTORY_PATH", history_path):
                history._write_history([{"message": "previous"}])

                with patch.object(
                    history.os, "replace", side_effect=OSError("replace failed")
                ), self.assertRaises(OSError):
                    history._write_history([{"message": "new"}])

                self.assertEqual(history._read_history(), [{"message": "previous"}])
                self.assertEqual(
                    [name for name in os.listdir(temp_dir) if name.endswith(".tmp")],
                    [],
                )

    def test_concurrent_logging_preserves_all_events(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            history_path = os.path.join(temp_dir, "history.json")
            with patch.object(history, "HISTORY_PATH", history_path):
                original_write = history._write_history

                def delayed_write(entries):
                    time.sleep(0.005)
                    original_write(entries)

                messages = [f"event-{index}" for index in range(48)]
                with patch.object(
                    history, "_write_history", side_effect=delayed_write
                ), ThreadPoolExecutor(max_workers=8) as executor:
                    futures = [
                        executor.submit(history.log_history_event, "pick", message)
                        for message in messages
                    ]
                    for future in futures:
                        future.result()

                persisted = history._read_history()

        self.assertEqual(len(persisted), len(messages))
        self.assertEqual({entry["message"] for entry in persisted}, set(messages))


if __name__ == "__main__":
    unittest.main()
