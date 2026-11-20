"""Asetusten, avainsanataulukon ja sovellusaliasten validointi ennen tallennusta."""

from collections.abc import Sequence
from dataclasses import dataclass

from puhis.core.actions import parse_special_key_token
from puhis.core.config_store import MAX_CAT_SIZE, MIN_CAT_SIZE, AppConfig

MAX_WAKE_WORD_LEN = 40
_FORBIDDEN_SHELL_CHARS = frozenset({"|", "&", ";", "`", "$", ">", "<", "\n", "\r"})


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Validoinnin tulos ja mahdolliset suomenkieliset virheilmoitukset."""

    valid: bool
    errors: list[str]


def validate_wake_word(wake_word: str) -> str | None:
    """Tarkistaa herätesanan kelvollisuuden. Palauttaa virheviestin tai `None`."""
    cleaned = wake_word.strip()
    if not cleaned:
        return "Herätesana ei saa olla tyhjä."
    if len(cleaned) > MAX_WAKE_WORD_LEN:
        return f"Herätesana on liian pitkä (enintään {MAX_WAKE_WORD_LEN} merkkiä)."
    return None


def validate_keywords_rows(
    rows: Sequence[tuple[str, str]],
) -> tuple[dict[str, str], list[str]]:
    """Validoi käyttöliittymän avainsanarivit `(puhesana, tuloste)`.

    Returns:
        `(puhdistettu_sanakirja, virheviestit)`
    """
    result: dict[str, str] = {}
    errors: list[str] = []

    for idx, (raw_phrase, raw_output) in enumerate(rows, start=1):
        phrase = raw_phrase.strip().lower()
        output = raw_output.strip() if raw_output.strip() else raw_output

        if not phrase and not output:
            continue
        if not phrase:
            errors.append(f"Avainsanarivi {idx}: puhesana puuttuu.")
            continue
        if not output:
            errors.append(f"Avainsanarivi {idx} ('{phrase}'): korvaava merkki tai näppäin puuttuu.")
            continue
        if phrase in result:
            errors.append(f"Toistuva avainsana: '{phrase}'.")
            continue

        stripped_out = output.strip()
        if len(stripped_out) > 2 and stripped_out.startswith("{") and stripped_out.endswith("}"):
            if parse_special_key_token(stripped_out) is None:
                errors.append(
                    f"Avainsana '{phrase}': tuntematon erikoisnäppäin '{stripped_out}'."
                )
                continue
            output = stripped_out.upper()

        result[phrase] = output

    return result, errors


def validate_app_alias_rows(
    rows: Sequence[tuple[str, Sequence[str]]],
) -> tuple[dict[str, list[str]], list[str]]:
    """Validoi käyttöliittymän sovellusaliasrivit `(puhenimi, komentolista)`.

    Returns:
        `(puhdistettu_sanakirja, virheviestit)`
    """
    result: dict[str, list[str]] = {}
    errors: list[str] = []

    for idx, (raw_alias, raw_cmd) in enumerate(rows, start=1):
        alias = raw_alias.strip().lower()
        parts = [part.strip() for part in raw_cmd if part and part.strip()]

        if not alias and not parts:
            continue
        if not alias:
            errors.append(f"Sovellusrivi {idx}: puhenimi puuttuu.")
            continue
        if not parts:
            errors.append(f"Sovellus '{alias}': suoritettava ohjelmapolku puuttuu.")
            continue
        if alias in result:
            errors.append(f"Toistuva sovellusnimi: '{alias}'.")
            continue
        if any(any(ch in part for ch in _FORBIDDEN_SHELL_CHARS) for part in parts):
            errors.append(
                f"Sovellus '{alias}': komento sisältää kiellettyjä erikoismerkkejä."
            )
            continue

        result[alias] = parts

    return result, errors


def validate_config(config: AppConfig) -> ValidationResult:
    """Validoi koko `AppConfig`-olion."""
    errors: list[str] = []

    wake_err = validate_wake_word(config.wake_word)
    if wake_err is not None:
        errors.append(wake_err)

    if not (MIN_CAT_SIZE <= config.cat_size <= MAX_CAT_SIZE):
        errors.append(f"Kissan koon tulee olla välillä {MIN_CAT_SIZE}–{MAX_CAT_SIZE} px.")

    _, kw_errors = validate_keywords_rows(list(config.keywords.items()))
    errors.extend(kw_errors)

    _, app_errors = validate_app_alias_rows(list(config.app_aliases.items()))
    errors.extend(app_errors)

    return ValidationResult(valid=not errors, errors=errors)
