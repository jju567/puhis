"""Ajonaikainen ja levylle tallentuva rekisteri nimetyille ikkunoille (`t1`, `t2`, ...)."""

import json
import logging
import os
from pathlib import Path
import re
import tempfile
from dataclasses import dataclass

from puhis.core.actions import WindowInfo

logger = logging.getLogger(__name__)

_DEFAULT_SLOT_PATTERN = re.compile(r"^t\d{1,2}$")
_VALID_ALIAS_PATTERN = re.compile(r"^[a-z0-9åäö_-]{1,32}$")
_MAX_WINDOWS_BYTES = 512_000


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
    """Hallinnoi ikkuna-aliaksia (`save t1`, `fokus t1`, `piilota t1`) ja tallentaa ne levylle."""

    def __init__(self, storage_path: Path | None = None) -> None:
        self._storage_path = storage_path
        self._entries: dict[str, WindowEntry] = {}
        if self._storage_path is not None:
            self._load_from_disk()

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
        self._save_to_disk()
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
        removed = self._entries.pop(normalized, None) is not None
        if removed:
            self._save_to_disk()
        return removed

    def clear(self) -> None:
        """Tyhjentää kaikki tallennetut ikkunat."""
        if not self._entries:
            return
        self._entries.clear()
        self._save_to_disk()

    def has_alias(self, alias: str) -> bool:
        """Tarkistaa, onko alias tallennettuna rekisteriin."""
        normalized = normalize_window_alias(alias)
        return normalized in self._entries

    def list_entries(self) -> list[WindowEntry]:
        """Palauttaa tallennetut ikkunat aliaksen mukaan järjestettynä."""
        return [self._entries[key] for key in sorted(self._entries)]

    def _load_from_disk(self) -> None:
        assert self._storage_path is not None
        if not self._storage_path.exists():
            return
        try:
            size = self._storage_path.stat().st_size
            if size > _MAX_WINDOWS_BYTES:
                raise ValueError(f"ikkunatiedosto on liian suuri ({size} tavua)")
            data = json.loads(self._storage_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("ikkunatiedoston juuri ei ole JSON-objekti")
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            logger.warning("Tallennettujen ikkunoiden lataus epäonnistui (%s)", exc)
            return

        raw_entries = data.get("windows")
        if not isinstance(raw_entries, dict):
            return
        for raw_alias, item in raw_entries.items():
            if not isinstance(raw_alias, str) or not isinstance(item, dict):
                continue
            normalized = normalize_window_alias(raw_alias)
            if not normalized or not _VALID_ALIAS_PATTERN.match(normalized):
                continue
            hwnd = item.get("hwnd")
            title = item.get("title")
            process_name = item.get("process_name")
            if isinstance(hwnd, bool) or not isinstance(hwnd, int) or hwnd <= 0:
                continue
            if not isinstance(title, str) or not isinstance(process_name, str):
                continue
            self._entries[normalized] = WindowEntry(
                alias=normalized,
                window=WindowInfo(hwnd=hwnd, title=title, process_name=process_name),
            )

    def _save_to_disk(self) -> None:
        if self._storage_path is None:
            return
        payload = {
            "version": 1,
            "windows": {
                entry.alias: {
                    "hwnd": entry.window.hwnd,
                    "title": entry.window.title,
                    "process_name": entry.window.process_name,
                }
                for entry in self.list_entries()
            },
        }
        try:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(
                dir=self._storage_path.parent,
                prefix=".windows-",
                suffix=".tmp",
            )
            tmp_path = Path(tmp_name)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump(payload, handle, ensure_ascii=False, indent=2)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(tmp_path, self._storage_path)
            except BaseException:
                tmp_path.unlink(missing_ok=True)
                raise
        except OSError:
            logger.exception("Tallennettujen ikkunoiden kirjoitus epäonnistui: %s", self._storage_path)
