"""Ajonaikainen rekisteri lennossa nimetyille ikkunoille (`t1`, `t2`, ...)."""

import re
from dataclasses import dataclass

from puhis.core.actions import WindowInfo

_DEFAULT_SLOT_PATTERN = re.compile(r"^t\d{1,2}$")
_VALID_ALIAS_PATTERN = re.compile(r"^[a-z0-9åäö_-]{1,32}$")


def normalize_window_alias(alias: str) -> str:
    """Siistii ja muuntaa ikkuna-aliaksen pieniksi kirjaimiksi."""
    return alias.strip().strip(".,!?:;\"'").lower()


def is_default_window_slot(token: str) -> bool:
    """Tarkistaa, onko sana oletusmuotoinen ikkunapaikka (esim. `t1`..`t99`)."""
    return bool(_DEFAULT_SLOT_PATTERN.match(normalize_window_alias(token)))


@dataclass(frozen=True, slots=True)
class WindowEntry:
    """Nimetty ikkunapaikka ja siihen tallennetun ikkunan tiedot."""

    alias: str
    window: WindowInfo


class WindowRegistry:
    """Hallinnoi ajonaikaisia ikkuna-aliaksia (`save t1`, `fokus t1`, `piilota t1`)."""

    def __init__(self) -> None:
        self._entries: dict[str, WindowEntry] = {}

    def save(self, alias: str, window: WindowInfo) -> WindowEntry:
        """Tallentaa tai päivittää ikkunan annetulle aliakselle.

        Raises:
            ValueError: jos alias on tyhjä tai sisältää kiellettyjä merkkejä, tai `hwnd <= 0`.
        """
        normalized = normalize_window_alias(alias)
        if not normalized or not _VALID_ALIAS_PATTERN.match(normalized):
            raise ValueError(f"Virheellinen ikkuna-alias: {alias!r}")
        if window.hwnd <= 0:
            raise ValueError(f"Virheellinen ikkunakahva: {window.hwnd}")

        entry = WindowEntry(alias=normalized, window=window)
        self._entries[normalized] = entry
        return entry

    def get(self, alias: str) -> WindowEntry | None:
        """Hakee tallennetun ikkunan aliaksella tai palauttaa `None`."""
        normalized = normalize_window_alias(alias)
        if not normalized:
            return None
        return self._entries.get(normalized)

    def remove(self, alias: str) -> bool:
        """Poistaa aliaksen rekisteristä. Palauttaa `True`, jos alias löytyi."""
        normalized = normalize_window_alias(alias)
        return self._entries.pop(normalized, None) is not None

    def clear(self) -> None:
        """Tyhjentää kaikki tallennetut ikkunat."""
        self._entries.clear()

    def has_alias(self, alias: str) -> bool:
        """Tarkistaa, onko alias tallennettuna rekisteriin."""
        normalized = normalize_window_alias(alias)
        return normalized in self._entries

    def list_entries(self) -> list[WindowEntry]:
        """Palauttaa tallennetut ikkunat aliaksen mukaan järjestettynä."""
        return [self._entries[key] for key in sorted(self._entries)]
