"""Renderöi kissan kaikissa tiloissa PNG-kuviksi ulkoasun tarkistamista varten.

Käyttö:
    .\\.venv\\Scripts\\python.exe scripts\\render_cat_preview.py --out <hakemisto> [--size 192]
"""

import argparse
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QPainter, QPixmap

from puhis.core.app_state import AssistantMode
from puhis.core.config_store import CatTheme
from puhis.ui.cat_painter import CatGeometry, paint_cat


def render(
    mode: AssistantMode,
    size: int,
    pupils: tuple[float, float],
    theme: CatTheme = CatTheme.CHARCOAL,
) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    try:
        paint_cat(painter, CatGeometry(float(size)), mode, pupils, pupils, theme=theme)
    finally:
        painter.end()
    return pixmap


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="Tulostehakemisto")
    parser.add_argument("--size", type=int, default=192, help="Kuvan koko pikseleinä")
    args = parser.parse_args()

    if not 32 <= args.size <= 1024:
        print("Virhe: --size pitää olla välillä 32–1024", file=sys.stderr)
        return 2

    app = QGuiApplication(sys.argv)  # noqa: F841 – QPixmap vaatii sovellusolion
    args.out.mkdir(parents=True, exist_ok=True)
    max_offset = CatGeometry(float(args.size)).max_pupil_offset
    for mode in AssistantMode:
        path = args.out / f"cat_{mode.value}.png"
        # Pupillit oikealle ylös, jotta katseen seuranta näkyy kuvassa.
        if not render(mode, args.size, (max_offset * 0.7, -max_offset * 0.7)).save(str(path)):
            print(f"Virhe: kuvan tallennus epäonnistui: {path}", file=sys.stderr)
            return 1
        print(f"Tallennettu: {path}")
    for theme in CatTheme:
        path = args.out / f"theme_{theme.value}.png"
        if not render(AssistantMode.IDLE, args.size, (0.0, 0.0), theme=theme).save(str(path)):
            print(f"Virhe: kuvan tallennus epäonnistui: {path}", file=sys.stderr)
            return 1
        print(f"Tallennettu: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
