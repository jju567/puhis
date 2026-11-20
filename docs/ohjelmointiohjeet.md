# Ohjelmointiohjeet – Python 3.13, PySide6 & Windows (`puhis`)

Tämä dokumentti määrittelee `puhis`-projektin Python-parhaat käytännöt, koodihygienian, arkkitehtuurisäännöt, Windows-käytännöt sekä yksikkötestauksen (`unittest`) vaatimukset.

---

## 1. Arkkitehtuuri ja pakettirakenne

Koodi sijoitetaan `src/puhis/`-pakettiin ja jaetaan selkeisiin vastuualueisiin:

```text
src/puhis/
├── __main__.py        # Sovelluksen käynnistyspiste (python -m puhis)
├── core/              # Puhdas sovelluslogiikka (EI PySide6- tai Win32-riippuvuuksia)
├── stt/               # Äänikaappaus, VAD ja puheentunnistus (Transcriber-protokolla)
├── platform/          # Windows-spesifiset rajapinnat (Win32 ctypes, SendInput, ikkunat)
└── ui/                # PySide6 (Qt6) -käyttöliittymä (kissa-widget, asetukset, tray)
```

- **Kerroserottelu:** `core/` ei saa koskaan importata `PySide6`- tai `platform/`-moduuleja. Näin koko ydinlogiikka on deterministisesti ja nopeasti yksikkötestattavissa ilman GUI:ta tai Windows-ikkunoita.
- **Riippuvuuksien injektointi:** Välitä palvelut ja asetukset konstruktoreiden kautta (`__init__`) globaalien muuttujien tai singletonien sijaan.
- **Rajapinnat (`Protocol`):** Eristä vaihdettavat komponentit (kuten puheentunnistin `Transcriber`, näppäinsyöttö `KeyboardInjectorProtocol`, ikkunanhallinta `WindowManagerProtocol`) `typing.Protocol`-rajapintojen taakse.

---

## 2. Python 3.13 Best Practices & koodihygienia

### Tyyppivihjeet ja tietomallit
- **Eksplisiittiset tyyppivihjeet:** Lisää tyyppivihjeet kaikille funktioille, metodeille ja luokkien attribuuteille. Käytä modernia Python 3.10+ -syntaksia (`str | None`, `list[str]`, `dict[str, str]`, ei vanhaa `Optional`/`List`).
- **Strukturoidut mallit:** Käytä `@dataclass(slots=True)` (ja muuttumattomalle datalle `@dataclass(frozen=True, slots=True)`) sekä `Enum`-luokkia vapaamuotoisten `dict`-rakenteiden ja maagisten merkkijonojen sijaan.

### Modulaarisuus, luettavuus ja PEP 8
- **Tiedosto- ja funktiokoko:** Pidä yksittäinen `.py`-tiedosto alle **400–500 rivin** ja funktiot tiiviinä (~30–50 riviä, yksi selkeä vastuu). Jos tiedosto kasvaa isoksi, jaa se alimoduuleihin.
- **Matala sisäkkäisyys:** Suosi aikaisia palautuksia (*early return / guard clauses*) syvien `if/else`-rakenteiden sijaan.
- **Nimeäminen:**
  - `snake_case` moduuleille, funktioille ja muuttujille
  - `PascalCase` luokille ja `Enum`-tyypeille
  - `UPPER_SNAKE_CASE` moduulitason vakioille
  - Koodin symbolit ja tiedostonimet englanniksi; käyttöliittymätekstit, dokumentaatio ja selittävät kommentit suomeksi.
- **Import-hygienia:**
  - Ryhmittele importit kolmeen osaan tyhjällä rivillä erotettuna: (1) standardikirjasto, (2) kolmannen osapuolen kirjastot, (3) `puhis`-moduulit.
  - Älä käytä villikortti-importteja (`from module import *`).
  - Poista käyttämättömät importit ja muuttujat.
- **Yleiset Python-ansat (vältä aina):**
  - **Ei muuttuvia oletusargumentteja:** Kirjoita `items: list[str] | None = None`, älä koskaan `items: list[str] = []`.
  - **Polut:** Käytä aina `pathlib.Path`-luokkaa merkkijonojen yhdistämisen sijaan.
  - **Merkistö:** Määritä tiedosto-operaatioissa aina `encoding="utf-8"`.
  - **Kommentit:** Kommentoi *miksi* ratkaisu on tehty (esim. Win32-erityispiirre), älä *mitä* koodi rivi riviltä tekee. Säilytä olemassa olevat kommentit, ellei logiikka muutu.

---

## 3. Virheenkäsittely, lokitus ja resurssien hallinta

- **Lokitus (`logging`), ei `print()`:**
  - Käytä jokaisessa moduulissa `logger = logging.getLogger(__name__)`.
  - Älä jätä debug-`print()`-kutsuja tuotantokoodiin (komentorivin testiskriptit `scripts/`-kansiossa saavat tulostaa selkeästi).
- **Täsmällinen poikkeustenkäsittely:**
  - Älä koskaan käytä paljasta `except:`-lohkoa tai niele virheitä hiljaa (`except Exception: pass`).
  - Nappaa mahdollisimman tarkka poikkeus (`OSError`, `ValueError`, `json.JSONDecodeError`), lokita tekninen syy (`logger.exception(...)`) ja palauta/näytä käyttäjälle ymmärrettävä suomenkielinen virheviesti.
- **Resurssien hallinta:**
  - Käytä aina `with`-kontekstimanageria tiedostoille, lukoille ja äänivirroille sekä `try / finally` -lohkoa hallittuun vapautukseen.
- **Atominen tiedostotallennus:**
  - Kun tallennat asetuksia (`config.json`), kirjoita ensin väliaikaistiedostoon samaan hakemistoon (`flush()` + `os.fsync()` tarvittaessa) ja korvaa kohdetiedosto atomisesti `os.replace()`-kutsulla. Näin asetukset eivät korruptoidu kaatumistilanteessa.

---

## 4. Säikeet ja PySide6 (Qt6) -käytännöt

- **Pidä UI-säie vapaana:**
  - Äänikaappaus (`sounddevice`), VAD ja `faster-whisper`-päättely ajetaan aina taustasäikeessä (`threading.Thread` tai `QThread`), ei koskaan Qt:n pääsäikeessä.
- **Säieturvallinen kommunikaatio:**
  - Taustasäikeet eivät saa koskaan muokata Qt-widgettejä suoraan. Välitä tulokset, tilamuutokset ja virheet UI:lle `PySide6.QtCore.Signal`-signaalien tai säieturvallisen `queue.Queue`-jonon kautta.
- **Siisti sammutus:**
  - Käytä `threading.Event`-pysäytyslippua ja odota taustasäikeiden päättymistä kohtuullisella aikakatkaisulla (`thread.join(timeout=2.0)`), jotta ohjelma sulkeutuu jättämättä taustaprosesseja tai mikrofonilukkoja.

---

## 5. Windows-spesifiset käytännöt (`ctypes` & tietoturva)

- **Tallennussijainnit:**
  - Asetukset: `%APPDATA%\puhis\config.json`
  - Lokit ja välimuisti: `%LOCALAPPDATA%\puhis\logs\`
  - Älä koskaan kovakoodaa käyttäjäpolkuja (`C:\Users\...`) äläkä kirjoita asennuskansioon.
- **Win32 `ctypes`-turvallisuus:**
  - Määrittele Win32-funktioille aina eksplisiittiset `argtypes` ja `restype` -tyypit.
  - Käytä `ctypes.WinDLL("user32", use_last_error=True)` ja tarkista epäonnistuessa `ctypes.get_last_error()`.
- **Fokus ja näppäinsyöttö:**
  - Kelluva kissaikoni merkitään `WS_EX_NOACTIVATE` + `WS_EX_TOPMOST` -lipuilla, jottei se varasta fokusta aktiiviselta kohdeikkunalta.
  - Tavallinen teksti (mukaan lukien ääkköset) syötetään `SendInput`-kutsuilla `KEYEVENTF_UNICODE`-lipulla ja erikoisnäppäimet (`Enter`, `Tab`, `Backspace`) virtuaalinäppäinkoodeilla (`VK_*`).
- **Tietoturva ja oikeudet:**
  - Aja normaalikäyttäjän oikeuksilla (ei tarpeetonta Admin/UAC-korotusta).
  - Älä koskaan käytä `subprocess.Popen(..., shell=True)` puheesta tunnistetulla tekstillä. Sovellusten käynnistys sallii vain käyttäjän asetuksissa määrittelemät sovellusaliakset ja turvallisen argumenttilistan (`shell=False`).
  - Validoi asetustiedostojen sisältö ja tiedostokoot latauksen yhteydessä.

---

## 6. Yksikkötestit (`unittest`) ja laadunvarmistus

### Testausperiaatteet
- **Testikehys:** Käytä Pythonin sisäänrakennettua `unittest`-moduulia (`tests/test_<moduuli>.py`), jotta testit toimivat ilman ylimääräisiä riippuvuuksia.
- **Rakenne (AAA):** Jaa jokainen testi selkeästi vaiheisiin *Arrange* (alustus), *Act* (kutsu) ja *Assert* (tarkistus). Nimeä testit kuvaavasti: `test_<toiminto>_<tilanne>_<odotettu_tulos>`.
- **Täydellinen eristys (pakollinen):**
  - Testit eivät saa koskaan lukea tai muokata käyttäjän oikeaa `%APPDATA%\puhis\`-hakemistoa, käynnistää oikeita Windows-sovelluksia tai lähettää oikeita näppäinpainalluksia työpöydälle.
  - Käytä tiedostotesteissä aina `tempfile.TemporaryDirectory()`-kontekstia.
  - Eristä Win32-, ääni- ja STT-rajapinnat kevyillä fake-toteutuksilla tai `unittest.mock`-olioilla.
- **Mitä testataan aina:**
  - Ydinlogiikan normaali toiminta (*happy path*).
  - Rajatapaukset: tyhjä puhe, ääkköset, isot/pienet kirjaimet, peräkkäiset välimerkit/näppäinkomennot, puuttuvat avaimet, korruptoitunut JSON.
  - Virhetilanteet: tuntematon ikkuna-alias (`t99`), suljettu ikkuna, puuttuva sovellusalias.

### Pakollinen tarkistuslista ennen committia

1. **Virtuaaliympäristö:** Pidä kaikki paketit `.venv`-hakemistossa ja päivitä `requirements.txt` & `pyproject.toml` uusien riippuvuuksien myötä.
2. **Syntaksitarkistus:**
   ```powershell
   .\.venv\Scripts\python.exe -m compileall -q src tests scripts
   ```
3. **Yksikkötestit:**
   ```powershell
   .\.venv\Scripts\python.exe -m unittest discover -s tests -v
   ```
4. **Git-hygienia:** Varmista `git status` -komennolla, ettei `.venv/`, `__pycache__/`, `.env`, lokitiedostot tai ladatut Whisper-mallit päädy versiohallintaan.
5. **Dokumentaatio:** Päivitä `README.md`, jos julkiset ominaisuudet, rakenne tai ajokomennot muuttuivat.
