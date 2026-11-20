# Vaihe 5 – Viimeistely, vakaus & Windows-paketointi

**Tila:** `Suunniteltu (odottaa Vaiheen 4 valmistumista ja hyväksyntää)`  
**Ylätason suunnitelma:** [../suunnitelma.md](../suunnitelma.md)

---

## 1. Tavoite

Viimeistellään `Puhis` päivittäiseen Windows-arkikäyttöön vakaaksi ja helposti käynnistettäväksi sovellukseksi:
- Valinnainen automaattikäynnistys Windowsin kirjautumisen yhteydessä (normaalikäyttäjän oikeuksilla).
- Moninäyttö- ja resoluutiomuutosten siisti käsittely (jos kissa jää näytön ulkopuolelle esim. ulkoisen näytön irrotuksen jälkeen, se palautetaan näkyvälle alueelle).
- Selkeä virheenkäsittely reunaolosuhteissa (mikrofoni irrotetaan ajon aikana, Whisper-mallin ensimmäinen lataus edistymisilmaisimella).
- Paketointiskripti Windows-jakelua varten (`PyInstaller` onedir-paketti, ei yksittäisen tiedoston hidasta purkua).

---

## 2. Tiedostorakenne ja moduulit

```text
src/puhis/
├── platform/
│   └── autostart.py            # Windows HKCU\...\Run automaattikäynnistyksen kytkentä (ilman Adminia)
└── ui/
    └── screen_bounds.py        # Kissan sijainnin varmistus näkyvien näyttöjen sisälle

scripts/
└── build_exe.ps1               # PyInstaller-paketointiskripti Windowsille

tests/
└── test_screen_bounds.py       # Sijainnin palautus näkyvälle alueelle eri näyttökokoonpanoilla
```

---

## 3. Windows-oikeus- ja tietoturvavaikutukset

- **Automaattikäynnistys:** Kirjoittaa vain nykyisen käyttäjän rekisterihaaraan (`HKCU\Software\Microsoft\Windows\CurrentVersion\Run`) — ei vaadi Admin-oikeuksia, ja kytkettävissä pois asetuksista.
- **Paketointi:** `.exe` ei sisällä mitään käyttäjäkohtaisia polkuja, asetuksia tai salaisuuksia.

---

## 4. Testaustapa

- **Yksikkötestit (`unittest`):** `test_screen_bounds.py` (kissa ulkona oikealta/alhaalta/irrotetulta näytöltä -> siirtyy turvallisesti näkyvälle näytölle).
- **Manuaalinen loppukatselmointi Windowsilla:**
  - Paketoidun `puhis.exe`:n käynnistys puhtaassa kansiossa.
  - Mikrofonin irrotus ja takaisinkytkentä → ei kaadu, näyttää selkeän suomenkielisen ilmoituksen.
  - Automaattikäynnistyksen päälle/pois-testaus.
  - Täysi käyttökierros: käynnistys → `"puhis avaa laskin"` → `"puhis save t1"` → sanelu Muistioon → asetusten muokkaus → sulkeminen.

---

## 5. Toteutuksen seuranta

| # | Tehtävä | Tila | Huomiot |
| :--- | :--- | :--- | :--- |
| 5.1 | Toteuta `ui/screen_bounds.py` (moninäyttö- ja DPI-suojaus) | `[ ]` | |
| 5.2 | Toteuta `platform/autostart.py` ja kytke asetusikkunaan | `[ ]` | Vain `HKCU`, ei Adminia |
| 5.3 | Lisää mallin latauksen tilailmoitus ja mikrofonivirheiden hallittu toipuminen | `[ ]` | |
| 5.4 | Toteuta `scripts/build_exe.ps1` (`PyInstaller`) | `[ ]` | |
| 5.5 | Kirjoita yksikkötestit (`test_screen_bounds.py`) | `[ ]` | |
| 5.6 | Aja täysi testikierros (`compileall`, `unittest`, paketoitu `.exe`) | `[ ]` | |
| 5.7 | Päivitä `README.md` (käyttö- ja paketointiohjeet) ja seurantataulukot | `[ ]` | |

### Hyväksymiskriteerit (Done)
- [ ] Paketoitu sovellus käynnistyy ja toimii luotettavasti ilman erillistä Python-asennusta.
- [ ] Mikrofoni- ja näyttömuutokset käsitellään kaatumatta.
- [ ] Kaikki yksikkötestit menevät läpi ja dokumentaatio on ajan tasalla.
