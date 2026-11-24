import json
import tempfile
import unittest
from pathlib import Path

from puhis.core.app_state import AssistantMode
from puhis.core.config_store import (
    DEFAULT_KEYWORDS,
    MAX_CAT_SIZE,
    MIN_CAT_SIZE,
    AppConfig,
    CatTheme,
    ConfigStore,
    SttEngine,
)


class ConfigStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.config_path = Path(self._tmp.name) / "puhis" / "config.json"
        self.store = ConfigStore(self.config_path)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_load_missing_file_returns_defaults(self) -> None:
        config = self.store.load()

        self.assertEqual(config, AppConfig())
        self.assertEqual(config.wake_word, "puhis")
        self.assertIs(config.cat_theme, CatTheme.CHARCOAL)
        self.assertFalse(self.config_path.exists())

    def test_save_and_load_roundtrip_preserves_values(self) -> None:
        config = AppConfig(
            wake_word="kissa",
            stt_engine=SttEngine.CHROME,
            cat_theme=CatTheme.CREAM,
            cat_size=120,
            cat_x=10,
            cat_y=-20,
        )
        config.keywords["ääkkönen"] = "ä"

        self.store.save(config)
        loaded = self.store.load()

        self.assertEqual(loaded, config)

    def test_save_writes_utf8_without_escaping(self) -> None:
        config = AppConfig(wake_word="mörkö")

        self.store.save(config)

        text = self.config_path.read_text(encoding="utf-8")
        self.assertIn("mörkö", text)

    def test_save_leaves_no_temporary_files(self) -> None:
        self.store.save(AppConfig())
        self.store.save(AppConfig(wake_word="toinen"))

        files = sorted(p.name for p in self.config_path.parent.iterdir())
        self.assertEqual(files, ["config.json"])

    def test_load_corrupt_json_returns_defaults_and_backs_up(self) -> None:
        self.config_path.parent.mkdir(parents=True)
        self.config_path.write_text("{ tämä ei ole json", encoding="utf-8")

        config = self.store.load()

        self.assertEqual(config, AppConfig())
        self.assertFalse(self.config_path.exists())
        self.assertTrue(self.config_path.with_name("config.json.corrupt").exists())

    def test_load_non_object_root_returns_defaults(self) -> None:
        self.config_path.parent.mkdir(parents=True)
        self.config_path.write_text("[1, 2, 3]", encoding="utf-8")

        self.assertEqual(self.store.load(), AppConfig())

    def test_load_invalid_fields_fall_back_to_defaults(self) -> None:
        self.config_path.parent.mkdir(parents=True)
        data = {
            "wake_word": "   ",
            "start_mode": "error",
            "cat_theme": "sininen",
            "cat_size": "iso",
            "cat_x": True,
            "cat_y": 5.5,
            "keywords": ["ei", "sanakirja"],
            "app_aliases": {"ok": ["calc.exe"], "tyhja": [], "vaara": "calc.exe", "": ["x"]},
        }
        self.config_path.write_text(json.dumps(data), encoding="utf-8")

        config = self.store.load()

        self.assertEqual(config.wake_word, "puhis")
        self.assertIs(config.start_mode, AssistantMode.IDLE)
        self.assertIs(config.cat_theme, CatTheme.CHARCOAL)
        self.assertEqual(config.cat_size, AppConfig().cat_size)
        self.assertIsNone(config.cat_x)
        self.assertIsNone(config.cat_y)
        self.assertEqual(config.keywords, DEFAULT_KEYWORDS)
        self.assertEqual(config.app_aliases, {"ok": ["calc.exe"]})

    def test_load_normalizes_wake_word_and_clamps_cat_size(self) -> None:
        self.store.save(AppConfig())
        data = json.loads(self.config_path.read_text(encoding="utf-8"))
        data["wake_word"] = "  PuHis "
        data["cat_size"] = 10_000
        self.config_path.write_text(json.dumps(data), encoding="utf-8")

        config = self.store.load()

        self.assertEqual(config.wake_word, "puhis")
        self.assertEqual(config.cat_size, MAX_CAT_SIZE)

    def test_from_dict_clamps_small_cat_size(self) -> None:
        self.assertEqual(AppConfig.from_dict({"cat_size": 1}).cat_size, MIN_CAT_SIZE)

    def test_defaults_are_independent_copies(self) -> None:
        first = AppConfig()
        first.keywords["uusi"] = "x"
        first.app_aliases["laskin"].append("--extra")

        second = AppConfig()

        self.assertNotIn("uusi", second.keywords)
        self.assertEqual(second.app_aliases["laskin"], ["calc.exe"])


if __name__ == "__main__":
    unittest.main()
