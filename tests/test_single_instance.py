import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from src.services import single_instance


class SingleInstanceTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == "win32", "The production lock uses Windows msvcrt semantics")
    def test_real_processes_enforce_single_instance_and_reacquire_after_exit(self):
        owner_code = """
import sys
from pathlib import Path

from src.services import single_instance

single_instance.LOCKFILE_PATH = sys.argv[1]
if not single_instance.check_single_instance():
    raise SystemExit(2)
Path(sys.argv[2]).write_text("ready", encoding="ascii")
try:
    sys.stdin.read(1)
finally:
    single_instance.remove_lockfile()
"""
        contender_code = """
import sys

from src.services import single_instance

single_instance.LOCKFILE_PATH = sys.argv[1]
acquired = single_instance.check_single_instance()
print("acquired" if acquired else "rejected", flush=True)
if acquired:
    single_instance.remove_lockfile()
"""

        root_dir = Path(__file__).resolve().parent.parent
        with tempfile.TemporaryDirectory() as tmpdir:
            lockfile_path = Path(tmpdir) / "instance.lock"
            ready_path = Path(tmpdir) / "owner.ready"
            owner = subprocess.Popen(
                [sys.executable, "-c", owner_code, str(lockfile_path), str(ready_path)],
                cwd=root_dir,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                deadline = time.monotonic() + 10
                while not ready_path.exists():
                    if owner.poll() is not None:
                        stderr = owner.stderr.read() if owner.stderr else ""
                        self.fail(f"The owner process exited before locking: {stderr}")
                    if time.monotonic() >= deadline:
                        self.fail("The owner process did not acquire the lock in time")
                    time.sleep(0.05)

                contender = subprocess.run(
                    [sys.executable, "-c", contender_code, str(lockfile_path)],
                    cwd=root_dir,
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )
                self.assertEqual(contender.returncode, 0, contender.stderr)
                self.assertEqual(contender.stdout.strip().splitlines()[-1], "rejected")

                self.assertIsNotNone(owner.stdin)
                owner.stdin.write("x")
                owner.stdin.flush()
                owner.wait(timeout=10)
                self.assertEqual(owner.returncode, 0)

                reacquired = subprocess.run(
                    [sys.executable, "-c", contender_code, str(lockfile_path)],
                    cwd=root_dir,
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )
                self.assertEqual(reacquired.returncode, 0, reacquired.stderr)
                self.assertEqual(reacquired.stdout.strip().splitlines()[-1], "acquired")
            finally:
                if owner.poll() is None:
                    owner.kill()
                    owner.wait(timeout=10)
                for stream in (owner.stdin, owner.stdout, owner.stderr):
                    if stream is not None:
                        stream.close()

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
