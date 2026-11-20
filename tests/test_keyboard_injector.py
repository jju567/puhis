import ctypes
import unittest

from puhis.core.actions import KeyAction, TextAction, VirtualKey
from puhis.platform.keyboard_injector import (
    INPUT,
    KEYEVENTF_KEYUP,
    KEYEVENTF_UNICODE,
    VK_RETURN,
    VK_TAB,
    KeyboardInjector,
)


class KeyboardInjectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.captured: list[INPUT] = []
        self.force_partial_send = False

        def fake_send_input(count: int, inputs: ctypes.Array[INPUT], item_size: int) -> int:
            self.assertEqual(item_size, ctypes.sizeof(INPUT))
            for idx in range(count):
                self.captured.append(inputs[idx])
            return count - 1 if self.force_partial_send else count

        self.injector = KeyboardInjector(send_input_fn=fake_send_input)

    def test_send_unicode_finnish_characters_creates_down_and_up_pairs(self) -> None:
        ok = self.injector.send_text("äö")

        self.assertTrue(ok)
        self.assertEqual(len(self.captured), 4)
        # 'ä' = U+00E4, 'ö' = U+00F6
        self.assertEqual(self.captured[0].union.ki.wScan, ord("ä"))
        self.assertEqual(self.captured[0].union.ki.dwFlags, KEYEVENTF_UNICODE)
        self.assertEqual(self.captured[1].union.ki.wScan, ord("ä"))
        self.assertEqual(self.captured[1].union.ki.dwFlags, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)
        self.assertEqual(self.captured[2].union.ki.wScan, ord("ö"))
        self.assertEqual(self.captured[3].union.ki.wScan, ord("ö"))

    def test_send_actions_combines_unicode_text_and_virtual_keys(self) -> None:
        ok = self.injector.send_actions([
            TextAction(text="A"),
            KeyAction(key=VirtualKey.TAB),
            KeyAction(key=VirtualKey.ENTER),
        ])

        self.assertTrue(ok)
        self.assertEqual(len(self.captured), 6)
        self.assertEqual(self.captured[0].union.ki.wScan, ord("A"))
        self.assertEqual(self.captured[2].union.ki.wVk, VK_TAB)
        self.assertEqual(self.captured[2].union.ki.dwFlags, 0)
        self.assertEqual(self.captured[3].union.ki.wVk, VK_TAB)
        self.assertEqual(self.captured[3].union.ki.dwFlags, KEYEVENTF_KEYUP)
        self.assertEqual(self.captured[4].union.ki.wVk, VK_RETURN)

    def test_send_actions_returns_false_when_send_input_fails(self) -> None:
        self.force_partial_send = True

        ok = self.injector.send_key(VirtualKey.ENTER)

        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
