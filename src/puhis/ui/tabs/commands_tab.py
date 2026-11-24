"""Yhteenvetovälilehti Puhiksen sisäänrakennetuista puhekomennoista."""

from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from puhis.core.config_store import DEFAULT_WAKE_WORD


def build_builtin_commands(wake_word: str) -> list[tuple[str, str, str]]:
    """Palauttaa listan `(komento, vaihtoehdot, kuvaus)` aktiivisella herätesanalla."""
    w = wake_word.strip() or DEFAULT_WAKE_WORD
    return [
        (
            f"{w}",
            "(pelkkä herätesana)",
            "Herättää kissan kuuntelemaan seuraavaa komentoa ilman herätesanaa.",
        ),
        (
            f"{w} sanele",
            f"{w} kirjoita, {w} aloita sanelu, {w} sanelu päälle",
            "Kytkee jatkuvan sanelutilan päälle (kirjoittaa puheen aktiiviseen ikkunaan).",
        ),
        (
            f"{w} seis",
            f"{w} lopeta, {w} stop, {w} lopeta sanelu, {w} sanelu pois",
            "Lopettaa sanelutilan ja palaa lepotilaan.",
        ),
        (
            f"{w} mykistä",
            f"{w} hiljaa",
            "Mykistää mikrofonin ja pysäyttää kuuntelun väliaikaisesti.",
        ),
        (
            f"{w} save t1",
            f"{w} tallenna <alias>, {w} seivaa <alias>",
            "Tallentaa aktiivisen ikkunan annetulle aliakselle (esim. t1, t2 tai oma nimi).",
        ),
        (
            f"{w} fokus t1",
            f"{w} focus t1, {w} aktivoi t1, {w} näytä t1, {w} avaa t1, {w} t1",
            "Tuo tallennetun ikkunan etualalle ja aktivoi sen.",
        ),
        (
            f"{w} piilota [t1]",
            f"{w} minimoi [t1]",
            "Pienentää tallennetun ikkunan (tai ilman aliasta nykyisen aktiivisen ikkunan).",
        ),
        (
            f"{w} avaa <sovellus>",
            f"{w} käynnistä <sovellus>, tai pelkkä {w} <sovellus>",
            "Käynnistää sallitun sovelluksen (ks. Sallitut sovellukset) ja kytkee sanelun päälle.",
        ),
    ]


class CommandsTab(QWidget):
    """Välilehti, joka listaa kaikki sisäänrakennetut puhekomennot."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setSpacing(10)

        info = QLabel(
            "Alla on lueteltu kaikki Puhiksen sisäänrakennetut puhekomennot ja niiden "
            "rinnakkaismuodot. Jos herätesana sanotaan ensin yksinään, seuraavan komennon "
            "voi sanoa hetken ajan myös ilman herätesanaa.",
            self,
        )
        info.setWordWrap(True)
        root.addWidget(info)

        self.table = QTableWidget(0, 3, self)
        self.table.setHorizontalHeaderLabels([
            "Puhekomento",
            "Vaihtoehtoiset muodot",
            "Toiminto",
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setWordWrap(True)
        root.addWidget(self.table, stretch=1)

        hint = QLabel(
            "Vinkki: Sanelutilassa toimivat erikoissanat ja näppäimet löytyvät "
            "'Omat avainsanat & näppäimet' -välilehdeltä ja käynnistettävät ohjelmat "
            "'Sallitut sovellukset' -välilehdeltä.",
            self,
        )
        hint.setWordWrap(True)
        root.addWidget(hint)

        self.set_wake_word(DEFAULT_WAKE_WORD)

    def set_wake_word(self, wake_word: str) -> None:
        """Päivittää komentotaulukon käyttämään annettua herätesanaa."""
        rows = build_builtin_commands(wake_word)
        self.table.setRowCount(0)
        for cmd, variants, desc in rows:
            row_idx = self.table.rowCount()
            self.table.insertRow(row_idx)
            self.table.setItem(row_idx, 0, QTableWidgetItem(cmd))
            self.table.setItem(row_idx, 1, QTableWidgetItem(variants))
            self.table.setItem(row_idx, 2, QTableWidgetItem(desc))
        self.table.resizeRowsToContents()
