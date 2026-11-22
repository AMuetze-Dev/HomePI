# Artefakt „kinderzimmer" — Auftrag

Lernspiele für ein Kleinkind, gespielt an einem ESP32 mit großen Knöpfen,
Lautsprecher und NFC-Leser. 3D-gedruckte Figuren tragen je einen NFC-Tag.

**Das Gerät spielt allein.** Der Pi ist die Redaktion: Hier werden Figuren,
Aufnahmen und Einstellungen gepflegt, und hier kommt das Protokoll an. Fällt
der Pi aus, spielt das Gerät mit dem letzten Stand weiter. Ein Babyspielzeug,
das bei einem WLAN-Ausfall verstummt, ist kaputt.

Allgemeine Regeln des Repos (Schichten, Tests zuerst, Tokens) stehen in
[`../../AGENTS.md`](../../AGENTS.md) und gelten hier unverändert.

---

## Pädagogische Leitlinien

Sie sind der Grund für mehrere technische Entscheidungen weiter unten. Wer an
einer davon dreht, liest zuerst hier.

1. **Das Gerät spielt mit, es ersetzt niemanden.** Bis etwa 2 Jahre ist jedes
   Spiel für ein Elternteil daneben gebaut.
2. **Eure Stimmen statt Sprachsynthese.** Es gibt keine eingebaute Stimme,
   nur Aufnahmen.
3. **Kein Bildschirm für das Kind.** Das Display ist für die Eltern.
4. **Fehler werden benannt, nicht bestraft.** Kein Summer, kein „falsch".
5. **Keine Belohnungsschleifen.** Keine Punkte, keine Zufallsfanfaren. Das
   Protokoll ist ein Tagebuch, keine Lernstatistik — es gibt bewusst
   **keine** Trefferquoten und keine Prozentwerte.
6. **Vorhersagbar.** Gleiche Figur, gleiche Reaktion.
7. **Kurz, mit Ende.** Nach `ruhe_nach_min` ohne Handlung wird das Gerät still
   und ruft nie von sich aus.
8. **Lautstärke hart gedeckelt.** `lautstaerke_max` ist eine Obergrenze, die die
   Firmware nicht überschreiten darf, auch nicht über die Knöpfe.

Die Spiele selbst, mit Ablauf, Förderziel und Begründung in einfacher Sprache,
stehen in `src/homepi_kinderzimmer/spiele.py`. Die Website zeigt genau diese
Texte. **Neue Spielart = Eintrag dort + Firmware.** Ein Spiel ist erst
`bereit`, wenn die Firmware es kann.

| Phase | Alter | Spiele | Stand |
|---|---|---|---|
| 1 Ich bewirke etwas | 5–9 Monate | Licht und Klang, Vertraute Stimmen | **bereit** |
| 2 Dinge verschwinden nicht | 8–18 Monate | Kuckuck, Tierlaute | geplant |
| 3 Ich ordne die Welt | 1½–3 Jahre | Farben, Formenbox, Rituale, Hörfiguren | geplant |
| 4 Ich denke mit | 3–6 Jahre | Mengen, Echo, Gefühle, Anlaute | geplant |

---

## Was wo liegt

| Datei | Inhalt |
|---|---|
| `spiele.py` | Spielkatalog: feste Daten, keine Datenbank |
| `dienst.py` | Regeln: UID, WAV-Prüfung, Stand, Zeitpunkte, Protokolltexte |
| `speicher.py` | Tabellen lesen und schreiben |
| `router.py` | Elternseite (Anmeldung) und Geräteseite (Token) |
| `geraet.py` | Prüfung des Gerätetokens |

### Zwei Arten von Aufrufern

`zugang=Zugang.SELBST`: Das Artefakt prüft selbst, denn das Gerät hat kein
Benutzerkonto.

- **Eltern** — alle Pfade außer `/geraet/…`. Lesen braucht `leser`, Ändern
  braucht `nutzer`, Geräte verwalten braucht `verwalter`.
- **Gerät** — `/geraet/…` mit `Authorization: Bearer <token>`. Das Token
  entsteht beim Anlegen des Geräts, wird **einmal** angezeigt und liegt nur
  als SHA-256 in der Datenbank — wie ein Sitzungstoken.

`tests/unit/test_anmeldung.py` geht jede Route durch und verlangt eine der
beiden Prüfungen. Ein neuer Endpunkt ohne Prüfung lässt den Test scheitern.

---

## Geräteschnittstelle (Vertrag mit der Firmware)

Format `1`. Ändert sich etwas Inkompatibles, steigt `format`. Eine Firmware,
die ein höheres Format sieht, behält ihren alten Stand und meldet das.

### Ablauf

1. **Start:** `GET /kinderzimmer/geraet/stand` → Manifest.
2. Dateien mit unbekannter oder geänderter `sha256` einzeln holen:
   `GET /kinderzimmer/geraet/dateien/{id}`. Erst in einen Zwischenordner,
   dann umschalten, wenn alles da ist.
3. **Während des Spiels:** Ereignisse live senden,
   `POST /kinderzimmer/geraet/ereignisse`. Ohne Verbindung puffern und beim
   nächsten Erfolg nachsenden.
4. Jede Antwort auf Ereignisse trägt `stand`. Weicht er vom eigenen ab, gleicht
   das Gerät ab, **sobald gerade kein Spiel läuft** — nie mitten im Spiel.

Es gibt kein regelmäßiges Abfragen. Der Abgleich hängt am Start und an den
Antworten auf das Protokoll.

### Manifest

```json
{
  "format": 1,
  "stand": "9f2c4a1b0e7d3c55",
  "einstellungen": {
    "lautstaerke_max": 50, "helligkeit_max": 40, "ruhe_nach_min": 10,
    "startspiel": "licht-und-klang",
    "spiele_aktiv": ["licht-und-klang", "stimmen"],
    "knoepfe": [{"nummer": 1, "farbe": "#FFB000", "klang": "<aufnahme-id>|null"}]
  },
  "figuren": [
    {"uid": "04A1B2C3D4E5F6", "name": "Oma", "art": "familie",
     "farbe": null, "form": null, "menge": null,
     "stimme": "<aufnahme-id>|null", "klang": "<aufnahme-id>|null"}
  ],
  "dateien": [{"id": "<aufnahme-id>", "sha256": "…", "bytes": 88244, "dauer_ms": 2000}]
}
```

- `stand` ist eine Prüfsumme über alles andere, kein Zähler. Gleicher Inhalt
  ergibt denselben Stand, egal wie oft gespeichert wurde.
- `dateien` enthält nur Aufnahmen, die eine Figur oder ein Knopf benutzt.
- UIDs: Großbuchstaben in Hex ohne Trenner, 4, 7 oder 10 Byte.

### Audioformat

WAV, PCM, 16 Bit, **mono, 22 050 Hz**, höchstens 30 Sekunden. Der Browser
schneidet Stille ab, gleicht die Lautheit an und rechnet um, bevor er hochlädt.
Der Pi lehnt alles andere ab. Damit braucht die Firmware keinen Decoder: Sie
schiebt die Samples direkt an den MAX98357A.

Rechnung: 44 KB je Sekunde. Bei rund 10 MB freiem Flash sind das knapp vier
Minuten, also gut 70 Clips von drei Sekunden. Für Phase 1 und 2 reicht das.
Hörfiguren (Phase 3) brauchen ein komprimiertes Format oder eine SD-Karte.
Das ist dann `format: 2`.

### Ereignisse

```json
{
  "start": 17, "jetzt_ms": 912345, "firmware": "0.1.0", "stand": "9f2c4a1b0e7d3c55",
  "ereignisse": [
    {"nr": 1, "ms": 1200, "zeit": "2026-11-20T08:15:02+01:00", "art": "start"},
    {"nr": 2, "ms": 5400, "zeit": null, "art": "knopf", "knopf": 1},
    {"nr": 3, "ms": 9100, "zeit": null, "art": "figur_auf", "uid": "04A1B2C3D4E5F6"}
  ]
}
```

| Feld | Bedeutung |
|---|---|
| `start` (Kopf) | Startzähler des Geräts, steigt bei jedem Einschalten |
| `start` (Ereignis) | nur bei Nachgereichtem aus einem früheren Start, sonst weglassen |
| `nr` | laufende Nummer innerhalb eines Starts |
| `ms` | Millisekunden seit dem Start, als es geschah |
| `zeit` | Uhrzeit, falls NTP schon lief, sonst `null` |
| `jetzt_ms` | Millisekunden seit dem Start beim Absenden |

`art`: `start`, `knopf` (+`knopf`), `figur_auf` / `figur_ab` (+`uid`),
`spiel` (+`spiel`), `ruhe`, `abgleich`.

**Doppelt senden ist harmlos.** `(gerät, start, nr)` ist eindeutig, und ein
zweites Mal wird stillschweigend übergangen. Die Antwort sagt, wie viele neu
waren. Ohne `zeit` rechnet der Pi aus `jetzt_ms - ms` zurück, aber nur für
Ereignisse aus dem **laufenden** Start. Ereignisse aus einem früheren Start ohne
Uhrzeit stehen mit „Zeit unbekannt" im Protokoll.

Antwort: `{"neu": 2, "doppelt": 1, "stand": "…"}`

---

## Hardware (Stand 20.11.2026)

ESP32-S3 DevKitC-1 N16R8 (16 MB Flash, 8 MB PSRAM), PN532, MAX98357A mit
Lautsprecher, Mikroschalter unter gedruckten Knöpfen. Dazu ein Elegoo-Display
mit 2,8-Zoll-Touch. **Es bringt einen eigenen ESP32 mit.** Ob es als
Elternpult per UART mit dem S3 spricht oder nur als Anzeige dient, entscheidet
die Firmware-Runde.

---

## Prüfen

```bash
cd modules/kinderzimmer
uv run ruff format --check . && uv run ruff check . && uv run mypy
DATABASE_URL='postgresql+asyncpg://app:app@127.0.0.1:15432/test' uv run pytest -m 'not smoke' --cov
cd ../../services/web && npx vitest run src/module/kinderzimmer
```

## Ausrollen

Neue Tabellen legt in Produktion `homepi schema anlegen` an (siehe
`docs/04-runbook.md`). Spalten in bestehenden Tabellen brauchen eine Migration
unter `scripts/migrationen/`.
