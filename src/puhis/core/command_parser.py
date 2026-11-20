"""Herätesanan tunnistus ja puhekomentojen jäsennys."""

from collections.abc import Collection

from puhis.core.actions import CommandType, ParsedCommand
from puhis.core.window_registry import is_default_window_slot, normalize_window_alias

_TOKEN_STRIP_CHARS = ".,!?:;\"'()[]{}-–—"

_START_DICTATION_PHRASES = frozenset({
    ("sanele",),
    ("kirjoita",),
    ("aloita", "sanelu"),
    ("sanelu", "päälle"),
})

_STOP_DICTATION_PHRASES = frozenset({
    ("seis",),
    ("lopeta",),
    ("stop",),
    ("lopeta", "sanelu"),
    ("sanelu", "pois"),
})

_MUTE_PHRASES = frozenset({
    ("mykistä",),
    ("hiljaa",),
})

_SAVE_VERBS = frozenset({"save", "tallenna"})
_FOCUS_VERBS = frozenset({"fokus", "focus", "aktivoi", "näytä"})
_HIDE_VERBS = frozenset({"piilota", "minimoi"})
_LAUNCH_VERBS = frozenset({"avaa", "käynnistä"})


def parse_command(
    text: str,
    wake_word: str = "puhis",
    known_window_aliases: Collection[str] = (),
) -> ParsedCommand | None:
    """Tunnistaa herätesanalla alkavan komennon.

    Args:
        text: Puheentunnistimelta saatu teksti.
        wake_word: Aktiivinen herätesana (oletus `"puhis"`).
        known_window_aliases: Tallennettujen ikkunoiden aliakset suoraa `"puhis <alias>"`-kutsua varten.

    Returns:
        `ParsedCommand`, jos syöte alkaa herätesanalla, muuten `None`.
    """
    tokens = _tokenize(text)
    wake_tokens = _tokenize(wake_word)
    if not tokens or not wake_tokens:
        return None

    if len(tokens) < len(wake_tokens):
        return None
    if tuple(tokens[: len(wake_tokens)]) != tuple(wake_tokens):
        return None

    rest = _collapse_split_slot_tokens(tokens[len(wake_tokens) :])
    if not rest:
        return ParsedCommand(command_type=CommandType.UNKNOWN, target=None, raw_text=text)

    rest_tuple = tuple(rest)
    if rest_tuple in _START_DICTATION_PHRASES:
        return ParsedCommand(command_type=CommandType.START_DICTATION, raw_text=text)
    if rest_tuple in _STOP_DICTATION_PHRASES:
        return ParsedCommand(command_type=CommandType.STOP_DICTATION, raw_text=text)
    if rest_tuple in _MUTE_PHRASES:
        return ParsedCommand(command_type=CommandType.MUTE, raw_text=text)

    verb = rest[0]
    args = rest[1:]

    if verb in _SAVE_VERBS:
        if len(args) == 1:
            return ParsedCommand(
                command_type=CommandType.SAVE_WINDOW,
                target=normalize_window_alias(args[0]),
                raw_text=text,
            )
        return ParsedCommand(
            command_type=CommandType.UNKNOWN,
            target=" ".join(rest),
            raw_text=text,
        )

    if verb in _FOCUS_VERBS:
        if len(args) == 1:
            return ParsedCommand(
                command_type=CommandType.FOCUS_WINDOW,
                target=normalize_window_alias(args[0]),
                raw_text=text,
            )
        return ParsedCommand(
            command_type=CommandType.UNKNOWN,
            target=" ".join(rest),
            raw_text=text,
        )

    if verb in _HIDE_VERBS:
        if not args:
            return ParsedCommand(command_type=CommandType.HIDE_WINDOW, target=None, raw_text=text)
        if len(args) == 1:
            return ParsedCommand(
                command_type=CommandType.HIDE_WINDOW,
                target=normalize_window_alias(args[0]),
                raw_text=text,
            )
        return ParsedCommand(
            command_type=CommandType.UNKNOWN,
            target=" ".join(rest),
            raw_text=text,
        )

    if verb in _LAUNCH_VERBS:
        target_app = " ".join(args).strip()
        if target_app:
            return ParsedCommand(
                command_type=CommandType.LAUNCH_APP,
                target=target_app,
                raw_text=text,
            )
        return ParsedCommand(
            command_type=CommandType.UNKNOWN,
            target=verb,
            raw_text=text,
        )

    # Suora ikkunakomento: "puhis t1" tai "puhis <tallennettu_alias>"
    if len(rest) == 1:
        candidate = normalize_window_alias(rest[0])
        normalized_known = {normalize_window_alias(a) for a in known_window_aliases}
        if is_default_window_slot(candidate) or candidate in normalized_known:
            return ParsedCommand(
                command_type=CommandType.FOCUS_WINDOW,
                target=candidate,
                raw_text=text,
            )

    return ParsedCommand(
        command_type=CommandType.UNKNOWN,
        target=" ".join(rest),
        raw_text=text,
    )


def _tokenize(text: str) -> list[str]:
    """Pilkoo tekstin pieniksi kirjaimiksi ja poistaa reunavälimerkit."""
    result: list[str] = []
    for raw in text.split():
        cleaned = raw.strip(_TOKEN_STRIP_CHARS).lower()
        if cleaned:
            result.append(cleaned)
    return result


def _collapse_split_slot_tokens(tokens: list[str]) -> list[str]:
    """Yhdistää puheentunnistimen erikseen pilkkomat `['t', '1']` -> `['t1']`."""
    if len(tokens) < 2:
        return tokens
    collapsed: list[str] = []
    idx = 0
    while idx < len(tokens):
        if (
            idx + 1 < len(tokens)
            and tokens[idx] == "t"
            and tokens[idx + 1].isdigit()
            and len(tokens[idx + 1]) <= 2
        ):
            collapsed.append(f"t{tokens[idx + 1]}")
            idx += 2
        else:
            collapsed.append(tokens[idx])
            idx += 1
    return collapsed
