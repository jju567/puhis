from collections.abc import Sequence
import unittest

from puhis.core.actions import InputAction, KeyAction, TextAction, VirtualKey, WindowInfo
from puhis.core.app_state import AssistantMode
from puhis.core.config_store import AppConfig
from puhis.core.utterance_router import UtteranceRouter
from puhis.core.window_registry import WindowRegistry


class _FakeKeyboardInjector:
    def __init__(self) -> None:
        self.sent_batches: list[list[InputAction]] = []
        self.should_succeed = True

    def send_actions(self, actions: Sequence[InputAction]) -> bool:
        self.sent_batches.append(list(actions))
        return self.should_succeed


class _FakeWindowManager:
    def __init__(self) -> None:
        self.active_window: WindowInfo | None = WindowInfo(
            hwnd=500,
            title="Muistio",
            process_name="notepad.exe",
        )
        self.valid_hwnds: set[int] = {500, 600}
        self.focused: list[int] = []
        self.minimized: list[int] = []

    def get_active_window(self) -> WindowInfo | None:
        return self.active_window

    def is_window_valid(self, hwnd: int) -> bool:
        return hwnd in self.valid_hwnds

    def focus_window(self, hwnd: int) -> bool:
        if hwnd not in self.valid_hwnds:
            return False
        self.focused.append(hwnd)
        return True

    def minimize_window(self, hwnd: int) -> bool:
        if hwnd not in self.valid_hwnds:
            return False
        self.minimized.append(hwnd)
        return True


class _FakeAppLauncher:
    def __init__(self) -> None:
        self.launched: list[str] = []
        self.known: set[str] = {"laskin", "muistio"}

    def launch(self, alias: str) -> tuple[bool, str]:
        if alias in self.known:
            self.launched.append(alias)
            return True, f"Käynnistettiin {alias}"
        return False, f"Tuntematon sovellus: {alias}"


class UtteranceRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = AppConfig()
        self.registry = WindowRegistry()
        self.keyboard = _FakeKeyboardInjector()
        self.windows = _FakeWindowManager()
        self.launcher = _FakeAppLauncher()
        self.router = UtteranceRouter(
            config=self.config,
            window_registry=self.registry,
            keyboard_injector=self.keyboard,
            window_manager=self.windows,
            app_launcher=self.launcher,
        )

    def test_idle_mode_ignores_speech_without_wake_word(self) -> None:
        result = self.router.handle_utterance("moi maailma", AssistantMode.IDLE)

        self.assertFalse(result.handled)
        self.assertEqual(self.keyboard.sent_batches, [])

    def test_dictating_mode_transforms_and_injects_speech(self) -> None:
        result = self.router.handle_utterance("moi pilkku maailma enter", AssistantMode.DICTATING)

        self.assertTrue(result.handled)
        self.assertTrue(result.success)
        self.assertEqual(
            self.keyboard.sent_batches,
            [[TextAction(text="moi, maailma"), KeyAction(key=VirtualKey.ENTER)]],
        )

    def test_wake_word_switches_between_idle_dictating_and_muted(self) -> None:
        start = self.router.handle_utterance("puhis sanele", AssistantMode.IDLE)
        stop = self.router.handle_utterance("puhis seis", AssistantMode.DICTATING)
        mute = self.router.handle_utterance("puhis mykistä", AssistantMode.DICTATING)

        self.assertIs(start.new_mode, AssistantMode.DICTATING)
        self.assertIs(stop.new_mode, AssistantMode.IDLE)
        self.assertIs(mute.new_mode, AssistantMode.MUTED)

    def test_save_focus_and_hide_window_workflow(self) -> None:
        save_res = self.router.handle_utterance("puhis save t1", AssistantMode.IDLE)
        focus_res = self.router.handle_utterance("puhis t1", AssistantMode.IDLE)
        hide_res = self.router.handle_utterance("puhis piilota t1", AssistantMode.IDLE)

        self.assertTrue(save_res.success)
        self.assertTrue(focus_res.success)
        self.assertTrue(hide_res.success)
        self.assertEqual(self.windows.focused, [500])
        self.assertEqual(self.windows.minimized, [500])

    def test_focus_closed_window_removes_stale_entry_and_reports_error(self) -> None:
        self.router.handle_utterance("puhis save t1", AssistantMode.IDLE)
        self.windows.valid_hwnds.discard(500)

        result = self.router.handle_utterance("puhis fokus t1", AssistantMode.IDLE)

        self.assertTrue(result.handled)
        self.assertFalse(result.success)
        self.assertIn("suljettu", result.message)
        self.assertIsNone(self.registry.get("t1"))

    def test_focus_unknown_window_returns_error(self) -> None:
        result = self.router.handle_utterance("puhis t99", AssistantMode.IDLE)

        self.assertTrue(result.handled)
        self.assertFalse(result.success)
        self.assertIn("Tuntematon ikkuna", result.message)

    def test_launch_app_executes_even_while_dictating(self) -> None:
        ok_res = self.router.handle_utterance("puhis avaa laskin", AssistantMode.DICTATING)
        fail_res = self.router.handle_utterance("puhis avaa tuntematon", AssistantMode.DICTATING)

        self.assertTrue(ok_res.success)
        self.assertEqual(self.launcher.launched, ["laskin"])
        self.assertFalse(fail_res.success)
        self.assertEqual(self.keyboard.sent_batches, [])

    def test_two_step_wake_word_then_command_without_wake_word(self) -> None:
        wake_res = self.router.handle_utterance("puis", AssistantMode.IDLE)
        self.assertTrue(wake_res.handled)
        self.assertTrue(wake_res.success)
        self.assertIs(wake_res.new_mode, AssistantMode.COMMAND)
        self.assertEqual(wake_res.message, "KUUNTELEN!")

        cmd_res = self.router.handle_utterance("avaa laskin", AssistantMode.COMMAND)
        self.assertTrue(cmd_res.handled)
        self.assertTrue(cmd_res.success)
        self.assertEqual(self.launcher.launched, ["laskin"])


if __name__ == "__main__":
    unittest.main()
