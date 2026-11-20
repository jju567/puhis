"""Puhiksen käynnistyspiste: `python -m puhis`."""

import logging
import sys
from logging.handlers import RotatingFileHandler
from types import TracebackType

from PySide6.QtWidgets import QApplication

from puhis import __version__
from puhis.core.config_store import ConfigStore
from puhis.platform.paths import ensure_dir, get_config_path, get_log_dir
from puhis.ui.app_controller import AppController

logger = logging.getLogger("puhis")

LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
LOG_MAX_BYTES = 1_000_000
LOG_BACKUP_COUNT = 3


def configure_logging() -> None:
    """Lokittaa konsoliin ja `%LOCALAPPDATA%\\puhis\\logs\\puhis.log`-tiedostoon."""
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    try:
        log_file = ensure_dir(get_log_dir()) / "puhis.log"
        handlers.append(
            RotatingFileHandler(
                log_file, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT, encoding="utf-8"
            )
        )
    except OSError as exc:
        # Sovelluksen pitää käynnistyä, vaikka lokihakemistoa ei voisi luoda.
        print(f"puhis: lokitiedostoa ei voitu avata ({exc})", file=sys.stderr)
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, handlers=handlers)
    logging.getLogger("faster_whisper").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpx2").setLevel(logging.WARNING)


def _log_uncaught(
    exc_type: type[BaseException], exc: BaseException, tb: TracebackType | None
) -> None:
    logger.critical("Käsittelemätön virhe", exc_info=(exc_type, exc, tb))


def main() -> int:
    configure_logging()
    sys.excepthook = _log_uncaught
    logger.info("puhis %s käynnistyy", __version__)

    app = QApplication(sys.argv)
    app.setApplicationName("Puhis")
    app.setApplicationVersion(__version__)
    # Kissa on Tool-ikkuna, joten sovellus ei saa sulkeutua sen piilottamisesta.
    app.setQuitOnLastWindowClosed(False)

    controller = AppController(app, ConfigStore(get_config_path()))
    controller.start()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
