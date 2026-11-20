# Ylätason suunnitelma – Puhis (Windows-ääninäppäimistö ja -avustin)

Tämä dokumentti kuvaa `puhis`-sovelluksen ylätason arkkitehtuurin, toiminnallisuudet, teknologiavaihtoehdot, Windows-reunaehdot ja vaiheistetun toteutussuunnitelman.

---

## 1. Tavoite ja ydinominaisuudet

`Puhis` on taustalla toimiva Windows-apuohjelma, jonka avulla käyttäjä voi:
1. **Sanella tekstiä aktiiviseen ikkunaan:** Puhe muunnetaan tekstiksi ja syötetään suoraan kulloinkin aktiivisena olevaan ikkunaan näppäimistösyötteenä.
2. **Käyttää välimerkkejä ja erikoisnäppäimiä avainsanoilla:** Puhutut avainsanat muunnetaan oikeiksi merkeiksi tai näppäinpainalluksiksi (esim. `"piste"` → `.`, `"pilkku"` → `,`, `"enter"` → `Enter`, `"tab"` → `Tab`, `"pyyhi"` → `Backspace`), eivätkä ne tulostu kirjaimellisena tekstinä.
3. **Ohjata Windowsia herätesanalla:** Oletusherätesana on `"puhis"` (vaihdettavissa asetuksista). Esimerkkejä:
   - `"puhis avaa laskin"` / `"puhis käynnistä laskin"` → käynnistää määritellyn sovelluksen.
   - `"puhis save t1"` → tallentaa sillä hetkellä aktiivisen ikkunan paikkaan `t1`.
   - `"puhis t1"` (tai `"puhis fokus t1"`) → tuo `t1`-ikkunan etualalle ja aktivoi sen.
   - `"puhis piilota t1"` (tai `"puhis piilota"`) → minimoi tai piilottaa kohdeikkunan.
4. **Muokata komentoja ja avainsanoja käyttöliittymästä:** Käyttäjä voi lisätä, muokata ja poistaa:
   - herätesanaa,
   - välimerkki- ja näppäinavainsanoja,
   - käynnistettävien sovellusten nimiä ja polkuja,
   - ikkuna-aliaksia (`t1`, `t2`, ...).
5. **Kelluva kissa-avustin ruudulla:**
   - Pieni, söpö, läpinäkyvä kelluva kissaikoni aina päällimmäisenä (*Always on Top*).
   - Kissan silmät seuraavat hiiren kursoria jatkuvasti.
   - Kissan ilme tai korostusväri kertoo tilan (lepotila / kuuntelee komentoa / sanelee / mikrofoni mykistetty).
   - Hiiren oikealla klikkauksella avautuu valikko ja asetussivu.
   - Kissa ei varasta ikkunafokusta aktiiviselta ohjelmalta.

---

## 2. Arkkitehtuuri ja moduulijako

Sovellus jaetaan projektin ohjeiden mukaisesti kolmeen selkeään kerrokseen (`src/`):

```text
src/
├── core/                      # Puhdas sovelluslogiikka (helposti yksikkötestattava)
│   ├── command_parser.py/cs   # Herätesanan tunnistus, komentojen jäsennys
│   ├── text_transformer.py/cs # Sanelutekstin muunnos -> teksti + näppäin-/välimerkkitapahtumat
│   ├── config_store.py/cs     # Asetusten ja avainsanojen atominen JSON-tallennus
│   └── window_registry.py/cs  # Lennossa nimetyt ikkunat (t1, t2, ...)
├── stt/                       # Äänikaappaus ja puheentunnistus
│   ├── audio_capture.py/cs    # Jatkuva mikrofonin kuuntelu taustasäikeessä
│   ├── vad.py/cs              # Puheaktiivisuuden tunnistus (Voice Activity Detection)
│   └── transcriber.py/cs      # Puhe -> teksti (rajapinta, jotta moottori on vaihdettavissa)
├── platform/                  # Windows-spesifiset rajapinnat (Win32 API)
│   ├── keyboard_injector.py/cs# Näppäinpainallusten ja Unicode-tekstin lähetys (SendInput)
│   ├── window_manager.py/cs   # Aktiivisen ikkunan haku, fokusointi, piilotus
│   ├── app_launcher.py/cs     # Sovellusten turvallinen käynnistys aliaksilla
│   └── cursor_tracker.py/cs   # Hiiren globaalin sijainnin luku (GetCursorPos)
└── ui/                        # Käyttöliittymä
    ├── cat_widget.*           # Kelluva kissaikoni, silmien animaatio, raahaus, pikavalikko
    ├── settings_window.*      # Asetusikkuna (herätesana, avainsanat, sovellukset, loki)
    └── tray_icon.*            # Windowsin ilmaisinalueen (System Tray) varakuvake
```

### Tietovirta (Pipeline)

```text
[Mikrofoni] -> [VAD (tunnistaa puheen)] -> [STT (puhe -> teksti)]
    -> [CommandParser]
        ├─ Alkaa herätesanalla ("puhis ...") -> [Windows-komento: fokus / piilota / save t1 / käynnistä / tilan vaihto]
        └─ Sanelutila aktiivinen -> [TextTransformer (välimerkit & erikoisnäppäimet)] -> [SendInput aktiiviseen ikkunaan]
```

---

## 3. Tarvittavat ohjelmistot ja teknologiavaihtoehdot

Teknologiapino kannattaa valita sen mukaan, halutaanko nopein toteutus paikallisella tekoälypuheentunnistuksella (Python) vai kevyin natiivi Windows-sovellus (C# / .NET).

### Vaihtoehto A: Python + PySide6 (Qt6) *(Suositus nopeaan kehitykseen ja STT-tukeen)*
- **Kieli & ajoaika:** Python 3.11+
- **Käyttöliittymä & kissa-widget:** `PySide6` (Qt6) – helppo toteuttaa läpinäkyvä, kehyksetön, skaalautuva (High-DPI) vektori- tai SVG-kissa, jonka silmät piirretään dynaamisesti hiiren koordinaattien mukaan.
- **Ääni & VAD:** `sounddevice` (tai `pyaudio`) + `silero-vad` / `webrtcvad`.
- **Puheentunnistus (STT):**
  - *Paikallinen:* `faster-whisper` (CTranslate2, tukee suomea erinomaisesti; erittäin nopea NVIDIA CUDA -näytönohjaimella, toimii myös CPU:lla pienemmällä mallilla).
  - *Pilvi (valinnainen rajapinta):* OpenAI Whisper API / Deepgram / Azure Speech.
- **Windows-integraatio:** `ctypes` (Win32 `SendInput`, `GetCursorPos`, `GetForegroundWindow`, `SetForegroundWindow`, `ShowWindow`) tai `pywin32`.
- **Paketointi:** `PyInstaller` tai `Nuitka` (yksittäinen asennuskansio / `.exe`).

### Vaihtoehto B: C# (.NET 8) + WPF
- **Kieli & ajoaika:** C# / .NET 8 (Windows-natiivi, pieni muistijälki, nopea käynnistys).
- **Käyttöliittymä & kissa-widget:** WPF (XAML-vektorigrafiikka kissalle, läpinäkyvä ikkuna, suora tuki Windows-teemoille ja High-DPI:lle).
- **Ääni & VAD:** `NAudio` + kevyt VAD.
- **Puheentunnistus (STT):** `Whisper.net` (C#-kääre `whisper.cpp`:lle) tai Azure/OpenAI-pilvi-API.
- **Windows-integraatio:** Suora P/Invoke (`user32.dll`, `kernel32.dll`).
- **Paketointi:** `dotnet publish` (self-contained `.exe`).

### Yhteiset kehitystyökalut
- **Git** versiohallintaan.
- **Mikrofoni** testaukseen.
- (Jos paikallinen Whisper GPU:lla) **NVIDIA CUDA Toolkit / cuDNN** tai GPU-ajurit.

---

## 4. Keskeiset Windows-tekniset yksityiskohdat ja riskit

1. **Kissa ei saa viedä fokusta (`WS_EX_NOACTIVATE`):**
   - Jos kelluva kissaikoni aktivoituu klikattaessa, puheella kirjoittaminen kohdistuisi vahingossa kissaan eikä käyttäjän editoriin. Kelluva ikkuna merkitään Windows-tyylillä `WS_EX_NOACTIVATE` + `WS_EX_TOPMOST`. Asetusikkuna sen sijaan saa normaalisti fokuksen.
2. **Hiiren seuranta kevyesti:**
   - Kissan silmien liikuttamiseen riittää kevyt ajastin (esim. 30 ms välein, ~33 FPS), joka kutsuu Win32 `GetCursorPos()`-funktiota ja laskee pupillien siirtymän kissan keskipisteen ja kursorin välisestä vektorista. Globaalia hiirikoukkua (`WH_MOUSE_LL`) ei tarvita.
3. **Ääkköset ja erikoisnäppäimet (`SendInput`):**
   - Tavallinen teksti (mukaan lukien `ä`, `ö`, `å` ja välimerkit) lähetetään `KEYEVENTF_UNICODE`-tapahtumina, jolloin näppäimistöasettelu (FI/US) ei sotke merkkejä.
   - Erikoisnäppäimet (`Enter`, `Tab`, `Backspace`, `Esc`, nuolinäppäimet, `Ctrl+Z` jne.) lähetetään virtuaalinäppäinkoodeina (`VK_*`).
4. **Ikkunoiden nimeäminen (`save t1`) ja fokusointi:**
   - Kun käyttäjä sanoo `"puhis save t1"`, tallennetaan aktiivisen ikkunan `HWND`-kahva sekä varmuudeksi prosessin nimi ja ikkunan otsikko. Jos ikkuna on suljettu, ilmoitetaan käyttäjälle siististi.
   - Windows rajoittaa `SetForegroundWindow`-kutsua taustasovelluksilta; tarvittaessa käytetään hallittua aktivointimekanismia (esim. minimoidun ikkunan palautus `SW_RESTORE` ennen fokusointia).
5. **Käyttöoikeudet (UAC / UIPI):**
   - Sovellus ajetaan normaaleilla käyttäjäoikeuksilla. Windowsin tietoturvamalli (UIPI) estää tavallista sovellusta lähettämästä näppäinpainalluksia järjestelmänvalvojana (Admin) ajettaviin ikkunoihin (esim. Admin-PowerShell). Tämä dokumentoidaan selkeästi.
6. **Tietoturva ja yksityisyys:**
   - Asetukset tallennetaan `%APPDATA%\puhis\config.json`-tiedostoon (atominen tallennus).
   - Ääntä ei tallenneta pysyvästi levylle.
   - Sovellusten käynnistys sallii vain käyttäjän asetuksissa määrittelemät sovellusaliakset (ei mielivaltaista komentorivisuoritusta puheesta).

---

## 5. Vaiheistettu toteutussuunnitelma ja kokonaisseuranta

Jokaisella vaiheella on oma yksityiskohtainen toteutussuunnitelmansa ja tehtävälistansa `docs/vaiheet/`-kansiossa. Jokainen vaihe varmistetaan käyttäjältä ennen toteutuksen aloittamista.

| Vaihe | Sisältö | Suunnitelma & seuranta | Tila |
| :--- | :--- | :--- | :--- |
| **Vaihe 1** | Projektirunko, asetukset & kelluva kissa-avustin (silmät seuraavat hiirtä, `WS_EX_NOACTIVATE`, oikea klikki, Tray) | [vaihe1_runko_ja_kissa.md](vaiheet/vaihe1_runko_ja_kissa.md) | `Valmis` |
| **Vaihe 2** | Komentotulkki, tekstinmuunnos, Win32 `SendInput`, ikkunanhallinta (`save t1`, fokus, piilotus) & sovelluskäynnistys | [vaihe2_windows_ohjaus_ja_syotto.md](vaiheet/vaihe2_windows_ohjaus_ja_syotto.md) | `Valmis` |
| **Vaihe 3** | Jatkuva taustakuuntelu (`sounddevice`), VAD & paikallinen `faster-whisper` (`small` INT8) + CPU-nopeustesti | [vaihe3_puheentunnistus_ja_kuuntelu.md](vaiheet/vaihe3_puheentunnistus_ja_kuuntelu.md) | `Suunniteltu` |
| **Vaihe 4** | Asetusikkuna (herätesana, välimerkit/näppäimet, sovellukset, ikkunat `t1`/`t2`, reaaliaikainen tapahtumaloki) | [vaihe4_asetus_ui_ja_loki.md](vaiheet/vaihe4_asetus_ui_ja_loki.md) | `Suunniteltu` |
| **Vaihe 5** | Viimeistely, moninäyttö-/mikrofonivakaus, valinnainen automaattikäynnistys & Windows `.exe`-paketointi | [vaihe5_viimeistely_ja_paketointi.md](vaiheet/vaihe5_viimeistely_ja_paketointi.md) | `Suunniteltu` |

---

## 6. Testausstrategia

- **Yksikkötestit (`tests/`):**
  - Herätesanan tunnistus (eri kirjoitusasut, iso/pieni alkukirjain, häiriöäänet).
  - Välimerkki- ja näppäinavainsanojen muunnos (`"hei pilkku maailma enter"` → teksti `"hei, maailma"` + `Enter`).
  - Ikkunarekisterin logiikka (`save t1`, ylikirjoitus, tuntematon alias).
  - Asetustiedoston lataus/tallennus eristetyssä väliaikaishakemistossa.
- **Manuaalinen integraatiotestaus Windowsilla:**
  - Kirjoitus Muistioon, selaimeen ja koodieditoriin ääkkösillä.
  - Ikkunan tallennus (`save t1`), vaihto ja piilotus.
  - Kissan silmien seuranta usealla näytöllä ja eri DPI-skaalauksilla.

---

## 7. Lukitut päätökset (20.11.2026)

1. **Puheentunnistus (STT):** Paikallinen offline-malli ensisijaisena (`faster-whisper` `small` INT8 + kevyt VAD), eristettynä `Transcriber`-rajapinnan taakse mahdollista pilvi-/selainlaajennusta varten.
2. **Sanelutilan toimintalogiikka:** Herätesana + tilakytkin. Oletuksena ohjelma reagoi vain herätesanalla alkaviin komentoihin (`"puhis ..."`). Sanelu kytketään päälle/pois komennolla (`"puhis sanele"` / `"puhis seis"`) tai kissaa klikkaamalla.
3. **Teknologiapino:** Python 3.13 + `PySide6` (Qt6) + Win32 API (`ctypes`).
4. **Kohdelaitteisto:** Intel Core 5 (pelkkä CPU, ei NVIDIA GPU:ta) → optimoidaan `INT8`-kvantisoinnilla, VAD-suodatuksella ja avainsanavihjeillä (`initial_prompt`).
5. **Kielituki:** Suomi pääkielenä + englanninkieliset avainsanat (`enter`, `tab`, `save t1`).
