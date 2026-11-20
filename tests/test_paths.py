import os
import unittest
from pathlib import Path
from unittest import mock

from puhis.platform import paths


class PathsTests(unittest.TestCase):
    def test_config_path_uses_appdata(self) -> None:
        with mock.patch.dict(os.environ, {"APPDATA": r"D:\Roaming Data"}):
            self.assertEqual(paths.get_config_path(), Path(r"D:\Roaming Data") / "puhis" / "config.json")

    def test_log_dir_uses_localappdata(self) -> None:
        with mock.patch.dict(os.environ, {"LOCALAPPDATA": r"D:\Local Ääkköset"}):
            self.assertEqual(paths.get_log_dir(), Path(r"D:\Local Ääkköset") / "puhis" / "logs")
            self.assertEqual(paths.get_models_dir(), Path(r"D:\Local Ääkköset") / "puhis" / "models")

    def test_missing_env_falls_back_to_home(self) -> None:
        with mock.patch.dict(os.environ, {"APPDATA": "  "}):
            expected = Path.home() / "AppData" / "Roaming" / "puhis"
            self.assertEqual(paths.get_config_dir(), expected)


if __name__ == "__main__":
    unittest.main()
