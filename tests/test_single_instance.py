import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.services import single_instance


class SingleInstanceTests(unittest.TestCase):
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
