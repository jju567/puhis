# AGENTS.md – Koodaus-, arkkitehtuuri- ja kehitysohjeet (Puhis)

Tämä tiedosto sisältää projektikohtaiset käytännöt, yleiset ohjelmointiohjeet sekä Windows-kehityksen pelisäännöt `puhis`-repositoriota varten.

**Lukittu teknologiapino:** Python 3.13+ · `PySide6` (Qt6) · `faster-whisper` (paikallinen `small` INT8 CPU:lla) · `sounddevice` + VAD · Win32 API (`ctypes`).

**Pakollinen sääntö:** Tiedoston [docs/ohjelmointiohjeet.md](docs/ohjelmointiohjeet.md) ohjelmointiohjeita, koodihygieniaa, Python-käytäntöjä ja testausvaatimuksia on **aina noudatettava** kaikessa toteutuksessa ilman poikkeuksia. Ylätason suunnitelma ja vaihekohtainen seuranta löytyvät tiedostosta [docs/suunnitelma.md](docs/suunnitelma.md).

---

## 1. Projektin rakenne

```text
puhis/
├── AGENTS.md                  # Agenttien ja kehityksen pääohjeet
├── README.md                  # Projektin kuvaus, asennus ja käyttöohjeet
├── .gitignore                 # Versiohallinnan ohitukset (buildit, lokit, .env)
├── .gitattributes             # Rivinvaihto- ja merkistösäännöt
├── docs/
│   └── ohjelmointiohjeet.md   # Yleiset ohjelmointi- ja Windows-ohjeet
├── src/                       # Varsinainen lähdekoodi (jaetaan core / ui / platform)
├── tests/                     # Yksikkö- ja integraatiotestit
└── scripts/                   # Build-, tarkistus- ja apuskriptit
```

- **Modulaarinen jako (`src/`):** Erota liiketoimintalogiikka (`core/` tai `domain/`), käyttöliittymä (`ui/`) ja Windows-järjestelmärajapinnat (`platform/`) toisistaan. Älä sekoita sovelluslogiikkaa suoraan käyttöliittymäkoodiin.
- **Merkistö ja rivinvaihdot:** Käytä kaikkialla `UTF-8`-merkistöä. Rivinvaihdot määritellään `.gitattributes`-tiedostossa (`LF` yleisesti, `CRLF` Windows-komentojonoille kuten `.bat`/`.ps1`).

---

## 2. Yleiset koodaus- ja arkkitehtuuriperusteet

- **Pidä tiedostot ja funktiot tiiviinä:** Jos kooditiedosto kasvaa yli ~400–500 rivin, jaa se selkeästi pienempiin moduuleihin yhden vastuun periaatteella.
- **Älä duplikoi logiikkaa:** Jos sama logiikka toistuu, eriytä se yhteiseen apufunktioon tai moduuliin.
- **Selkeä virheenkäsittely:**
  - Älä niele virheitä hiljaa. Käsittele poikkeukset ja virhekoodit hallitusti, lokita tekninen syy ja näytä käyttäjälle ymmärrettävä suomenkielinen virheilmoitus.
  - Tarkista aina `null`/tyhjät arvot, taulukoiden rajat ja nollalla jako.
- **Kieli ja kommentointi:**
  - Dokumentaatio, `README.md`, suunnitelmat ja käyttöliittymätekstit kirjoitetaan selkeällä suomen kielellä (ellei toisin sovita).
  - Koodin symbolit (luokat, funktiot, muuttujat, tiedostonimet) nimetään englanniksi valitun kielen nimeämiskäytäntöjen mukaisesti.
  - Kommentoi *miksi* jokin ratkaisu on tehty, älä *mitä* koodi rivi riviltä tekee. Säilytä olemassa olevat kommentit, ellei kyseistä logiikkaa muuteta.

---

## 3. Windows-ohjelman erityissäännöt

- **Polut ja tallennussijainnit:**
  - Älä koskaan kovakoodaa käyttäjäkohtaisia absoluuttisia polkuja (`C:\Users\...`).
  - Tallenna käyttäjän asetukset, välimuisti ja lokit Windowsin standardihakemistoihin (`%APPDATA%` / `%LOCALAPPDATA%`), älä sovelluksen asennuskansioon (`Program Files`).
  - Käsittele polkujen välilyönnit ja erikoismerkit (ääkköset) turvallisesti kielen omilla polkukirjastoilla.
- **Resurssien hallinta ja responsiivisuus:**
  - Vapauta tiedostokahvat, verkko- ja laiteyhteydet sekä käyttöjärjestelmäkahvat aina hallitusti (`try/finally`, `using`, `with`, RAII).
  - Älä estä käyttöliittymäsäiettä (UI thread) raskaalla laskennalla tai I/O-toiminnoilla; käytä asynkronisuutta tai taustasäikeitä.
- **Käyttöoikeudet ja tietoturva:**
  - Ohjelman tulee toimia tavallisen käyttäjän oikeuksilla ilman järjestelmänvalvojan (Admin/UAC) korotusta, ellei yksittäinen ominaisuus sitä välttämättä vaadi.
  - Älä koskaan vie salasanoja, API-avaimia, tokeneita tai henkilökohtaisia polkuja Git-versiohallintaan.
  - Validoi kaikki ulkoiset syötteet ja tiedostot (tiedostokoko, tyyppi, polkuturvallisuus).
- **High-DPI ja teemat:** Suunnittele käyttöliittymä skaalautuvaksi eri DPI-asetuksilla ja huomioi Windowsin vaalea/tumma teema.

---

## 4. Suunnittelu-, testaus- ja Git-käytännöt

- **Suunnitelma ja varmistus aina ennen toteutusta (pakollinen työtapa):**
  - Ennen uuden ominaisuuden tai muutoksen toteutusta tehdään **aina ensin suunnitelma** (tarvittaessa tiedostoon `docs/`), johon kuvataan tavoite, rakenne, mahdolliset Windows-oikeus-/tietoturvavaikutukset ja testaustapa.
  - **Varmista suunnitelma aina käyttäjältä** ennen varsinaisen koodauksen aloittamista. Älä aloita toteutusta ilman käyttäjän kuittausta.
- **Yksikkötestit ja eristys:**
  - Ydinlogiikalle (`core/` / `domain/`) kirjoitetaan yksikkötestit.
  - Testit eivät saa koskaan muokata käyttäjän oikeita asetustiedostoja tai tuotantodataa — käytä testeissä aina eristettyjä väliaikaishakemistoja.
- **`README.md` ajan tasalle:** Päivitä `README.md` aina, kun projektin rakenne, valittu teknologia, käännösohjeet tai julkiset ominaisuudet muuttuvat.
- **Ennen committia (pakollinen tarkistus):**
  - Käytä virtuaaliympäristöä (`.venv\Scripts\python.exe`) tai `py`-komentoa.
  - Aja syntaksitarkistus: `.venv\Scripts\python.exe -m compileall -q src tests scripts`
  - Aja yksikkötestit: `.venv\Scripts\python.exe -m unittest discover -s tests -v`
  - Tarkista, ettei väliaikaistiedostoja, build-artefakteja, malleja tai salaisuuksia ole päätynyt Git-muutoksiin.
- **Commit-viestit ja raportointi:**
  - Pidä commitit rajattuina ja kuvaa tiiviisti *mitä* ja *miksi* muutettiin.
  - Ilmoita aina rehellisesti, mitkä tarkistukset ja testit ajettiin paikallisesti ja mitä ei voitu testata.
