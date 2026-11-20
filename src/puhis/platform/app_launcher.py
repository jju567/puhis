"""Valkolistattujen Windows-sovellusten turvallinen käynnistys (`shell=False`)."""

import logging
import subprocess
from collections.abc import Callable, Mapping, Sequence

logger = logging.getLogger(__name__)

type PopenFunc = Callable[[Sequence[str]], object]


def _default_popen(command: Sequence[str]) -> object:
    # shell=False on pakollinen tietoturvasääntö: puheesta ei saa koskaan
    # suorittaa komentotulkin komentoja.
    return subprocess.Popen(list(command), shell=False)


class AppLauncher:
    """Käynnistää vain käyttäjän asetuksissa määritellyt sovellusaliakset."""

    def __init__(
        self,
        app_aliases: Mapping[str, Sequence[str]],
        popen_fn: PopenFunc = _default_popen,
    ) -> None:
        self._aliases: dict[str, list[str]] = {}
        self._popen = popen_fn
        self.update_aliases(app_aliases)

    def update_aliases(self, app_aliases: Mapping[str, Sequence[str]]) -> None:
        """Päivittää sallittujen sovellusaliasten taulukon."""
        cleaned: dict[str, list[str]] = {}
        for alias, cmd in app_aliases.items():
            key = alias.strip().lower()
            parts = [part for part in cmd if isinstance(part, str) and part.strip()]
            if key and parts:
                cleaned[key] = parts
        self._aliases = cleaned

    def launch(self, alias: str) -> tuple[bool, str]:
        """Käynnistää aliasta vastaavan sovelluksen.

        Returns:
            `(onnistui, suomenkielinen_palauteviesti)`
        """
        normalized = alias.strip().strip(".,!?:;\"'").lower()
        if not normalized:
            return False, "Sovelluksen nimi puuttuu."

        command = self._aliases.get(normalized)
        if not command:
            logger.warning("Tuntematon sovellusalias: %s", normalized)
            return False, f"Tuntematon sovellus: {normalized}"

        try:
            self._popen(command)
        except FileNotFoundError:
            logger.exception("Sovellustiedostoa ei löytynyt aliakselle %s: %s", normalized, command[0])
            return False, f"Sovellusta '{normalized}' ei löytynyt ({command[0]})."
        except OSError as exc:
            logger.exception("Sovelluksen '%s' käynnistys epäonnistui", normalized)
            return False, f"Sovelluksen '{normalized}' käynnistys epäonnistui ({exc})."

        logger.info("Käynnistettiin sovellus '%s' (%s)", normalized, command[0])
        return True, f"Käynnistettiin {normalized}"
