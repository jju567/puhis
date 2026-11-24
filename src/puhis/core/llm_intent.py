"""LLM-pohjaisen komentotulkinnan promptin rakennus ja JSON-vastauksen validointi."""

from collections.abc import Collection
import json
import re
from typing import Protocol

from puhis.core.actions import CommandType, ParsedCommand
from puhis.core.window_registry import is_default_window_slot, normalize_window_alias

_ALLOWED_LLM_COMMANDS = frozenset({
    CommandType.START_DICTATION,
    CommandType.STOP_DICTATION,
    CommandType.MUTE,
    CommandType.SAVE_WINDOW,
    CommandType.FOCUS_WINDOW,
    CommandType.HIDE_WINDOW,
    CommandType.LAUNCH_APP,
})

_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


class IntentInterpreterProtocol(Protocol):
    """Rajapinta epäselvien puhekomentojen LLM-tulkinnalle."""

    def interpret_intent(
        self,
        text: str,
        *,
        known_window_aliases: Collection[str],
        known_app_aliases: Collection[str],
    ) -> ParsedCommand | None: ...


def build_intent_messages(
    text: str,
    *,
    known_window_aliases: Collection[str],
    known_app_aliases: Collection[str],
) -> list[dict[str, str]]:
    """Rakentaa OpenAI/OpenRouter-yhteensopivan viestilistan komentotulkintaan."""
    windows = sorted({normalize_window_alias(w) for w in known_window_aliases if w.strip()})
    apps = sorted({a.strip().lower() for a in known_app_aliases if a.strip()})

    system_prompt = (
        "Olet suomenkielisen Puhis-ääniavustimen komentotulkki. "
        "Päättele käyttäjän puhumasta tekstistä aikomus ja palauta VAIN JSON-objekti "
        'muodossa {"command": "...", "target": ...}.\n'
        "Sallitut command-arvot:\n"
        '- "start_dictation": käyttäjä haluaa aloittaa sanelun/kirjoittamisen (target: null)\n'
        '- "stop_dictation": käyttäjä haluaa lopettaa sanelun (target: null)\n'
        '- "mute": käyttäjä haluaa mykistää mikrofonin (target: null)\n'
        '- "save_window": tallenna aktiivinen ikkuna paikkaan t1..t9 (target: "t1".."t9")\n'
        '- "focus_window": tuo tallennettu ikkuna esiin (target: ikkunan alias)\n'
        '- "hide_window": piilota/minimoi ikkuna (target: ikkunan alias tai null aktiiviselle)\n'
        '- "launch_app": käynnistä sovellus (target: sovellusalias)\n'
        '- "unknown": ei mikään edellisistä (target: null)\n'
        f"Tallennetut ikkuna-aliakset: {windows or ['t1..t9']}\n"
        f"Sallitut sovellusaliakset: {apps or ['(ei määritelty)']}\n"
        "Älä keksi uusia sovelluksia tai komentoja. Vastaa pelkällä JSON-objektilla."
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": text.strip()},
    ]


def parse_llm_intent_response(
    raw_content: str,
    raw_text: str,
    *,
    known_window_aliases: Collection[str],
    known_app_aliases: Collection[str],
) -> ParsedCommand | None:
    """Jäsentää ja validoi LLM:n JSON-vastauksen turvalliseksi `ParsedCommand`-olioksi."""
    payload = _extract_json_dict(raw_content)
    if payload is None:
        return None

    raw_cmd = payload.get("command")
    if not isinstance(raw_cmd, str):
        return None
    try:
        cmd_type = CommandType(raw_cmd.strip().lower())
    except ValueError:
        return None

    if cmd_type not in _ALLOWED_LLM_COMMANDS:
        return None

    raw_target = payload.get("target")
    target: str | None = None
    if isinstance(raw_target, str) and raw_target.strip():
        target = raw_target.strip().lower()

    if cmd_type in {CommandType.START_DICTATION, CommandType.STOP_DICTATION, CommandType.MUTE}:
        return ParsedCommand(command_type=cmd_type, target=None, raw_text=raw_text)

    if cmd_type is CommandType.LAUNCH_APP:
        allowed_apps = {a.strip().lower(): a.strip().lower() for a in known_app_aliases if a.strip()}
        if target is None or target not in allowed_apps:
            return None
        return ParsedCommand(command_type=cmd_type, target=allowed_apps[target], raw_text=raw_text)

    allowed_windows = {
        normalize_window_alias(w): normalize_window_alias(w)
        for w in known_window_aliases
        if w.strip()
    }
    if cmd_type is CommandType.HIDE_WINDOW and target is None:
        return ParsedCommand(command_type=cmd_type, target=None, raw_text=raw_text)

    if target is None:
        return None

    normalized_target = normalize_window_alias(target)
    if normalized_target in allowed_windows:
        return ParsedCommand(
            command_type=cmd_type,
            target=allowed_windows[normalized_target],
            raw_text=raw_text,
        )
    if is_default_window_slot(normalized_target):
        return ParsedCommand(command_type=cmd_type, target=normalized_target, raw_text=raw_text)

    return None


def _extract_json_dict(raw_content: str) -> dict[str, object] | None:
    text = raw_content.strip()
    if not text:
        return None
    match = _JSON_BLOCK_RE.search(text)
    if match is None:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None
