# Puhis – Windows-ääninäppäimistö ja -avustin

Paikallisella puheentunnistuksella toimiva Windows-apuohjelma, jolla voit sanella tekstiä (välimerkit ja erikoisnäppäimet avainsanoina) aktiiviseen ikkunaan sekä ohjata Windowsia herätesanalla (`"puhis"`). Ruudulla kelluu söpö kissa-avustin, jonka silmät seuraavat hiirtä ja josta avautuvat asetukset hiiren oikealla klikkauksella.

---

## Teknologiapino

- **Kieli:** Python 3.13+
- **Käyttöliittymä:** `PySide6` (Qt6)
- **Puheentunnistus (lennossa vaihdettava):**
  - 🌐 **Selaintunnistus (`GoogleWebSpeechTranscriber`, `fi-FI`, oletus)** – sama nopea ja tarkka suomen puhekielen tunnistus kuin Chrome-selaimen Web Speech API:ssa (`SpeechRecognition`).
  - 💻 **Paikallinen (`FasterWhisperTranscriber`, `small` INT8)** – 100 % offline CPU-tunnistus.
  - **Äänikaappaus:** `sounddevice` + adaptiivinen VAD esipuskurilla.
- **Windows-integraatio:** Win32 API (`ctypes`: `SendInput`, `GetForegroundWindow`, `SetForegroundWindow`, `ShowWindow`)

---

## Projektin rakenne

- `AGENTS.md` – Agenttien ja kehityksen pääohjeet sekä työnkulku.
- `docs/ohjelmointiohjeet.md` – Yleiset ohjelmointi- ja Windows-kehitysohjeet.
- `docs/suunnitelma.md` – Ylätason arkkitehtuuri- ja toteutussuunnitelma.
- `src/puhis/` – Varsinainen lähdekoodi:
  - `core/` – Ydinlogiikka (`actions.py`, `app_state.py`, `command_parser.py`, `config_store.py`, `eye_math.py`, `text_transformer.py`, `utterance_router.py`, `window_registry.py`)
  - `platform/` – Windows-rajapinnat (`keyboard_injector.py`, `window_manager.py`, `app_launcher.py`, `win32_window.py`, `paths.py`)
  - `stt/` – Äänikaappaus, VAD ja puheentunnistus (`vad.py`, `transcriber.py`, `audio_capture.py`)
  - `ui/` – Kelluva kissa-widget, ohjain ja System Tray -kuvake (`cat_widget.py`, `cat_painter.py`, `app_controller.py`, `app_menu.py`, `tray_icon.py`)
- `tests/` – Yksikkötestit (`unittest`).
- `scripts/` – Apu- ja testiskriptit (`render_cat_preview.py`, `test_win32_actions.py`, `benchmark_whisper.py`).

---

## Kehitysympäristön pystytys

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -e . --no-deps
```

### Käynnistys

```powershell
.\.venv\Scripts\python.exe -m puhis
```

> Ensimmäisellä puhejaksolla `faster-whisper` lataa `small`-mallin paikalliseen välimuistiin (`%LOCALAPPDATA%\puhis\models\`).

### Nykyiset ominaisuudet (Vaiheet 1–3)

- **Kelluva kissa** (`src/puhis/ui/cat_widget.py`, `cat_painter.py`): aina päällimmäisenä, ei näy tehtäväpalkissa eikä vie fokusta aktiiviselta ikkunalta (`WS_EX_NOACTIVATE`). Silmät seuraavat hiirtä ja räpäyttävät luonnollisesti.
- **Hiiri:** vasen klikki = sanelu päälle/pois, raahaus = siirto (sijainti muistetaan), oikea klikki = valikko (sis. väriteeman vaihto: *Hiili*, *Oranssi*, *Kerma*).
- **Tilat:** lepo (harmaa kehä), sanelu (vihreä sykkivä kehä + hymy), komento (sinivioletti kehä), mykistetty (silmät kiinni + `zZ`), virhe (oranssinpunainen kehä, suupielet alaspäin ja `!`).
- **Ilmaisinalue (Tray):** sama valikko; klikkaus näyttää/piilottaa kissan.
- **Jatkuva taustakuuntelu ja paikallinen puheentunnistus** (`src/puhis/stt/`):
  - Kevyt energiapohjainen VAD (`vad.py`) esipuskurilla leikkaa puhejaksot hiljaisuuksien välistä.
  - Paikallinen `faster-whisper` (`small`, `int8`, `transcriber.py`) muuntaa puheen tekstiksi ilman pilviyhteyttä.
- **Herätesana ja komentotulkki** (`src/puhis/core/command_parser.py`, `utterance_router.py`):
  - Tilan vaihto: `"puhis sanele"`, `"puhis seis"`, `"puhis mykistä"`.
  - Ikkunoiden nimeäminen ja ohjaus: `"puhis save t1"`, `"puhis t1"` / `"puhis fokus t1"`, `"puhis piilota t1"`, `"puhis piilota"`.
  - Valkolistattujen sovellusten käynnistys (`shell=False`): `"puhis avaa laskin"`, `"puhis käynnistä muistio"`.
- **Tekstin- ja näppäinmuunnos** (`src/puhis/core/text_transformer.py`, `platform/keyboard_injector.py`):
  - Muuntaa välimerkki- ja näppäinavainsanat (`piste`, `pilkku`, `kysymysmerkki`, `huutomerkki`, `kaksoispiste`, `puolipiste`, `enter`, `rivinvaihto`, `tab`, `pyyhi`) `TextAction`- ja `KeyAction`-tapahtumiksi ja syöttää ne Win32 `SendInput`-rajapinnalla (`KEYEVENTF_UNICODE` + `VK_*`).
  - **Huomio Windowsin käyttöoikeuksista (UIPI):** Puhis ajetaan tavallisilla käyttäjäoikeuksilla, joten Windows estää `SendInput`-syötön järjestelmänvalvojana (Admin) ajettaviin ikkunoihin.
- **Asetukset ja tallennussijainnit:**
  - Asetukset: `%APPDATA%\puhis\config.json` (asetusikkuna tulee vaiheessa 4).
  - Loki: `%LOCALAPPDATA%\puhis\logs\puhis.log`.
  - Whisper-mallit: `%LOCALAPPDATA%\puhis\models\`.

### Apuskriptit

```powershell
# Kissan esikatselukuvat:
.\.venv\Scripts\python.exe scripts\render_cat_preview.py --out <hakemisto>

# Vaiheen 2 komentoketjun kuiva-ajo / live-testi:
.\.venv\Scripts\python.exe scripts\test_win32_actions.py --dry-run
.\.venv\Scripts\python.exe scripts\test_win32_actions.py --live

# Vaiheen 3 Whisper CPU -nopeustesti (kuiva-ajo tai oikea small INT8 -malli):
.\.venv\Scripts\python.exe scripts\benchmark_whisper.py --dry-run
.\.venv\Scripts\python.exe scripts\benchmark_whisper.py
```

### Testit ja tarkistukset

```powershell
.\.venv\Scripts\python.exe -m compileall -q src tests scripts
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```
