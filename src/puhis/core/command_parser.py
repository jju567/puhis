"""Herätesanan sumea (fuzzy) tunnistus ja puhekomentojen jäsennys."""

from collections.abc import Collection
from difflib import SequenceMatcher

from puhis.core.actions import CommandType, ParsedCommand
from puhis.core.window_registry import is_default_window_slot, normalize_window_alias

_TOKEN_STRIP_CHARS = ".,!?:;\"'()[]{}-–—"

# Yleiset Whisper-kuulomuodot oletusherätesanalle "puhis" (pehmeä h katoaa tai muuttuu).
_PUHIS_PHONETIC_VARIANTS = frozenset({
    "puhis",
    "puis",
    "puhi",
    "puuhis",
    "puhissa",
    "puhiksen",
    "puhista",
    "puhikselle",
    "puh",
    "puhiz",
    "buhis",
    "buis",
    "fuhis",
    "poohis",
    "puhus",
    "puhes",
})

_FILLER_PREFIXES = frozenset({"hei", "moi", "oi", "no", "hei,", "kuule"})

_START_DICTATION_VERBS = frozenset({"sanele", "kirjoita", "sanelu"})
_START_DICTATION_PHRASES = frozenset({
    ("sanele",),
    ("kirjoita",),
    ("aloita", "sanelu"),
    ("sanelu", "päälle"),
})

_STOP_DICTATION_VERBS = frozenset({"seis", "lopeta", "stop"})
_STOP_DICTATION_PHRASES = frozenset({
    ("seis",),
    ("lopeta",),
    ("stop",),
    ("lopeta", "sanelu"),
    ("sanelu", "pois"),
})

_MUTE_VERBS = frozenset({"mykistä", "hiljaa"})
_SAVE_VERBS = frozenset({"save", "tallenna", "seivaa"})
_FOCUS_VERBS = frozenset({"fokus", "focus", "aktivoi", "näytä"})
_HIDE_VERBS = frozenset({"piilota", "minimoi"})
_LAUNCH_VERBS = frozenset({"avaa", "avaan", "ava", "käynnistä", "käynnistää"})

WAKE_FUZZY_THRESHOLD = 0.72
VERB_FUZZY_THRESHOLD = 0.75
APP_FUZZY_THRESHOLD = 0.74


def parse_command(
    text: str,
    wake_word: str = "puhis",
    known_window_aliases: Collection[str] = (),
    known_app_aliases: Collection[str] = (),
    *,
    require_wake_word: bool = True,
) -> ParsedCommand | None:
    """Tunnistaa herätesanalla alkavan (tai valmiiksi herätetyn tilan) komennon.

    Args:
        text: Puheentunnistimelta saatu teksti.
        wake_word: Aktiivinen herätesana (oletus `"puhis"`).
        known_window_aliases: Tallennettujen ikkunoiden aliakset (`t1`, ...).
        known_app_aliases: Asetuksissa määritellyt sovellusaliakset (`laskin`, `muistio`, ...).
        require_wake_word: Jos `False` (kissa on jo `COMMAND`-kuuntelutilassa),
            komento hyväksytään myös ilman herätesanaa.

    Returns:
        `ParsedCommand`, jos syöte tulkitaan komennoksi, muuten `None`.
    """
    tokens = _tokenize(text)
    wake_tokens = _tokenize(wake_word)
    if not tokens or not wake_tokens:
        return None

    had_wake_word, rest_tokens = _consume_wake_word(tokens, wake_tokens)
    if not had_wake_word and require_wake_word:
        return None

    rest = _collapse_split_slot_tokens(rest_tokens)
    if not rest:
        if had_wake_word:
            return ParsedCommand(command_type=CommandType.WAKE, target=None, raw_text=text)
        return None

    parsed = _parse_action_tokens(
        rest,
        raw_text=text,
        known_window_aliases=known_window_aliases,
        known_app_aliases=known_app_aliases,
    )
    if parsed is not None:
        return parsed

    if had_wake_word:
        return ParsedCommand(
            command_type=CommandType.UNKNOWN,
            target=" ".join(rest),
            raw_text=text,
        )
    return None


def _consume_wake_word(tokens: list[str], wake_tokens: list[str]) -> tuple[bool, list[str]]:
    """Etsii ja poistaa herätesanan (sekä sen välittömät toistot) lauseen alusta."""
    w_len = len(wake_tokens)
    start_idx = 0
    if len(tokens) > w_len and tokens[0] in _FILLER_PREFIXES:
        if _span_matches_wake(tokens[1 : 1 + w_len], wake_tokens):
            start_idx = 1

    if len(tokens) - start_idx < w_len:
        return False, tokens
    if not _span_matches_wake(tokens[start_idx : start_idx + w_len], wake_tokens):
        return False, tokens

    idx = start_idx + w_len
    # Ohitetaan peräkkäiset toistot, esim. "puis, puis, avaa, laskin."
    while idx + w_len <= len(tokens) and _span_matches_wake(tokens[idx : idx + w_len], wake_tokens):
        idx += w_len

    return True, tokens[idx:]


def _span_matches_wake(span: list[str], wake_tokens: list[str]) -> bool:
    if len(span) != len(wake_tokens):
        return False
    return all(_token_matches_wake(tok, w_tok) for tok, w_tok in zip(span, wake_tokens, strict=True))


def _token_matches_wake(token: str, wake_token: str) -> bool:
    if token == wake_token:
        return True
    if wake_token == "puhis" and token in _PUHIS_PHONETIC_VARIANTS:
        return True
    if len(token) < 3 or len(wake_token) < 3:
        return False
    if len(wake_token) >= 4 and token.startswith(wake_token[:4]):
        return True
    return _similarity(token, wake_token) >= WAKE_FUZZY_THRESHOLD


def _parse_action_tokens(
    rest: list[str],
    *,
    raw_text: str,
    known_window_aliases: Collection[str],
    known_app_aliases: Collection[str],
) -> ParsedCommand | None:
    rest_tuple = tuple(rest)
    if rest_tuple in _START_DICTATION_PHRASES or (
        len(rest) == 1 and _matches_verb(rest[0], _START_DICTATION_VERBS)
    ):
        return ParsedCommand(command_type=CommandType.START_DICTATION, raw_text=raw_text)

    if rest_tuple in _STOP_DICTATION_PHRASES or (
        len(rest) == 1 and _matches_verb(rest[0], _STOP_DICTATION_VERBS)
    ):
        return ParsedCommand(command_type=CommandType.STOP_DICTATION, raw_text=raw_text)

    if len(rest) == 1 and _matches_verb(rest[0], _MUTE_VERBS):
        return ParsedCommand(command_type=CommandType.MUTE, raw_text=raw_text)

    verb = rest[0]
    args = rest[1:]

    if _matches_verb(verb, _SAVE_VERBS):
        if len(args) == 1:
            return ParsedCommand(
                command_type=CommandType.SAVE_WINDOW,
                target=normalize_window_alias(args[0]),
                raw_text=raw_text,
            )
        return None

    if _matches_verb(verb, _FOCUS_VERBS):
        if len(args) == 1:
            return ParsedCommand(
                command_type=CommandType.FOCUS_WINDOW,
                target=normalize_window_alias(args[0]),
                raw_text=raw_text,
            )
        return None

    if _matches_verb(verb, _HIDE_VERBS):
        if not args:
            return ParsedCommand(command_type=CommandType.HIDE_WINDOW, target=None, raw_text=raw_text)
        if len(args) == 1:
            return ParsedCommand(
                command_type=CommandType.HIDE_WINDOW,
                target=normalize_window_alias(args[0]),
                raw_text=raw_text,
            )
        return None

    if _matches_verb(verb, _LAUNCH_VERBS):
        target_app = " ".join(args).strip()
        if target_app:
            resolved_app = _resolve_app_alias(target_app, known_app_aliases)
            return ParsedCommand(
                command_type=CommandType.LAUNCH_APP,
                target=resolved_app,
                raw_text=raw_text,
            )
        return None

    # Suora ikkunakomento: "puhis t1" tai "puhis <tallennettu_alias>"
    if len(rest) == 1:
        candidate = normalize_window_alias(rest[0])
        normalized_known = {normalize_window_alias(a) for a in known_window_aliases}
        if is_default_window_slot(candidate) or candidate in normalized_known:
            return ParsedCommand(
                command_type=CommandType.FOCUS_WINDOW,
                target=candidate,
                raw_text=raw_text,
            )

    # Sumea sovelluskäynnistys: esim. "puhis laskin" tai "kamaa laskin",
    # kun kohde täsmää tunnettuun sovellusaliakseen.
    if known_app_aliases:
        if len(rest) == 1:
            matched_app = _match_known_app(rest[0], known_app_aliases)
            if matched_app is not None:
                return ParsedCommand(
                    command_type=CommandType.LAUNCH_APP,
                    target=matched_app,
                    raw_text=raw_text,
                )
        elif len(rest) >= 2:
            tail = " ".join(args).strip()
            matched_app = _match_known_app(tail, known_app_aliases)
            if matched_app is not None:
                return ParsedCommand(
                    command_type=CommandType.LAUNCH_APP,
                    target=matched_app,
                    raw_text=raw_text,
                )

    return None


def _matches_verb(token: str, verbs: frozenset[str]) -> bool:
    if token in verbs:
        return True
    if len(token) < 3:
        return False
    return any(_similarity(token, v) >= VERB_FUZZY_THRESHOLD for v in verbs)


def _resolve_app_alias(target: str, known_app_aliases: Collection[str]) -> str:
    """Palauttaa parhaiten täsmäävän tunnetun sovellusaliaksen tai alkuperäisen nimen."""
    matched = _match_known_app(target, known_app_aliases)
    return matched if matched is not None else target


def _match_known_app(candidate: str, known_app_aliases: Collection[str]) -> str | None:
    cleaned = candidate.strip().lower()
    if not cleaned or not known_app_aliases:
        return None

    aliases = [a.strip().lower() for a in known_app_aliases if a.strip()]
    if cleaned in aliases:
        return cleaned

    best_alias: str | None = None
    best_score = 0.0
    for alias in aliases:
        # Suomen taivutusmuodot kuten "laskimen" -> "laskin", "muistion" -> "muistio"
        if len(alias) >= 4 and cleaned.startswith(alias[:4]):
            score = max(_similarity(cleaned, alias), 0.80)
        else:
            score = _similarity(cleaned, alias)
        if score >= APP_FUZZY_THRESHOLD and score > best_score:
            best_score = score
            best_alias = alias
    return best_alias


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


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
            and tokens[idx] in ("t", "tee")
            and tokens[idx + 1].isdigit()
            and len(tokens[idx + 1]) <= 2
        ):
            collapsed.append(f"t{tokens[idx + 1]}")
            idx += 2
        else:
            collapsed.append(tokens[idx])
            idx += 1
    return collapsed
