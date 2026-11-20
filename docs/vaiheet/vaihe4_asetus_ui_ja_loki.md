# Vaihe 4 – Asetusikkuna, muokattavat avainsanat & tapahtumaloki

**Tila:** `Suunniteltu (odottaa Vaiheen 3 valmistumista ja hyväksyntää)`  
**Ylätason suunnitelma:** [../suunnitelma.md](../suunnitelma.md)

---

## 1. Tavoite

Rakennetaan moderni, Windows 11 -tyylinen suomenkielinen asetusikkuna (`Puhis – Asetukset`), jossa on vasemman reunan navigaatiopalkki ja tuki vaalealle/tummalle teemalle. Ikkuna aukeaa kissan oikean klikin valikosta (tai System Traystä) ja mahdollistaa kaiken muokkaamisen ilman JSON-tiedostojen käsin editoimista:
- **Yleiset & Ulkoasu:** Herätesanan vaihto (oletus `"puhis"`), kissan teemaväri (Hiili / Kerma / Oranssi), koko/läpinäkyvyys, oletustila käynnistyksessä sekä live-esikatselu.
- **Ääni & Puhe:** Mikrofonilaitteen valinta, reaaliaikainen äänitasomittari, Whisper-mallin valinta (`small` / `base` / mukautettu polku), VAD-herkkyys.
- **Sanasto & Näppäimet:** Haettava taulukko, jossa käyttäjä voi lisätä, muokata ja poistaa avainsanoja (esim. `"enter"` → `VK_RETURN`, `"tab"` → `VK_TAB`, `"piste"` → `.`).
- **Sovellukset:** Taulukko käynnistettäville ohjelmille (esim. `"laskin"` → `calc.exe`, `"selain"` → `msedge.exe`), mukana "Selaa `.exe`"-valitsin.
- **Ikkunat & Loki:** Näkymä aktiivisista ikkuna-aliaksista (`t1`, `t2`, ...) + reaaliaikainen tapahtumaloki siitä, mitä ohjelma kuuli ja minkä toiminnon se suoritti.

---

## 2. Tiedostorakenne ja moduulit

```text
src/puhis/
├── core/
│   ├── config_validator.py     # Asetusten ja avainsanojen validointi ennen tallennusta
│   └── event_log.py            # Ring-buffer tapahtumalokille (viimeiset N tapahtumaa)
└── ui/
    ├── settings_window.py      # Pääasetusikkuna (vasen sivupalkki + QStackedWidget)
    ├── tabs/
    │   ├── general_tab.py      # Herätesana, mikrofoni, STT-asetukset
    │   ├── keywords_tab.py     # Välimerkkien & näppäinten muokkaustaulukko
    │   ├── apps_tab.py         # Sovellusaliasten muokkaustaulukko + .exe-valitsin
    │   └── windows_log_tab.py  # Tallennetut ikkunat (t1, t2) & reaaliaikainen tapahtumaloki

tests/
├── test_config_validator.py    # Tyhjä herätesana, duplikaattiavainsanat, virheelliset arvot
└── test_event_log.py           # Ring-bufferin kokoraja ja aikaleimat
```

---

## 3. Windows-oikeus- ja tietoturvavaikutukset

- Asetusikkuna saa normaalisti ikkunafokuksen (toisin kuin kelluva kissa).
- Sovelluspolkuja lisättäessä tarkistetaan, että syöte on validi polku tai suoritettava nimi ilman shell-injektiomerkkejä.
- Muutokset tallennetaan atomisesti `%APPDATA%\puhis\config.json` -tiedostoon ja päivittyvät lennosta (`CommandParser`, `TextTransformer`, `initial_prompt`) ilman uudelleenkäynnistystä.
- Huomioidaan High-DPI-skaalaus ja Windowsin vaalea/tumma teema.

---

## 4. Testaustapa

- **Yksikkötestit (`unittest`):**
  - `test_config_validator.py`: tyhjä herätesana hylätään, duplikaattiavainsanat havaitaan, kelvolliset asetukset hyväksytään.
  - `test_event_log.py`: loki pitää muistin kurissa (esim. max 200 riviä).
- **Manuaalinen UI-testaus Windowsilla:**
  - Vaihda herätesana `"puhis"` → `"kissa"` asetuksista → uusi herätesana toimii heti puheella.
  - Lisää uusi avainsana ja uusi sovellusalias → tallentuu ja säilyy uudelleenkäynnistyksen yli.
  - Testaa eri DPI-skaalauksilla (100 % / 125 % / 150 %).

---

## 5. Toteutuksen seuranta

| # | Tehtävä | Tila | Huomiot |
| :--- | :--- | :--- | :--- |
| 4.1 | Toteuta `core/config_validator.py` ja `core/event_log.py` | `[ ]` | |
| 4.2 | Toteuta `ui/settings_window.py` ja välilehdet (`ui/tabs/`) | `[ ]` | Pidä tiedostot < 400 riviä |
| 4.3 | Kytke asetusten välitön päivitys (`hot-reload`) kontrolleriin ja kissaan | `[ ]` | |
| 4.4 | Kytke reaaliaikainen tapahtumaloki UI:hin Qt-signaaleilla | `[ ]` | |
| 4.5 | Kirjoita yksikkötestit (`test_config_validator.py`, `test_event_log.py`) | `[ ]` | |
| 4.6 | Aja `compileall`, `unittest` ja manuaalinen UI-testaus | `[ ]` | |
| 4.7 | Päivitä `README.md` ja seurantataulukot | `[ ]` | |

### Hyväksymiskriteerit (Done)
- [ ] Herätesana, välimerkkiavainsanat ja sovellusaliakset ovat muokattavissa UI:sta ja astuvat voimaan heti.
- [ ] Tapahtumaloki näyttää selkeästi kuullun tekstin ja suoritetun toiminnon.
- [ ] Kaikki yksikkötestit ja syntaksitarkistukset menevät läpi.
