import unittest

from puhis.core.actions import CommandType, ParsedCommand
from puhis.core.command_parser import parse_command


class CommandParserTests(unittest.TestCase):
    def test_parse_command_without_wake_word_returns_none(self) -> None:
        self.assertIsNone(parse_command("kirjoita tämä muistioon"))
        self.assertIsNone(parse_command("   "))
        self.assertIsNone(parse_command(""))

    def test_parse_command_recognizes_dictation_start_and_stop(self) -> None:
        start_cases = ["puhis sanele", "Puhis, kirjoita!", "PUHIS aloita sanelu.", "puhis sanelu päälle"]
        for text in start_cases:
            with self.subTest(text=text):
                result = parse_command(text)
                self.assertIsNotNone(result)
                assert result is not None
                self.assertIs(result.command_type, CommandType.START_DICTATION)

        stop_cases = ["puhis seis", "Puhis! Lopeta.", "puhis lopeta sanelu", "puhis sanelu pois", "puhis stop"]
        for text in stop_cases:
            with self.subTest(text=text):
                result = parse_command(text)
                self.assertIsNotNone(result)
                assert result is not None
                self.assertIs(result.command_type, CommandType.STOP_DICTATION)

    def test_parse_command_recognizes_mute(self) -> None:
        result = parse_command("Puhis, mykistä.")
        self.assertEqual(
            result,
            ParsedCommand(command_type=CommandType.MUTE, target=None, raw_text="Puhis, mykistä."),
        )

    def test_parse_command_recognizes_save_window_and_split_slot(self) -> None:
        direct = parse_command("puhis save t1")
        split_slot = parse_command("Puhis tallenna t 2.")

        self.assertEqual(
            direct,
            ParsedCommand(command_type=CommandType.SAVE_WINDOW, target="t1", raw_text="puhis save t1"),
        )
        self.assertEqual(
            split_slot,
            ParsedCommand(command_type=CommandType.SAVE_WINDOW, target="t2", raw_text="Puhis tallenna t 2."),
        )

    def test_parse_command_recognizes_focus_with_and_without_verb(self) -> None:
        explicit = parse_command("puhis fokus t1")
        shorthand = parse_command("Puhis, t1!")
        shorthand_split = parse_command("puhis t 3")
        custom_alias = parse_command("puhis editori", known_window_aliases={"editori"})

        self.assertEqual(
            explicit,
            ParsedCommand(command_type=CommandType.FOCUS_WINDOW, target="t1", raw_text="puhis fokus t1"),
        )
        self.assertEqual(
            shorthand,
            ParsedCommand(command_type=CommandType.FOCUS_WINDOW, target="t1", raw_text="Puhis, t1!"),
        )
        self.assertEqual(
            shorthand_split,
            ParsedCommand(command_type=CommandType.FOCUS_WINDOW, target="t3", raw_text="puhis t 3"),
        )
        self.assertEqual(
            custom_alias,
            ParsedCommand(command_type=CommandType.FOCUS_WINDOW, target="editori", raw_text="puhis editori"),
        )

    def test_parse_command_recognizes_hide_active_and_named_window(self) -> None:
        active = parse_command("puhis piilota")
        named = parse_command("Puhis, piilota t1.")
        minimoi = parse_command("puhis minimoi t 2")

        self.assertEqual(
            active,
            ParsedCommand(command_type=CommandType.HIDE_WINDOW, target=None, raw_text="puhis piilota"),
        )
        self.assertEqual(
            named,
            ParsedCommand(command_type=CommandType.HIDE_WINDOW, target="t1", raw_text="Puhis, piilota t1."),
        )
        self.assertEqual(
            minimoi,
            ParsedCommand(command_type=CommandType.HIDE_WINDOW, target="t2", raw_text="puhis minimoi t 2"),
        )

    def test_parse_command_recognizes_launch_app(self) -> None:
        avaa = parse_command("puhis avaa laskin")
        kaynnista = parse_command("Puhis, käynnistä muistio!")
        multiword = parse_command("puhis avaa visual studio")

        self.assertEqual(
            avaa,
            ParsedCommand(command_type=CommandType.LAUNCH_APP, target="laskin", raw_text="puhis avaa laskin"),
        )
        self.assertEqual(
            kaynnista,
            ParsedCommand(
                command_type=CommandType.LAUNCH_APP,
                target="muistio",
                raw_text="Puhis, käynnistä muistio!",
            ),
        )
        self.assertEqual(
            multiword,
            ParsedCommand(
                command_type=CommandType.LAUNCH_APP,
                target="visual studio",
                raw_text="puhis avaa visual studio",
            ),
        )

    def test_parse_command_supports_custom_and_multiword_wake_word(self) -> None:
        single = parse_command("Kissa avaa laskin", wake_word="kissa")
        multi = parse_command("Hei kissa, save t1", wake_word="hei kissa")

        self.assertIsNotNone(single)
        assert single is not None
        self.assertIs(single.command_type, CommandType.LAUNCH_APP)
        self.assertEqual(single.target, "laskin")

        self.assertIsNotNone(multi)
        assert multi is not None
        self.assertIs(multi.command_type, CommandType.SAVE_WINDOW)
        self.assertEqual(multi.target, "t1")

    def test_parse_command_marks_incomplete_or_unrecognized_as_unknown(self) -> None:
        cases = ["puhis", "puhis save", "puhis fokus", "puhis avaa", "puhis keitä kahvia"]
        for text in cases:
            with self.subTest(text=text):
                result = parse_command(text)
                self.assertIsNotNone(result)
                assert result is not None
                self.assertIs(result.command_type, CommandType.UNKNOWN)


if __name__ == "__main__":
    unittest.main()
