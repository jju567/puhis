import unittest

from puhis.core.config_store import AppConfig
from puhis.core.config_validator import (
    validate_app_alias_rows,
    validate_config,
    validate_keywords_rows,
    validate_wake_word,
)


class ConfigValidatorTests(unittest.TestCase):
    def test_validate_wake_word_rejects_empty_and_overlong(self) -> None:
        self.assertIsNotNone(validate_wake_word(""))
        self.assertIsNotNone(validate_wake_word("   "))
        self.assertIsNotNone(validate_wake_word("a" * 50))
        self.assertIsNone(validate_wake_word("puhis"))

    def test_validate_keywords_rows_detects_duplicates_and_unknown_special_keys(self) -> None:
        cleaned, errors = validate_keywords_rows([
            ("  Piste ", "."),
            ("piste", "!"),
            ("enter", "{enter}"),
            ("virhe", "{EI_OLE}"),
            ("", "x"),
            ("tyhja", ""),
            ("", ""),
        ])

        self.assertEqual(cleaned, {"piste": ".", "enter": "{ENTER}"})
        self.assertEqual(len(errors), 4)

    def test_validate_app_alias_rows_detects_duplicates_and_shell_injection(self) -> None:
        cleaned, errors = validate_app_alias_rows([
            ("Muistio", ["notepad.exe"]),
            ("muistio", ["calc.exe"]),
            ("vaara", ["cmd.exe & del *.*"]),
            ("", ["calc.exe"]),
            ("tyhja", []),
            ("", []),
        ])

        self.assertEqual(cleaned, {"muistio": ["notepad.exe"]})
        self.assertEqual(len(errors), 4)

    def test_validate_config_accepts_default_config(self) -> None:
        res = validate_config(AppConfig())

        self.assertTrue(res.valid)
        self.assertEqual(res.errors, [])


if __name__ == "__main__":
    unittest.main()
