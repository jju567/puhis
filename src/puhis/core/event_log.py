"""Muistirajoitettu tapahtumaloki (ring-buffer) tunnistetuille puhejaksoille ja komennoille."""

from collections import deque
from dataclasses import dataclass
from datetime import datetime

DEFAULT_MAX_EVENTS = 200


@dataclass(frozen=True, slots=True)
class LogEvent:
    """Yksittäinen puhe- tai komentotapahtuma lokinäkymää varten."""

    timestamp: str
    heard_text: str
    action_message: str
    success: bool = True


class EventLog:
    """Säilyttää viimeisimmät N puhe- ja komentotapahtumaa muistissa."""

    def __init__(self, max_entries: int = DEFAULT_MAX_EVENTS) -> None:
        if max_entries <= 0:
            raise ValueError("max_entries tulee olla positiivinen kokonaisluku")
        self._max_entries = max_entries
        self._entries: deque[LogEvent] = deque(maxlen=max_entries)

    @property
    def max_entries(self) -> int:
        return self._max_entries

    def append(
        self,
        heard_text: str,
        action_message: str,
        *,
        success: bool = True,
        timestamp: str | None = None,
    ) -> LogEvent:
        """Lisää uuden tapahtuman lokiin ja palauttaa sen."""
        ts = timestamp if timestamp is not None else datetime.now().strftime("%H:%M:%S")
        event = LogEvent(
            timestamp=ts,
            heard_text=heard_text.strip(),
            action_message=action_message.strip(),
            success=success,
        )
        self._entries.append(event)
        return event

    def list_events(self) -> list[LogEvent]:
        """Palauttaa tapahtumat vanhimmasta uusimpaan."""
        return list(self._entries)

    def clear(self) -> None:
        """Tyhjentää tapahtumalokin."""
        self._entries.clear()
