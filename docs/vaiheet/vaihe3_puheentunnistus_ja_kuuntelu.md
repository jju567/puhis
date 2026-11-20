# Vaihe 3 – Jatkuva taustakuuntelu, VAD & paikallinen Whisper-STT

**Tila:** `Toteutettu – odottaa käyttäjän mikrofoni- ja CPU-testiä`  
**Ylätason suunnitelma:** [../suunnitelma.md](../suunnitelma.md)

---

## 1. Tavoite

Liitetään sovellukseen paikallinen, jatkuvasti taustalla kuunteleva puheentunnistus Intel Core 5 -prosessorille optimoituna:
- Kevyt **VAD** tunnistaa puheen alun ja lopun (~1–2 % CPU lepotilassa), jolloin Whisper aktivoituu vasta puhuttaessa.
- Paikallinen `faster-whisper` (`small`, `compute_type="int8"`) eristettynä `TranscriberProtocol`-protokollan taakse.
- Avainsanavihjeet (`initial_prompt`: `"puhis, save t1, t2, enter, tab, piste, pilkku..."`) parantamaan suomen + englanninkielisten komentojen tarkkuutta.
- Taustasäikeessä pyörivä äänikaappaus (`sounddevice`) ja säieturvallinen yhteys käyttöliittymään (Qt `Signal`) kissan tilan päivittämiseksi.
- Koko putki toimii päästä päähän: puhe → komento tai sanelu aktiiviseen ikkunaan.

---

## 2. Tiedostorakenne ja moduulit

```text
src/puhis/
├── stt/
│   ├── __init__.py
│   ├── transcriber.py          # TranscriberProtocol + FasterWhisperTranscriber (small INT8)
│   ├── vad.py                  # Puheaktiivisuuden tunnistus ja puhejaksojen leikkaus
│   └── audio_capture.py        # sounddevice-taustasäie + queue.Queue + threading.Event
└── ui/
    └── app_controller.py       # Yhdistää AudioListener -> Qt Signal -> UtteranceRouter -> CatWidget

scripts/
└── benchmark_whisper.py        # Intel Core 5 CPU -nopeus- ja viivetesti mallin varmistamiseen

tests/
├── test_vad.py                 # Hiljaisuus vs. puhe -segmentointi synteettisellä äänidatalla
├── test_transcriber.py         # initial_prompt ja FasterWhisperTranscriber mockatulla mallilla
└── test_audio_capture.py       # Taustasäikeen puhejaksojen välitys, mykistys ja siisti sammutus
```

---

## 3. Windows-oikeus- ja tietoturvavaikutukset

- **Yksityisyys:** 100 % paikallinen puheentunnistus — ääntä ei lähetetä verkkoon eikä tallenneta levylle.
- **Mikrofonin tila näkyy aina:** Kissan ulkoasu kertoo selvästi, onko ohjelma mykistetty, lepotilassa (kuuntelee vain `"puhis"`-herätettä) vai sanelutilassa.
- **Ensimmäinen käynnistys:** Whisper-mallin lataus paikalliseen välimuistiin (`%LOCALAPPDATA%\puhis\models\`) tapahtuu vain kerran.
- **Resurssien vapautus:** Äänivirta ja taustasäikeet suljetaan hallitusti `threading.Event` + `join(timeout=2.0)` -mekanismilla.

---

## 4. Testaustapa

- **CPU-nopeustesti (`scripts/benchmark_whisper.py`):** Mittaa mallin latausajan ja 2 s / 4 s puhepätkän tunnistusviiveen.
- **Yksikkötestit (`unittest`):**
  - `test_vad.py`: hiljaisuus ei laukaise tunnistusta, puhejakso leikataan oikein esipuskurin ja tauon kanssa.
  - `test_transcriber.py`: `build_initial_prompt` ja `FasterWhisperTranscriber` eristettynä.
  - `test_audio_capture.py`: taustasäikeen elinkaari, mykistystila ja virheenkäsittely.
- **Live-testi mikrofonilla:** Oikea puhesanelu Muistioon + `"puhis avaa laskin"` + `"puhis save t1"` + `"puhis t1"`.

---

## 5. Toteutuksen seuranta

| # | Tehtävä | Tila | Huomiot |
| :--- | :--- | :--- | :--- |
| 3.1 | Asenna `sounddevice`, `numpy`, `faster-whisper` `.venv`:iin | `[x]` | `sounddevice 0.5.6`, `numpy 2.5.5`, `faster-whisper 1.2.1` |
| 3.2 | Toteuta `scripts/benchmark_whisper.py` | `[x]` | Tukee `--dry-run`- ja oikeaa mallitestiä |
| 3.3 | Toteuta `stt/vad.py` ja `stt/audio_capture.py` | `[x]` | Hallittu sammutus + esipuskuri |
| 3.4 | Toteuta `stt/transcriber.py` (`TranscriberProtocol` + `FasterWhisperTranscriber`) | `[x]` | `small` INT8 + `initial_prompt` |
| 3.5 | Kytke `AudioListener` ja `UtteranceRouter` Qt-signaaleilla `AppController`iin | `[x]` | Säieturvallinen `Signal(str)` |
| 3.6 | Kirjoita yksikkötestit (`test_vad.py`, `test_transcriber.py`, `test_audio_capture.py`) | `[x]` | Yhteensä 72 yksikkötestiä |
| 3.7 | Aja `compileall`, `unittest` ja live-mikrofonitesti | `[~]` | Automaattiset testit (72/72) OK; live-mikrofoni käyttäjän testattavana |
| 3.8 | Päivitä `README.md` ja seurantataulukot | `[x]` | |

### Hyväksymiskriteerit (Done)
- [x] Lepotilan CPU-kuorma on matala (VAD ei laukaise Whisperiä hiljaisuudessa).
- [ ] `"puhis avaa laskin"`, `"puhis save t1"`, `"puhis sanele"` ja välimerkkien sanelu toimivat luotettavasti mikrofonilla.
- [x] Kissan tilaindikaattori päivittyy oikein (lepo / komento / sanelee / mykistetty / virhe).
- [x] Kaikki yksikkötestit (72/72) ja syntaksitarkistukset menevät läpi.
