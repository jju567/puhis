"""Windowsin standardihakemistot Puhiksen asetuksille, lokeille ja välimuistille."""

import os
from pathlib import Path

APP_DIR_NAME = "puhis"
CONFIG_FILE_NAME = "config.json"


def _env_dir(variable: str, fallback: Path) -> Path:
    value = os.environ.get(variable, "").strip()
    return Path(value) if value else fallback


def get_config_dir() -> Path:
    """Palauttaa `%APPDATA%\\puhis` -hakemiston (roaming-asetukset)."""
    roaming = _env_dir("APPDATA", Path.home() / "AppData" / "Roaming")
    return roaming / APP_DIR_NAME


def get_local_data_dir() -> Path:
    """Palauttaa `%LOCALAPPDATA%\\puhis` -hakemiston (lokit, välimuisti, mallit)."""
    local = _env_dir("LOCALAPPDATA", Path.home() / "AppData" / "Local")
    return local / APP_DIR_NAME


def get_config_path() -> Path:
    """Palauttaa asetustiedoston polun."""
    return get_config_dir() / CONFIG_FILE_NAME


def get_log_dir() -> Path:
    """Palauttaa lokihakemiston polun."""
    return get_local_data_dir() / "logs"


def get_models_dir() -> Path:
    """Palauttaa Whisper-mallien paikallisen välimuistihakemiston polun."""
    return get_local_data_dir() / "models"


def ensure_dir(path: Path) -> Path:
    """Luo hakemiston tarvittaessa ja palauttaa sen."""
    path.mkdir(parents=True, exist_ok=True)
    return path
