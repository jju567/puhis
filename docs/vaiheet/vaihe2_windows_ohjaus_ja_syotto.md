# Vaihe 2 – Komentotulkki, tekstinmuunnos, näppäinsyöttö & ikkunanhallinta

**Tila:** `Valmis`  
**Ylätason suunnitelma:** [../suunnitelma.md](../suunnitelma.md)

---

## 1. Tavoite

Rakennetaan koko komentojen käsittelyketju ja Windows-ohjaus ilman puheentunnistusta (testattavissa yksikkötesteillä ja tekstisyötteellä):
- **Herätesanan tunnistus ja komentotulkki (`core/command_parser.py`):**
  - Tunnistaa muokattavan herätesanan (oletus `"puhis"`).
  - Jäsentää komennot: `"puhis sanele"`, `"puhis seis"`, `"puhis mykistä"`, `"puhis save t1"`, `"puhis t1"` / `"puhis fokus t1"`, `"puhis piilota t1"`, `"puhis piilota"`, `"puhis avaa laskin"` / `"puhis käynnistä laskin"`.
- **Tekstinmuunnos (`core/text_transformer.py`):**
  - Muuntaa sanelutekstin vuorotteleviksi `TextAction`- ja `KeyAction`-tapahtumiksi (esim. `"moi pilkku maailma enter"` → `"moi, maailma"` + `VK_RETURN`).
  - Hoitaa välimerkkien välilyöntisäännöt (ei välilyöntiä ennen `. , ? ! : ;`, välilyönti jälkeen).
  - Tukee käyttäjän muokattavia yksi- ja monisanaisia avainsanoja (esim. `enter`, `tab`, `piste`, `pilkku`, `kysymysmerkki`, `huutomerkki`, `rivinvaihto`, `pyyhi`).
- **Ikkunarekisteri (`core/window_registry.py`):**
  - Tallentaa lennossa nimetyt ikkunat (`t1`, `t2`, ...) sisältäen `hwnd`, prosessin nimen ja ikkunan otsikon.
- **Puhejakson reititin (`core/utterance_router.py`):**
  - Kytkee komentotulkin, tekstinmuunnoksen, ikkunarekisterin ja alustarajapinnat yhteen.
- **Windows-alustakerros (`platform/`):**
  - `keyboard_injector.py`: Win32 `SendInput` (`KEYEVENTF_UNICODE` ääkkösille + `VK_*` erikoisnäppäimille).
  - `window_manager.py`: `GetForegroundWindow`, `SetForegroundWindow`, `ShowWindow` (minimoi/piilota/palauta), `IsWindow`, `IsIconic`.
  - `app_launcher.py`: turvallinen sovellusten käynnistys käyttäjän määrittämästä alias-taulukosta (`subprocess.Popen(..., shell=False)`).

---

## 2. Tiedostorakenne ja moduulit

```text
src/puhis/
├── core/
│   ├── actions.py              # Dataclassit & Protocol-rajapinnat: TextAction, KeyAction, ParsedCommand, UtteranceResult
│   ├── command_parser.py       # Herätesana + komentojen jäsennys
│   ├── text_transformer.py     # Saneluteksti -> teksti- ja näppäintapahtumat
│   ├── utterance_router.py     # Komentojen ja sanelun reititin
│   └── window_registry.py      # Ikkuna-aliasten (t1, t2...) hallinta
└── platform/
    ├── keyboard_injector.py    # Win32 SendInput (Unicode + VK_*)
    ├── window_manager.py       # Win32 ikkunanhallinta (fokus, piilotus, aktiivinen ikkuna)
    └── app_launcher.py         # Valkolistattu sovellusten käynnistys

tests/
├── test_command_parser.py      # Herätesana, kaikki komennot, isot/pienet kirjaimet, tuntemattomat komennot
├── test_text_transformer.py    # Välimerkit, enter/tab, ääkköset, peräkkäiset avainsanat, tyhjä syöte
├── test_window_registry.py     # save t1, ylikirjoitus, haku, poisto, tuntematon alias
├── test_utterance_router.py    # Komentojen ja sanelun reititys fake-alustarajapinnoilla
├── test_app_launcher.py        # Valkolistatut sovellukset ja virheenkäsittely
└── test_keyboard_injector.py   # INPUT-puskurin muodostus (UTF-16LE + VK_*)
```

---

## 3. Windows-oikeus- ja tietoturvavaikutukset

- **UIPI-rajoitus:** Tavallisilla käyttäjäoikeuksilla `SendInput` ei kirjoita Admin-oikeuksin ajettaviin ikkunoihin (dokumentoitu `README.md`:ssä).
- **Turvallinen käynnistys:** `app_launcher.py` ei koskaan aja raakaa puhetekstiä shellissä (`shell=False`). Vain `config.json`:ssa määritellyt sovellusaliakset (esim. `"laskin": ["calc.exe"]`) voidaan käynnistää.
- **`SetForegroundWindow`-rajoitus:** Palautetaan minimoitu ikkuna (`SW_RESTORE`) ennen fokusointia ja käsitellään epäonnistuminen siististi lokittaen.

---

## 4. Testaustapa

- **Yksikkötestit (`unittest`):** Kattavat testit `command_parser`, `text_transformer`, `window_registry`, `utterance_router`, `app_launcher` ja `keyboard_injector` -moduuleille täysin ilman oikeita Win32-vaikutuksia.
- **Testiskripti (`scripts/test_win32_actions.py`):**
  - `--dry-run`: kuiva-ajo komentoketjulle ilman sivuvaikutuksia.
  - `--live`: kirjoittaa Muistioon ääkkösiä + `Enter` + `Tab`, tallentaa Muistion `t1`:ksi, käynnistää Laskimen (`"avaa laskin"`), tallentaa Laskimen `t2`:ksi, vaihtaa fokuksen `t1` ↔ `t2` ja piilottaa `t2`:n.

---

## 5. Toteutuksen seuranta

| # | Tehtävä | Tila | Huomiot |
| :--- | :--- | :--- | :--- |
| 2.1 | Toteuta `core/actions.py` ja `core/window_registry.py` | `[x]` | Lisätty myös `Protocol`-rajapinnat |
| 2.2 | Toteuta `core/text_transformer.py` (välimerkit, välilyönnit, erikoisnäppäimet) | `[x]` | Tukee myös monisanaisia avainsanoja ja STT-reunavälimerkkejä |
| 2.3 | Toteuta `core/command_parser.py` (herätesana & komennot) | `[x]` | Yhdistää myös STT:n pilkkomat `t 1` → `t1` |
| 2.4 | Toteuta `platform/keyboard_injector.py` (Win32 `SendInput`) | `[x]` | 64/32-bit `INPUT`-union, Unicode + `VK_*` |
| 2.5 | Toteuta `platform/window_manager.py`, `platform/app_launcher.py` ja `core/utterance_router.py` | `[x]` | `shell=False` |
| 2.6 | Kirjoita yksikkötestit (`test_command_parser.py`, `test_text_transformer.py`, `test_window_registry.py` ym.) | `[x]` | Yhteensä 58 yksikkötestiä |
| 2.7 | Aja `compileall`, `unittest` ja savutesti | `[x]` | `compileall`, `unittest` (58/58), `--dry-run` ja `--live` OK |
| 2.8 | Päivitä `README.md` ja seurantataulukot | `[x]` | |

### Hyväksymiskriteerit (Done)
- [x] Kaikki ydinlogiikan yksikkötestit menevät läpi (58/58).
- [x] Ääkköset, välimerkit, `Enter` ja `Tab` menevät luotettavasti perille Muistioon (`scripts\test_win32_actions.py --live`).
- [x] `save t1`, fokusointi, piilotus ja `"avaa laskin"` toimivat Windowsilla (`scripts\test_win32_actions.py --live`).
