"""Avustimen toimintatilat ja tilasiirtymät."""

from enum import StrEnum


class AssistantMode(StrEnum):
    """Avustimen toimintatila.

    Arvot ovat merkkijonoja, jotta ne voidaan tallentaa sellaisenaan asetustiedostoon.
    """

    IDLE = "idle"
    DICTATING = "dictating"
    COMMAND = "command"
    MUTED = "muted"
    ERROR = "error"


def toggle_dictation(mode: AssistantMode) -> AssistantMode:
    """Vaihtaa lepotilan ja sanelutilan välillä.

    Mykistetty tai virhetila ei muutu, jotta vahingossa tehty klikkaus ei avaa
    mikrofonia käyttäjän tietämättä.
    """
    if mode is AssistantMode.IDLE:
        return AssistantMode.DICTATING
    if mode is AssistantMode.DICTATING:
        return AssistantMode.IDLE
    return mode


def toggle_mute(mode: AssistantMode) -> AssistantMode:
    """Mykistää avustimen tai palauttaa sen mykistyksestä lepotilaan."""
    if mode is AssistantMode.MUTED:
        return AssistantMode.IDLE
    return AssistantMode.MUTED
