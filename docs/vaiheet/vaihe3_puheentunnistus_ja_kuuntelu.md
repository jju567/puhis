# Vaihe 3 – Jatkuva taustakuuntelu, VAD & paikallinen Whisper-STT

**Tila:** `Suunniteltu (odottaa Vaiheen 2 valmistumista ja hyväksyntää)`  
**Ylätason suunnitelma:** [../suunnitelma.md](../suunnitelma.md)

---

## 1. Tavoite

Liitetään sovellukseen paikallinen, jatkuvasti taustalla kuunteleva puheentunnistus Intel Core 5 -prosessorille optimoituna:
- Kevyt **VAD** tunnistaa puheen alun ja lopun (~1–2 % CPU lepotilassa), jolloin Whisper aktivoituu vasta puhuttaessa.
- Paikallinen `faster-whisper` (`small`, `compute_type="int8"`) eristettynä `Transcriber`-protokollan taakse.
- Avainsanavihjeet (`initial_prompt`: `"puhis, save t1, t2, enter, tab, piste, pilkku..."`) parantamaan suomen + englanninkielisten komentojen tarkkuutta.
- Taustasäikeessä pyörivä äänikaappaus (`sounddevice`) ja säieturvallinen yhteys käyttöliittymään (Qt `Signal`) kissan tilan päivittämiseksi.
- Koko putki toimii päästä päähän: puhe → komento tai sanelu aktiiviseen ikkunaan.

---

## 2. Tiedostorakenne ja moduulit

```text
src/puhis/
├── stt/
│   ├── __init__.py
│   ├── transcriber.py          # Transcriber-Protocol + FasterWhisperTranscriber (small INT8)
│   ├── vad.py                  # Puheaktiivisuuden tunnistus ja puhejaksojen leikkaus
│   └── audio_capture.py        # sounddevice-taustasäie + queue.Queue + threading.Event
└── core/
    └── assistant_controller.py # Yhdistää STT -> CommandParser -> TextTransformer / Platform

scripts/
└── benchmark_whisper.py        # Intel Core 5 CPU -nopeus- ja viivetesti mallin varmistamiseen

tests/
├── test_vad.py                 # Hiljaisuus vs. puhe -segmentointi synteettisellä äänidatalla
└── test_assistant_controller.py# Päästä päähän -testi fake-STT:llä ja fake-Win32:lla
```

---

## 3. Windows-oikeus- ja tietoturvavaikutukset

- **Yksityisyys:** 100 % paikallinen puheentunnistus — ääntä ei lähetetä verkkoon eikä tallenneta levylle.
- **Mikrofonin tila näkyy aina:** Kissan ulkoasu kertoo selvästi, onko ohjelma mykistetty, lepotilassa (kuuntelee vain `"puhis"`-herätettä) vai sanelutilassa.
- **Ensimmäinen käynnistys:** Whisper-mallin lataus Hugging Face -välimuistiin (`%LOCALAPPDATA%\puhis\models\` tai HF cache) tapahtuu vain kerran; edistymisestä ja virheistä kerrotaan käyttäjälle selkeästi.
- **Resurssien vapautus:** Äänivirta ja taustasäikeet suljetaan hallitusti `threading.Event` + `join()` -mekanismilla.

---

## 4. Testaustapa

- **CPU-nopeustesti (`scripts/benchmark_whisper.py`):** Mitataan mallin latausaika ja 2 s / 4 s puhepätkän tunnistusviive Intel Core 5:llä.
- **Yksikkötestit (`unittest`):**
  - `test_vad.py`: hiljaisuus ei laukaise tunnistusta, puhejakso leikataan oikein tauon jälkeen.
  - `test_assistant_controller.py`: täysi reititys fake-STT:llä ja fake-Win32:lla (`"puhis save t1"`, `"puhis sanele"`, `"hei pilkku maailma enter"`, `"puhis seis"`).
- **Live-testi mikrofonilla:** Oikea puhesanelu Muistioon + `"puhis avaa laskin"` + `"puhis save t1"` + `"puhis t1"`.

---

## 5. Toteutuksen seuranta

| # | Tehtävä | Tila | Huomiot |
| :--- | :--- | :--- | :--- |
| 3.1 | Asenna `sounddevice`, `numpy`, `faster-whisper` `.venv`:iin | `[ ]` | |
| 3.2 | Toteuta `scripts/benchmark_whisper.py` ja mittaa Intel Core 5 -viive | `[ ]` | |
| 3.3 | Toteuta `stt/vad.py` ja `stt/audio_capture.py` | `[ ]` | Hallittu sammutus |
| 3.4 | Toteuta `stt/transcriber.py` (`Transcriber`-Protocol + `FasterWhisperTranscriber`) | `[ ]` | `small` INT8 + `initial_prompt` |
| 3.5 | Toteuta `core/assistant_controller.py` ja kytke Qt-signaalit kissaan | `[ ]` | |
| 3.6 | Kirjoita yksikkötestit (`test_vad.py`, `test_assistant_controller.py`) | `[ ]` | |
| 3.7 | Aja `compileall`, `unittest` ja live-mikrofonitesti | `[ ]` | |
| 3.8 | Päivitä `README.md` ja seurantataulukot | `[ ]` | |

### Hyväksymiskriteerit (Done)
- [ ] Lepotilan CPU-kuorma on matala (VAD ei laukaise Whisperiä hiljaisuudessa).
- [ ] `"puhis avaa laskin"`, `"puhis save t1"`, `"puhis sanele"` ja välimerkkien sanelu toimivat luotettavasti mikrofonilla.
- [ ] Kissan tilaindikaattori päivittyy oikein (lepo / kuuntelee / sanelee / mykistetty).
- [ ] Kaikki yksikkötestit ja syntaksitarkistukset menevät läpi.
