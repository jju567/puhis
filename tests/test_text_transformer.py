import unittest

from puhis.core.actions import KeyAction, TextAction, VirtualKey
from puhis.core.config_store import DEFAULT_KEYWORDS
from puhis.core.text_transformer import transform_dictation


class TextTransformerTests(unittest.TestCase):
    def test_transform_empty_or_whitespace_returns_empty_list(self) -> None:
        self.assertEqual(transform_dictation("", DEFAULT_KEYWORDS), [])
        self.assertEqual(transform_dictation("   \t\n  ", DEFAULT_KEYWORDS), [])

    def test_transform_comma_and_enter_example(self) -> None:
        actions = transform_dictation("moi pilkku maailma enter", DEFAULT_KEYWORDS)

        self.assertEqual(
            actions,
            [
                TextAction(text="moi, maailma"),
                KeyAction(key=VirtualKey.ENTER),
            ],
        )

    def test_transform_finnish_characters_and_punctuation_spacing(self) -> None:
        text = "Ääkköset toimivat kaksoispiste kyllä huutomerkki Mitä kuuluu kysymysmerkki"
        actions = transform_dictation(text, DEFAULT_KEYWORDS)

        self.assertEqual(
            actions,
            [TextAction(text="Ääkköset toimivat: kyllä! Mitä kuuluu?")],
        )

    def test_transform_consecutive_special_keys_and_text(self) -> None:
        actions = transform_dictation(
            "tab sarake yksi tab sarake kaksi rivinvaihto pyyhi",
            DEFAULT_KEYWORDS,
        )

        self.assertEqual(
            actions,
            [
                KeyAction(key=VirtualKey.TAB),
                TextAction(text="sarake yksi"),
                KeyAction(key=VirtualKey.TAB),
                TextAction(text="sarake kaksi"),
                KeyAction(key=VirtualKey.ENTER),
                KeyAction(key=VirtualKey.BACKSPACE),
            ],
        )

    def test_transform_consecutive_periods_forms_ellipsis(self) -> None:
        actions = transform_dictation("odota piste piste piste valmis piste", DEFAULT_KEYWORDS)

        self.assertEqual(actions, [TextAction(text="odota... valmis.")])

    def test_transform_handles_stt_punctuation_on_keywords(self) -> None:
        actions = transform_dictation("Moi, pilkku maailma Enter.", DEFAULT_KEYWORDS)

        self.assertEqual(
            actions,
            [
                TextAction(text="Moi, maailma"),
                KeyAction(key=VirtualKey.ENTER),
            ],
        )

    def test_transform_supports_custom_multiword_keywords(self) -> None:
        keywords = dict(DEFAULT_KEYWORDS)
        keywords["uusi rivi"] = "{ENTER}"
        keywords["sähköposti"] = "testi@esimerkki.fi"

        actions = transform_dictation("osoite on sähköposti uusi rivi kiitos", keywords)

        self.assertEqual(
            actions,
            [
                TextAction(text="osoite on testi@esimerkki.fi"),
                KeyAction(key=VirtualKey.ENTER),
                TextAction(text="kiitos"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
