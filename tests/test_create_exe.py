import os
import unittest
from pathlib import Path
from unittest.mock import patch

from create_exe import _run_pyinstaller


class PyInstallerEnvironmentTests(unittest.TestCase):
    def test_build_uses_and_removes_temporary_appdata(self):
        appdata_during_build = None
        original_appdata = os.environ.get("APPDATA")

        def record_environment(command, **kwargs):
            nonlocal appdata_during_build
            appdata_during_build = kwargs["env"]["APPDATA"]
            self.assertTrue(Path(appdata_during_build).is_dir())
            self.assertNotEqual(appdata_during_build, original_appdata)

        with patch("create_exe.subprocess.run", side_effect=record_environment):
            _run_pyinstaller(["pyinstaller", "launcher_web.py"])

        self.assertIsNotNone(appdata_during_build)
        self.assertFalse(Path(appdata_during_build).exists())


if __name__ == "__main__":
    unittest.main()
