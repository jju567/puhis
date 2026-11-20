# Puhis – Windows-ääninäppäimistö ja -avustin

Paikallisella puheentunnistuksella toimiva Windows-apuohjelma, jolla voit sanella tekstiä (välimerkit ja erikoisnäppäimet avainsanoina) aktiiviseen ikkunaan sekä ohjata Windowsia herätesanalla (`"puhis"`). Ruudulla kelluu söpö kissa-avustin, jonka silmät seuraavat hiirtä ja josta avautuvat asetukset hiiren oikealla klikkauksella.

---

## Teknologiapino

- **Kieli:** Python 3.13+
- **Käyttöliittymä:** `PySide6` (Qt6)
- **Puheentunnistus (paikallinen):** `faster-whisper` (`small`, INT8 CPU-optimointi) + `sounddevice` + VAD
- **Windows-integraatio:** Win32 API (`ctypes`: `SendInput`, `GetCursorPos`, `GetForegroundWindow`, `SetForegroundWindow`, `ShowWindow`)

---

## Projektin rakenne

- `AGENTS.md` – Agenttien ja kehityksen pääohjeet sekä työnkulku.
- `docs/ohjelmointiohjeet.md` – Yleiset ohjelmointi- ja Windows-kehitysohjeet.
- `docs/suunnitelma.md` – Ylätason arkkitehtuuri- ja toteutussuunnitelma.
- `src/puhis/` – Varsinainen lähdekoodi:
  - `core/` – Ydinlogiikka (asetukset, komentotulkki, tekstinmuunnos, ikkunarekisteri)
  - `platform/` – Windows-rajapinnat (näppäinsyöttö, ikkunanhallinta, sovelluskäynnistys, kursoriseuranta)
  - `stt/` – Äänikaappaus, VAD ja puheentunnistus
  - `ui/` – Kelluva kissa-widget, asetusikkuna ja System Tray -kuvake
- `tests/` – Yksikkötestit.
- `scripts/` – Apu- ja testiskriptit (mm. CPU-nopeustesti).

---

## Kehitysympäristön pystytys

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install "PySide6>=6.7.0"
.\.venv\Scripts\python.exe -m pip install -e . --no-deps
```

> Puheentunnistuksen riippuvuudet (`faster-whisper`, `sounddevice`, `numpy`) asennetaan vaiheessa 3: `pip install -r requirements.txt`.

### Käynnistys

```powershell
.\.venv\Scripts\python.exe -m puhis
```

### Nykyiset ominaisuudet (Vaihe 1)

- **Kelluva kissa** (`src/puhis/ui/cat_widget.py`, `cat_painter.py`): aina päällimmäisenä, ei näy tehtäväpalkissa eikä vie fokusta aktiiviselta ikkunalta (`WS_EX_NOACTIVATE`). Silmät seuraavat hiirtä ja räpäyttävät luonnollisesti.
- **Hiiri:** vasen klikki = sanelu päälle/pois, raahaus = siirto (sijainti muistetaan), oikea klikki = valikko (sis. väriteeman vaihto: *Hiili*, *Oranssi*, *Kerma*).
- **Tilat:** lepo (harmaa kehä), sanelu (vihreä sykkivä kehä + hymy), komento (sinivioletti kehä), mykistetty (silmät kiinni + `zZ`), virhe (oranssinpunainen kehä, suupielet alaspäin ja `!`).
- **Ilmaisinalue (Tray):** sama valikko; klikkaus näyttää/piilottaa kissan.
- **Asetukset:** `%APPDATA%\puhis\config.json` (herätesana, kissan koko/sijainti, aloitustila, avainsanat, sovellusaliakset). Asetusikkuna tulee vaiheessa 4.
- **Loki:** `%LOCALAPPDATA%\puhis\logs\puhis.log`.

### Kissan esikatselukuvat

```powershell
.\.venv\Scripts\python.exe scripts\render_cat_preview.py --out <hakemisto>
```

### Testit ja tarkistukset

```powershell
.\.venv\Scripts\python.exe -m compileall -q src tests scripts
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```
