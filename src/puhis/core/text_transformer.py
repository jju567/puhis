"""Sanelutekstin muunnos teksti- ja näppäintapahtumiksi (`TextAction`, `KeyAction`)."""

from collections.abc import Mapping

from puhis.core.actions import InputAction, KeyAction, TextAction, parse_special_key_token

# Välimerkit, joiden eteen ei tule välilyöntiä, mutta joiden jälkeen tulee välilyönti
# ennen seuraavaa tavallista sanaa.
_NO_SPACE_BEFORE = frozenset({".", ",", "?", "!", ":", ";", ")", "]", "}"})
_NO_SPACE_AFTER = frozenset({"(", "[", "{"})
_STT_TRAILING_PUNCT = ".,!?:;"


def transform_dictation(text: str, keywords: Mapping[str, str]) -> list[InputAction]:
    """Muuntaa puhutun sanelujakson teksti- ja erikoisnäppäintoiminnoiksi.

    Args:
        text: Puheentunnistimelta saatu raakateksti.
        keywords: Käyttäjän avainsanataulukko (esim. `{"pilkku": ",", "enter": "{ENTER}"}`).

    Returns:
        Järjestetty lista `TextAction`- ja `KeyAction`-tapahtumia.
    """
    raw_words = text.split()
    if not raw_words:
        return []

    normalized_keywords, max_kw_len = _prepare_keywords(keywords)
    actions: list[InputAction] = []
    text_buffer: list[tuple[str, bool]] = []  # (teksti, onko_avainsanasta)

    idx = 0
    word_count = len(raw_words)
    while idx < word_count:
        match = _match_keyword(raw_words, idx, normalized_keywords, max_kw_len)
        if match is not None:
            replacement, consumed = match
            idx += consumed
            special_key = parse_special_key_token(replacement)
            if special_key is not None:
                _flush_text_buffer(text_buffer, actions)
                actions.append(KeyAction(key=special_key))
            else:
                text_buffer.append((replacement, True))
        else:
            text_buffer.append((raw_words[idx], False))
            idx += 1

    _flush_text_buffer(text_buffer, actions)
    return actions


def _prepare_keywords(keywords: Mapping[str, str]) -> tuple[dict[tuple[str, ...], str], int]:
    """Esikäsittelee avainsanat monisanaista hakua varten."""
    prepared: dict[tuple[str, ...], str] = {}
    max_len = 0
    for phrase, output in keywords.items():
        parts = tuple(phrase.strip().lower().split())
        if not parts or not output:
            continue
        prepared[parts] = output
        if len(parts) > max_len:
            max_len = len(parts)
    return prepared, max_len


def _match_keyword(
    words: list[str],
    start: int,
    keywords: dict[tuple[str, ...], str],
    max_kw_len: int,
) -> tuple[str, int] | None:
    """Etsii pisimmän avainsanaosuman kohdasta `start`."""
    if not keywords or max_kw_len <= 0:
        return None

    upper_bound = min(max_kw_len, len(words) - start)
    for length in range(upper_bound, 0, -1):
        span = words[start : start + length]
        exact_key = tuple(w.lower() for w in span)
        if exact_key in keywords:
            return keywords[exact_key], length

        # STT lisää usein pisteen tai pilkun lauseen viimeisen avainsanan perään
        # (esim. "enter." -> "enter").
        stripped_key = tuple(w.strip(_STT_TRAILING_PUNCT).lower() for w in span)
        if all(stripped_key) and stripped_key in keywords:
            return keywords[stripped_key], length

    return None


def _flush_text_buffer(
    buffer: list[tuple[str, bool]],
    actions: list[InputAction],
) -> None:
    """Yhdistää puskurin sanat ja välimerkit yhdeksi `TextAction`-tapahtumaksi."""
    if not buffer:
        return

    rendered = ""
    prev_from_keyword = False
    for piece, from_keyword in buffer:
        if not piece:
            continue
        if not rendered:
            rendered = piece
            prev_from_keyword = from_keyword
            continue

        attaches_left = piece[0] in _NO_SPACE_BEFORE
        if attaches_left:
            # Jos STT lisäsi jo saman välimerkin edellisen tavallisen sanan perään
            # (esim. "Moi, pilkku"), poistetaan tuplavälimerkki.
            if not prev_from_keyword and rendered.endswith(piece[0]):
                rendered = rendered[:-1]
            rendered += piece
        elif rendered[-1] in _NO_SPACE_AFTER:
            rendered += piece
        else:
            rendered += " " + piece

        prev_from_keyword = from_keyword

    buffer.clear()
    if rendered:
        actions.append(TextAction(text=rendered))
