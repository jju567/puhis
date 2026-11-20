import unittest

from puhis.core.app_state import AssistantMode, toggle_dictation, toggle_mute


class AppStateTests(unittest.TestCase):
    def test_toggle_dictation_switches_idle_and_dictating(self) -> None:
        self.assertIs(toggle_dictation(AssistantMode.IDLE), AssistantMode.DICTATING)
        self.assertIs(toggle_dictation(AssistantMode.DICTATING), AssistantMode.IDLE)

    def test_toggle_dictation_does_not_unmute(self) -> None:
        self.assertIs(toggle_dictation(AssistantMode.MUTED), AssistantMode.MUTED)
        self.assertIs(toggle_dictation(AssistantMode.ERROR), AssistantMode.ERROR)
        self.assertIs(toggle_dictation(AssistantMode.COMMAND), AssistantMode.COMMAND)

    def test_toggle_mute_mutes_any_active_mode(self) -> None:
        for mode in (AssistantMode.IDLE, AssistantMode.DICTATING, AssistantMode.COMMAND, AssistantMode.ERROR):
            with self.subTest(mode=mode):
                self.assertIs(toggle_mute(mode), AssistantMode.MUTED)

    def test_toggle_mute_unmutes_to_idle(self) -> None:
        self.assertIs(toggle_mute(AssistantMode.MUTED), AssistantMode.IDLE)


if __name__ == "__main__":
    unittest.main()
