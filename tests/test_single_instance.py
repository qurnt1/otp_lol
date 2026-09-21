import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.services import single_instance


class SingleInstanceTests(unittest.TestCase):
    def test_first_instance_acquires_the_lock(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            lockfile_path = Path(tmpdir) / "instance.lock"
            with patch.object(single_instance, "LOCKFILE_PATH", str(lockfile_path)), patch.object(
                single_instance, "_lock_fd", None
            ), patch.object(single_instance.os, "open", return_value=41), patch.object(
                single_instance.msvcrt, "locking"
            ), patch.object(single_instance.os, "write"):
                self.assertTrue(single_instance.check_single_instance())

    def test_second_instance_is_rejected_while_owner_lock_is_active(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            lockfile_path = Path(tmpdir) / "instance.lock"
            with patch.object(single_instance, "LOCKFILE_PATH", str(lockfile_path)), patch.object(
                single_instance, "_lock_fd", None
            ), patch.object(single_instance.os, "open", side_effect=OSError("already locked")), patch.object(
                single_instance, "_is_stale_lockfile", return_value=False
            ):
                self.assertFalse(single_instance.check_single_instance())

    def test_non_owner_does_not_remove_existing_lockfile(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            lockfile_path = Path(tmpdir) / "instance.lock"
            lockfile_path.write_text("owner-pid", encoding="ascii")

            with patch.object(single_instance, "LOCKFILE_PATH", str(lockfile_path)), patch.object(
                single_instance, "_lock_fd", None
            ):
                single_instance.remove_lockfile()

            self.assertTrue(lockfile_path.exists())


if __name__ == "__main__":
    unittest.main()
