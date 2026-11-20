"""Asetusten tietomalli sekä atominen JSON-lataus ja -tallennus."""

import json
import logging
import os
import tempfile
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from puhis.core.app_state import AssistantMode

logger = logging.getLogger(__name__)


class CatTheme(StrEnum):
    """Kissan turkin väriteema."""

    CHARCOAL = "charcoal"
    ORANGE = "orange"
    CREAM = "cream"


class SttEngine(StrEnum):
    """Valittava puheentunnistusmoottori."""

    WEB = "web"
    WHISPER = "whisper"


CONFIG_VERSION = 1
MAX_CONFIG_BYTES = 1_000_000
MIN_CAT_SIZE = 48
MAX_CAT_SIZE = 256
DEFAULT_CAT_SIZE = 96
DEFAULT_WAKE_WORD = "puhis"

# Erikoisnäppäimet merkitään aaltosulkeilla, jotta ne erottuvat tavallisista merkeistä.
DEFAULT_KEYWORDS: dict[str, str] = {
    "piste": ".",
    "pilkku": ",",
    "kysymysmerkki": "?",
    "huutomerkki": "!",
    "kaksoispiste": ":",
    "puolipiste": ";",
    "plus": "+",
    "miinus": "-",
    "kertaa": "*",
    "jaettuna": "/",
    "yhtä kuin": "=",
    "enter": "{ENTER}",
    "rivinvaihto": "{ENTER}",
    "tab": "{TAB}",
    "välilyönti": "{SPACE}",
    "pyyhi": "{BACKSPACE}",
    "esc": "{ESCAPE}",
}

DEFAULT_APP_ALIASES: dict[str, list[str]] = {
    "laskin": ["calc.exe"],
    "muistio": ["notepad.exe"],
}

# Virhetila on ajonaikainen, eikä sovellusta saa käynnistää siihen.
_ALLOWED_START_MODES = frozenset({AssistantMode.IDLE, AssistantMode.DICTATING, AssistantMode.MUTED})


@dataclass(slots=True)
class AppConfig:
    """Käyttäjän asetukset."""

    wake_word: str = DEFAULT_WAKE_WORD
    start_mode: AssistantMode = AssistantMode.IDLE
    stt_engine: SttEngine = SttEngine.WEB
    cat_theme: CatTheme = CatTheme.CHARCOAL
    cat_size: int = DEFAULT_CAT_SIZE
    cat_x: int | None = None
    cat_y: int | None = None
    keywords: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_KEYWORDS))
    app_aliases: dict[str, list[str]] = field(
        default_factory=lambda: {name: list(cmd) for name, cmd in DEFAULT_APP_ALIASES.items()}
    )

    def to_dict(self) -> dict[str, Any]:
        """Muuntaa asetukset JSON-yhteensopivaksi sanakirjaksi."""
        return {
            "version": CONFIG_VERSION,
            "wake_word": self.wake_word,
            "start_mode": self.start_mode.value,
            "stt_engine": self.stt_engine.value,
            "cat_theme": self.cat_theme.value,
            "cat_size": self.cat_size,
            "cat_x": self.cat_x,
            "cat_y": self.cat_y,
            "keywords": dict(self.keywords),
            "app_aliases": {name: list(cmd) for name, cmd in self.app_aliases.items()},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppConfig":
        """Luo asetukset sanakirjasta; virheelliset kentät korvataan oletuksilla."""
        defaults = cls()
        return cls(
            wake_word=_parse_wake_word(data.get("wake_word"), defaults.wake_word),
            start_mode=_parse_start_mode(data.get("start_mode"), defaults.start_mode),
            stt_engine=_parse_stt_engine(data.get("stt_engine"), defaults.stt_engine),
            cat_theme=_parse_cat_theme(data.get("cat_theme"), defaults.cat_theme),
            cat_size=_parse_cat_size(data.get("cat_size"), defaults.cat_size),
            cat_x=_parse_optional_int(data.get("cat_x")),
            cat_y=_parse_optional_int(data.get("cat_y")),
            keywords=_parse_keywords(data.get("keywords"), defaults.keywords),
            app_aliases=_parse_app_aliases(data.get("app_aliases"), defaults.app_aliases),
        )


def _parse_wake_word(value: Any, default: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip().lower()
    if value is not None:
        logger.warning("Virheellinen herätesana asetuksissa, käytetään oletusta")
    return default


def _parse_start_mode(value: Any, default: AssistantMode) -> AssistantMode:
    try:
        mode = AssistantMode(value)
    except ValueError:
        return default
    return mode if mode in _ALLOWED_START_MODES else default


def _parse_cat_theme(value: Any, default: CatTheme) -> CatTheme:
    try:
        return CatTheme(value)
    except ValueError:
        return default


def _parse_stt_engine(value: Any, default: SttEngine) -> SttEngine:
    try:
        return SttEngine(value)
    except ValueError:
        return default


def _parse_cat_size(value: Any, default: int) -> int:
    # bool on int:n aliluokka, joten se suljetaan erikseen pois.
    if isinstance(value, bool) or not isinstance(value, int):
        return default
    return max(MIN_CAT_SIZE, min(MAX_CAT_SIZE, value))


def _parse_optional_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _parse_keywords(value: Any, default: dict[str, str]) -> dict[str, str]:
    if not isinstance(value, dict):
        return dict(default)
    merged = dict(default)
    for key, output in value.items():
        if isinstance(key, str) and key.strip() and isinstance(output, str) and output:
            merged[key.strip().lower()] = output
    return merged


def _parse_app_aliases(value: Any, default: dict[str, list[str]]) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        return {name: list(cmd) for name, cmd in default.items()}
    result: dict[str, list[str]] = {}
    for name, command in value.items():
        if not isinstance(name, str) or not name.strip():
            continue
        if not isinstance(command, list) or not command:
            continue
        if not all(isinstance(part, str) and part for part in command):
            continue
        result[name.strip().lower()] = list(command)
    return result


class ConfigStore:
    """Lataa ja tallentaa asetukset JSON-tiedostoon atomisesti."""

    def __init__(self, path: Path) -> None:
        self._path = path

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> AppConfig:
        """Lataa asetukset; puuttuva tai viallinen tiedosto palauttaa oletukset."""
        if not self._path.exists():
            logger.info("Asetustiedostoa ei löytynyt, käytetään oletuksia: %s", self._path)
            return AppConfig()

        try:
            size = self._path.stat().st_size
            if size > MAX_CONFIG_BYTES:
                raise ValueError(f"asetustiedosto on liian suuri ({size} tavua)")
            data = json.loads(self._path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("asetustiedoston juuri ei ole JSON-objekti")
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            # json.JSONDecodeError on ValueError:n aliluokka.
            logger.warning("Asetustiedosto on viallinen (%s), käytetään oletuksia", exc)
            self._backup_corrupt_file()
            return AppConfig()

        return AppConfig.from_dict(data)

    def save(self, config: AppConfig) -> None:
        """Tallentaa asetukset atomisesti.

        Kirjoitetaan ensin väliaikaistiedostoon samaan hakemistoon ja korvataan
        kohde `os.replace()`-kutsulla, jottei kaatuminen jätä puolikasta tiedostoa.

        Raises:
            OSError: jos tallennus epäonnistuu.
        """
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=self._path.parent, prefix=".config-", suffix=".tmp")
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(config.to_dict(), handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, self._path)
        except BaseException:
            tmp_path.unlink(missing_ok=True)
            raise

    def _backup_corrupt_file(self) -> None:
        backup = self._path.with_name(self._path.name + ".corrupt")
        try:
            os.replace(self._path, backup)
            logger.warning("Viallinen asetustiedosto siirrettiin: %s", backup)
        except OSError:
            logger.exception("Viallisen asetustiedoston varmuuskopiointi epäonnistui")
