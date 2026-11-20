"""Komentotulkin, tekstinmuunnoksen ja alustarajapintojen tietomallit."""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from puhis.core.app_state import AssistantMode


class VirtualKey(StrEnum):
    """Tuetut virtuaalinäppäimet sanelun erikoiskomennoille."""

    ENTER = "ENTER"
    TAB = "TAB"
    BACKSPACE = "BACKSPACE"
    ESCAPE = "ESCAPE"
    SPACE = "SPACE"
    DELETE = "DELETE"
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    UP = "UP"
    DOWN = "DOWN"


_SPECIAL_TOKEN_MAP: dict[str, VirtualKey] = {
    "{ENTER}": VirtualKey.ENTER,
    "{RETURN}": VirtualKey.ENTER,
    "{TAB}": VirtualKey.TAB,
    "{BACKSPACE}": VirtualKey.BACKSPACE,
    "{BS}": VirtualKey.BACKSPACE,
    "{ESCAPE}": VirtualKey.ESCAPE,
    "{ESC}": VirtualKey.ESCAPE,
    "{SPACE}": VirtualKey.SPACE,
    "{DELETE}": VirtualKey.DELETE,
    "{DEL}": VirtualKey.DELETE,
    "{LEFT}": VirtualKey.LEFT,
    "{RIGHT}": VirtualKey.RIGHT,
    "{UP}": VirtualKey.UP,
    "{DOWN}": VirtualKey.DOWN,
}


def parse_special_key_token(token: str) -> VirtualKey | None:
    """Tunnistaa asetustiedoston aaltosulkumuotoisen näppäinmerkin (esim. `{ENTER}`)."""
    return _SPECIAL_TOKEN_MAP.get(token.strip().upper())


@dataclass(frozen=True, slots=True)
class TextAction:
    """Tekstijakso, joka syötetään Unicode-näppäintapahtumina."""

    text: str


@dataclass(frozen=True, slots=True)
class KeyAction:
    """Yksittäinen erikoisnäppäinpainallus (`VK_*`)."""

    key: VirtualKey


type InputAction = TextAction | KeyAction


class CommandType(StrEnum):
    """Herätesanalla alkavan komennon tyyppi."""

    START_DICTATION = "start_dictation"
    STOP_DICTATION = "stop_dictation"
    MUTE = "mute"
    SAVE_WINDOW = "save_window"
    FOCUS_WINDOW = "focus_window"
    HIDE_WINDOW = "hide_window"
    LAUNCH_APP = "launch_app"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ParsedCommand:
    """Jäsennetty herätesanakomento."""

    command_type: CommandType
    target: str | None = None
    raw_text: str = ""


@dataclass(frozen=True, slots=True)
class WindowInfo:
    """Windows-ikkunan tunnistetiedot."""

    hwnd: int
    title: str = ""
    process_name: str = ""


@dataclass(frozen=True, slots=True)
class UtteranceResult:
    """Puhejakson käsittelyn lopputulos ja käyttäjälle näytettävä palaute."""

    handled: bool
    success: bool
    message: str
    new_mode: AssistantMode | None = None


class KeyboardInjectorProtocol(Protocol):
    """Alustariippumaton rajapinta tekstin ja näppäinten syöttöön."""

    def send_actions(self, actions: Sequence[InputAction]) -> bool:
        """Lähettää teksti- ja näppäintapahtumat aktiiviseen ikkunaan."""


class WindowManagerProtocol(Protocol):
    """Alustariippumaton rajapinta Windows-ikkunoiden hallintaan."""

    def get_active_window(self) -> WindowInfo | None:
        """Palauttaa aktiivisen etualaikkunan tiedot tai `None`."""

    def is_window_valid(self, hwnd: int) -> bool:
        """Tarkistaa, onko ikkunakahva edelleen olemassa."""

    def focus_window(self, hwnd: int) -> bool:
        """Tuo ikkunan etualalle ja palauttaa sen tarvittaessa minimoinnista."""

    def minimize_window(self, hwnd: int) -> bool:
        """Minimoi (piilottaa tehtäväpalkkiin) annetun ikkunan."""


class AppLauncherProtocol(Protocol):
    """Alustariippumaton rajapinta valkolistattujen sovellusten käynnistykseen."""

    def launch(self, alias: str) -> tuple[bool, str]:
        """Käynnistää aliasta vastaavan sovelluksen ja palauttaa `(onnistui, viesti)`."""
