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
        self.batch_sizes: list[int] = []
        self.force_partial_send = False

        def fake_send_input(count: int, inputs: ctypes.Array[INPUT], item_size: int) -> int:
            self.assertEqual(item_size, ctypes.sizeof(INPUT))
            self.batch_sizes.append(count)
            for idx in range(count):
                self.captured.append(inputs[idx])
            return count - 1 if self.force_partial_send else count

        self.injector = KeyboardInjector(send_input_fn=fake_send_input, inter_key_delay_s=0.0)

    def test_send_unicode_finnish_characters_creates_down_and_up_pairs(self) -> None:
        ok = self.injector.send_text("äö")

        self.assertTrue(ok)
        self.assertEqual(len(self.captured), 4)
        self.assertEqual(self.batch_sizes, [2, 2])
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

    def test_send_ctrl_backspace_sends_atomic_four_event_combo(self) -> None:
        from puhis.platform.keyboard_injector import VK_BACK, VK_CONTROL

        ok = self.injector.send_key(VirtualKey.CTRL_BACKSPACE)

        self.assertTrue(ok)
        self.assertEqual(self.batch_sizes, [4])
        self.assertEqual(
            [(item.union.ki.wVk, item.union.ki.dwFlags) for item in self.captured],
            [
                (VK_CONTROL, 0),
                (VK_BACK, 0),
                (VK_BACK, KEYEVENTF_KEYUP),
                (VK_CONTROL, KEYEVENTF_KEYUP),
            ],
        )

    def test_send_text_via_clipboard_pastes_and_restores_previous_text(self) -> None:
        from puhis.platform.keyboard_injector import VK_CONTROL, VK_V

        class _FakeClipboard:
            def __init__(self) -> None:
                self.value: str | None = "vanha leike"
                self.history: list[str] = []

            def get_text(self) -> str | None:
                return self.value

            def set_text(self, text: str) -> bool:
                self.value = text
                self.history.append(text)
                return True

        clipboard = _FakeClipboard()
        injector = KeyboardInjector(
            send_input_fn=self.injector._send_input,
            inter_key_delay_s=0.0,
            clipboard=clipboard,
            paste_settle_delay_s=0.0,
        )

        ok = injector.send_text("Pieni kissa istuu ikkunalla.")

        self.assertTrue(ok)
        self.assertEqual(clipboard.history, ["Pieni kissa istuu ikkunalla.", "vanha leike"])
        self.assertEqual(clipboard.value, "vanha leike")
        self.assertEqual(
            [(item.union.ki.wVk, item.union.ki.dwFlags) for item in self.captured],
            [
                (VK_CONTROL, 0),
                (VK_V, 0),
                (VK_V, KEYEVENTF_KEYUP),
                (VK_CONTROL, KEYEVENTF_KEYUP),
            ],
        )

    def test_send_clear_all_sends_ctrl_a_and_backspace(self) -> None:
        from puhis.platform.keyboard_injector import VK_A, VK_BACK, VK_CONTROL

        ok = self.injector.send_key(VirtualKey.CLEAR_ALL)

        self.assertTrue(ok)
        self.assertEqual(self.batch_sizes, [6])
        self.assertEqual(
            [(item.union.ki.wVk, item.union.ki.dwFlags) for item in self.captured],
            [
                (VK_CONTROL, 0),
                (VK_A, 0),
                (VK_A, KEYEVENTF_KEYUP),
                (VK_CONTROL, KEYEVENTF_KEYUP),
                (VK_BACK, 0),
                (VK_BACK, KEYEVENTF_KEYUP),
            ],
        )


if __name__ == "__main__":
    unittest.main()
