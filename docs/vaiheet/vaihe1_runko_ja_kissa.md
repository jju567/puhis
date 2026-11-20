# Vaihe 1 – Projektirunko, asetukset & kelluva kissa-avustin

**Tila:** `Toteutettu – odottaa käyttäjän manuaalista testausta`  
**Ylätason suunnitelma:** [../suunnitelma.md](../suunnitelma.md)

---

## 1. Tavoite

Pystytetään toimiva Python 3.13 + PySide6 -kehitysympäristö ja toteutetaan sovelluksen näkyvä perusta:
- Pieni, söpö, läpinäkyvä kelluva hiilenharmaa vektorikissa (*Always on Top*, `QPainter`-vektorigrafiikka, oletuskoko ~84×84 px, High-DPI-skaalautuva).
- Kissan silmät seuraavat hiiren kursoria jatkuvasti (~30 FPS) ja räpäyttävät satunnaisesti 4–7 s välein.
- Kissa **ei varasta fokusta** aktiiviselta ikkunalta (`WS_EX_NOACTIVATE`).
- Selkeät visuaaliset tilat ja ympäröivä tilarengas (halo):
  - **Lepo (`IDLE`):** valpas ilme, hento harmaa rengas.
  - **Sanelu (`DICTATING`):** iloinen ilme, smaragdinvihreä sykkivä rengas + puhekuplapalaute (`"Sanelu päällä"`).
  - **Komento (`COMMAND`):** sähkönsininen/violetti hehku + puhekuplapalaute (esim. `"→ Laskin"`).
  - **Mykistetty (`MUTED`):** nukkuva kissa (suljetut silmät + `zZz`), himmeä rengas.
  - **Virhe (`ERROR`):** oranssi/punainen rengas + tooltip.
- Pieni läpiklikattava puhekuplapalaute (*toast*) kissan yläpuolella komentojen kuittaukseksi (1,5–2 s).
- Kissa on siirrettävissä raahaamalla, vasen klikki vaihtaa tilan (lepo / sanelu), ja hiiren oikealla avautuu pikavalikko (mm. "Asetukset (tulossa)", "Mykistä", "Näytä/Piilota", "Sulje").
- System Tray -kuvake varalla, jos kissa piilotetaan.
- Asetusten atominen tallennus `%APPDATA%\puhis\config.json` (herätesana `"puhis"`, kissan sijainti, teemaväri, oletusavainsanat).

---

## 2. Tiedostorakenne ja moduulit

```text
src/puhis/
├── __init__.py
├── __main__.py                 # Sovelluksen käynnistyspiste & logging-alustus
├── core/
│   ├── __init__.py
│   ├── app_state.py            # AssistantMode-Enum (IDLE, DICTATING, COMMAND, MUTED, ERROR)
│   ├── config_store.py         # AppConfig-dataclass + atominen JSON-lataus/tallennus
│   └── eye_math.py             # Puhdas matematiikka pupillien sijainnille (helposti testattava)
├── platform/
│   ├── __init__.py
│   ├── paths.py                # %APPDATA%\puhis ja %LOCALAPPDATA%\puhis -polut
│   └── win32_window.py         # WS_EX_NOACTIVATE -tyylin asetus & GetCursorPos (ctypes)
└── ui/
    ├── __init__.py
    ├── cat_widget.py           # Kelluva kissa-widget (QPainter-vektorigrafiikka, silmät, halo, toast, raahaus, menu)
    └── tray_icon.py            # Windows System Tray -kuvake ja pikavalikko

tests/
├── test_config_store.py        # Atominen tallennus, oletusarvot, korruptoitunut JSON (TemporaryDirectory)
└── test_eye_math.py            # Pupillivektorin laskenta eri suunnissa, nollaetäisyys, maksimisäde
```

---

## 3. Windows-oikeus- ja tietoturvavaikutukset

- Ei vaadi järjestelmänvalvojan (Admin/UAC) oikeuksia.
- Ei verkkoliikennettä tai mikrofonin käyttöä vielä tässä vaiheessa.
- Asetukset tallennetaan vain `%APPDATA%\puhis\config.json` -tiedostoon (atominen `os.replace()`).
- `GetCursorPos` ja `SetWindowLongPtrW` (`WS_EX_NOACTIVATE`) käytetään turvallisesti `ctypes`:llä eksplisiittisillä `argtypes`/`restype`-määrityksillä.

---

## 4. Testaustapa

- **Yksikkötestit (`unittest`):**
  - `test_config_store.py`: oletusasetusten luonti, tallennus ja uudelleenlataus väliaikaishakemistossa, korruptoituneen tiedoston siisti käsittely.
  - `test_eye_math.py`: pupillien rajoittuminen silmän sisälle, suunnat (ylös/alas/vasen/oikea/keskellä).
- **Manuaalinen savutesti Windowsilla:**
  - Kissa ilmestyy ruudulle ilman ikkunakehyksiä ja pysyy muiden ikkunoiden päällä.
  - Avaa Muistio, klikkaa kissaa → fokus pysyy Muistiossa.
  - Liikuta hiirtä ruudun eri laitoihin → kissan silmät seuraavat sujuvasti.
  - Raahaa kissa uuteen paikkaan, sulje ja avaa uudelleen → sijainti muistetaan.
  - Hiiren oikea klikki avaa pikavalikon, "Sulje" sammuttaa prosessin puhtaasti.

---

## 5. Toteutuksen seuranta

| # | Tehtävä | Tila | Huomiot |
| :--- | :--- | :--- | :--- |
| 1.1 | Luo `.venv` ja asenna `PySide6` (`pip install -e .`) | `[x]` | PySide6 6.12.0, puhis editable (`--no-deps`, Whisper asennetaan vaiheessa 3) |
| 1.2 | Toteuta `core/app_state.py` ja `core/eye_math.py` | `[x]` | Tilasiirtymät `toggle_dictation` / `toggle_mute` |
| 1.3 | Toteuta `platform/paths.py` ja `core/config_store.py` | `[x]` | Atominen tallennus, viallinen tiedosto → `.corrupt`-varmuuskopio |
| 1.4 | Toteuta `platform/win32_window.py` (`WS_EX_NOACTIVATE`) | `[x]` | Ks. poikkeama 1 |
| 1.5 | Toteuta kissa (`ui/cat_painter.py` + `ui/cat_widget.py`) | `[x]` | Ks. poikkeama 2 |
| 1.6 | Toteuta `ui/tray_icon.py`, `ui/app_menu.py`, `ui/app_controller.py` ja `__main__.py` | `[x]` | Sama valikko kissalla ja Traylla |
| 1.7 | Kirjoita yksikkötestit | `[x]` | 23 testiä: config_store, eye_math, app_state, paths |
| 1.8 | Aja `compileall`, `unittest` ja savutesti | `[~]` | Automaattiset OK; käyttäjän manuaalinen testi kesken |
| 1.9 | Päivitä `README.md` ja seurantataulukot | `[x]` | |

### Poikkeamat suunnitelmasta
1. **Kursorin sijainti luetaan `QCursor.pos()`-funktiolla eikä Win32 `GetCursorPos`-kutsulla.** Syy: `GetCursorPos` palauttaa fyysiset pikselit, kun taas Qt-ikkunan koordinaatit ovat loogisia. High-DPI-näytöillä (125 %/150 %) sekoittaminen vääristäisi katseen suunnan. `QCursor.pos()` toimii globaalisti myös ilman fokusta.
2. **Kissan piirto eriytettiin omaan `ui/cat_painter.py`-moduuliinsa** (tiedostokoko ja uudelleenkäyttö Tray-ikonissa ja esikatseluskriptissä).
3. **Lisätty:** `ui/app_menu.py`, `ui/app_controller.py`, `tests/test_app_state.py`, `tests/test_paths.py` ja `scripts/render_cat_preview.py`.

### Ajetut tarkistukset (20.11.2026)
- `compileall` – OK
- `unittest` – 23/23 OK
- Offscreen-savutesti (eristetty `%APPDATA%`): käynnistys, tilan vaihto, asetusten tallennus ja hallittu sulkeminen – OK
- Oikea Windows-ikkuna (eristetty `%APPDATA%`): `WS_EX_NOACTIVATE`, `WS_EX_TOPMOST` ja `WS_EX_TOOLWINDOW` asettuivat, Tray käytettävissä – OK
- **Ei vielä testattu (vaatii käyttäjän):** fokuksen säilyminen Muistiossa kissaa klikattaessa, silmien seuranta silmämääräisesti, raahaus, oikea klikki, eri DPI-skaalaukset.

### Hyväksymiskriteerit (Done)
- [x] `compileall` ja kaikki `unittest`-testit menevät läpi ilman virheitä.
- [ ] Kissa kelluu päällimmäisenä, silmät seuraavat hiirtä, fokus ei karkaa Muistiosta ja oikea klikki avaa valikon. *(käyttäjän testi)*
- [x] Sovellus sammuu puhtaasti ilman taustalle jäävää prosessia.
