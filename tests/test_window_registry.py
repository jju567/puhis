from pathlib import Path
import tempfile
import unittest

from puhis.core.actions import WindowInfo
from puhis.core.window_registry import WindowRegistry, is_default_window_slot


class WindowRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = WindowRegistry()

    def test_save_and_get_window_normalizes_alias(self) -> None:
        info = WindowInfo(hwnd=1001, title="Nimetön – Muistio", process_name="notepad.exe")

        entry = self.registry.save("  T1. ", info)
        loaded = self.registry.get("t1")

        self.assertEqual(entry.alias, "t1")
        self.assertEqual(loaded, entry)
        self.assertTrue(self.registry.has_alias("T1"))

    def test_save_overwrites_existing_alias(self) -> None:
        first = WindowInfo(hwnd=100, title="Muistio", process_name="notepad.exe")
        second = WindowInfo(hwnd=200, title="Laskin", process_name="calc.exe")

        self.registry.save("t1", first)
        self.registry.save("t1", second)

        entry = self.registry.get("t1")
        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertEqual(entry.window, second)
        self.assertEqual(len(self.registry.list_entries()), 1)

    def test_get_and_remove_unknown_alias_return_none_and_false(self) -> None:
        self.assertIsNone(self.registry.get("t99"))
        self.assertIsNone(self.registry.get("   "))
        self.assertFalse(self.registry.remove("t99"))

    def test_remove_and_clear_entries(self) -> None:
        self.registry.save("t2", WindowInfo(hwnd=20, title="B"))
        self.registry.save("t1", WindowInfo(hwnd=10, title="A"))

        self.assertEqual([e.alias for e in self.registry.list_entries()], ["t1", "t2"])
        self.assertTrue(self.registry.remove("T1"))
        self.assertIsNone(self.registry.get("t1"))

        self.registry.clear()
        self.assertEqual(self.registry.list_entries(), [])

    def test_save_invalid_alias_or_hwnd_raises_value_error(self) -> None:
        valid_win = WindowInfo(hwnd=123, title="Testi")
        with self.assertRaises(ValueError):
            self.registry.save("   ", valid_win)
        with self.assertRaises(ValueError):
            self.registry.save("väärä alias välilyönnillä", valid_win)
        with self.assertRaises(ValueError):
            self.registry.save("t1", WindowInfo(hwnd=0))

    def test_is_default_window_slot_matches_t1_to_t99(self) -> None:
        self.assertTrue(is_default_window_slot("t1"))
        self.assertTrue(is_default_window_slot("T12."))
        self.assertFalse(is_default_window_slot("t"))
        self.assertFalse(is_default_window_slot("t100"))
        self.assertFalse(is_default_window_slot("laskin"))

    def test_persists_and_reloads_windows_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "windows.json"
            reg1 = WindowRegistry(storage_path=path)
            reg1.save("depo", WindowInfo(hwnd=67390, title="DEPO 3.0", process_name="chrome.exe"))
            reg1.save("t1", WindowInfo(hwnd=1234, title="Muistio", process_name="notepad.exe"))

            reg2 = WindowRegistry(storage_path=path)
            self.assertEqual([e.alias for e in reg2.list_entries()], ["depo", "t1"])
            depo = reg2.get("depo")
            self.assertIsNotNone(depo)
            assert depo is not None
            self.assertEqual(depo.window.hwnd, 67390)
            self.assertEqual(depo.window.process_name, "chrome.exe")

            reg2.remove("t1")
            reg3 = WindowRegistry(storage_path=path)
            self.assertEqual([e.alias for e in reg3.list_entries()], ["depo"])

    def test_corrupt_windows_file_does_not_crash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "windows.json"
            path.write_text("{rikkinäinen json", encoding="utf-8")
            reg = WindowRegistry(storage_path=path)
            self.assertEqual(reg.list_entries(), [])


if __name__ == "__main__":
    unittest.main()
