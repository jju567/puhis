from collections.abc import Sequence
import unittest

from puhis.platform.app_launcher import AppLauncher


class AppLauncherTests(unittest.TestCase):
    def setUp(self) -> None:
        self.spawned: list[list[str]] = []

        def fake_popen(cmd: Sequence[str]) -> object:
            self.spawned.append(list(cmd))
            return object()

        self.launcher = AppLauncher(
            app_aliases={
                "laskin": ["calc.exe"],
                "muistio": ["notepad.exe", "/A"],
            },
            popen_fn=fake_popen,
        )

    def test_launch_known_alias_calls_popen_with_argument_list(self) -> None:
        ok, msg = self.launcher.launch("  Muistio! ")

        self.assertTrue(ok)
        self.assertIn("muistio", msg.lower())
        self.assertEqual(self.spawned, [["notepad.exe", "/A"]])

    def test_launch_unknown_alias_is_rejected_without_calling_popen(self) -> None:
        ok, msg = self.launcher.launch("cmd.exe /c dir")

        self.assertFalse(ok)
        self.assertIn("Tuntematon sovellus", msg)
        self.assertEqual(self.spawned, [])

    def test_launch_handles_file_not_found_gracefully(self) -> None:
        def missing_popen(cmd: Sequence[str]) -> object:
            raise FileNotFoundError(cmd[0])

        launcher = AppLauncher({"laskin": ["puuttuva.exe"]}, popen_fn=missing_popen)
        ok, msg = launcher.launch("laskin")

        self.assertFalse(ok)
        self.assertIn("ei löytynyt", msg)


if __name__ == "__main__":
    unittest.main()
