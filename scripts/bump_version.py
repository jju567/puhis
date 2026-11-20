"""Kasvattaa Puhiksen versionumeroa (patch/build) synkronoidusti `__init__.py`- ja `pyproject.toml`-tiedostoissa.

Käyttö:
    .\\.venv\\Scripts\\python.exe scripts\\bump_version.py
"""

from pathlib import Path
import re
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
INIT_PATH = ROOT_DIR / "src" / "puhis" / "__init__.py"
PYPROJECT_PATH = ROOT_DIR / "pyproject.toml"

_INIT_PATTERN = re.compile(r'(__version__\s*=\s*")(\d+)\.(\d+)\.(\d+)(")')
_PYPROJECT_PATTERN = re.compile(r'(^version\s*=\s*")(\d+)\.(\d+)\.(\d+)(")', re.MULTILINE)


def bump_patch_version() -> str:
    """Kasvattaa patch-versionumeroa yhdellä ja päivittää molemmat tiedostot."""
    init_text = INIT_PATH.read_text(encoding="utf-8")
    match = _INIT_PATTERN.search(init_text)
    if match is None:
        raise ValueError(f"Versionumeroa ei löytynyt tiedostosta {INIT_PATH}")

    major, minor, patch = int(match.group(2)), int(match.group(3)), int(match.group(4))
    new_version = f"{major}.{minor}.{patch + 1}"

    new_init = _INIT_PATTERN.sub(rf"\g<1>{new_version}\g<5>", init_text, count=1)
    INIT_PATH.write_text(new_init, encoding="utf-8")

    pyproject_text = PYPROJECT_PATH.read_text(encoding="utf-8")
    new_pyproject = _PYPROJECT_PATTERN.sub(rf"\g<1>{new_version}\g<5>", pyproject_text, count=1)
    PYPROJECT_PATH.write_text(new_pyproject, encoding="utf-8")

    return new_version


def main() -> int:
    new_version = bump_patch_version()
    print(f"Puhis-versio päivitetty: {new_version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
