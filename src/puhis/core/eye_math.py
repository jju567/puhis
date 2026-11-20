"""Kissan pupillien sijainnin laskenta hiiren kursorin suhteen."""

import math

DEFAULT_FOLLOW_DISTANCE = 150.0


def pupil_offset(
    eye_x: float,
    eye_y: float,
    target_x: float,
    target_y: float,
    max_offset: float,
    follow_distance: float = DEFAULT_FOLLOW_DISTANCE,
) -> tuple[float, float]:
    """Palauttaa pupillin siirtymän silmän keskipisteestä kohti kohdetta.

    Siirtymä kasvaa lineaarisesti etäisyyden mukana `follow_distance`-rajaan asti
    ja on sen jälkeen `max_offset`. Näin pupilli ei hypi reunalle, kun kursori
    liikkuu aivan kissan päällä, vaan liike näyttää luonnolliselta.
    """
    if max_offset < 0:
        raise ValueError("max_offset ei voi olla negatiivinen")
    if follow_distance <= 0:
        raise ValueError("follow_distance on oltava positiivinen")

    dx = target_x - eye_x
    dy = target_y - eye_y
    distance = math.hypot(dx, dy)
    if distance < 1e-9:
        return (0.0, 0.0)

    magnitude = max_offset * min(1.0, distance / follow_distance)
    scale = magnitude / distance
    return (dx * scale, dy * scale)
