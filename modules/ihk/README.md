# homepi-ihk

IHK-Abschlussprüfungen Fachinformatiker Anwendungsentwicklung bewerten.

Artefakt im HomePI-Gateway. Grundgerüst kommt aus `homepi-core`:
Einstellungen, Logging, `/health`, `/info`, Fehlerformat, Anfrage-Kennung.

**Für Agenten: [AGENTS.md](AGENTS.md)** — dort steht, wie hier gearbeitet wird.

---

## Herkunft

Portiert aus dem **ExamManager V2** (`D:\DevLibrary\ExamManager V2`), einer
Offline-Android-App, die die Excel-Vorlage `TEMPLATE.xlsm` ersetzt hat. Der
Rechenkern (`scoring.ts`) ist hier `dienst.py` und rechnet gegen dieselben
echten Altprüfungen wie dort — ohne Namen, in `tests/unit/altfaelle.json`.

Was sich gegenüber dem ExamManager ändert:

| | ExamManager | hier |
|---|---|---|
| Daten | IndexedDB auf dem Tablet | Postgres auf dem Pi, von jedem Gerät aus |
| PDFs | nur auf dem Tablet | beim Artefakt, `ihk_dokumente` |
| Korrekturbogen | pdfmake im Browser | `bogen.py` mit fpdf2 auf dem Server |
| Zeitmessung | Uhr des Tablets | Zeitstempel vom Server, Anzeige gegen dessen Uhr |
| Sicherung | JSON-Export | `make backup` der Datenbank |

## Bewertung

- **Dokumentation** 100 P über 7 Sektionen, 38 Kriterien. Sektion 5 hat eine
  Mängel-Zeile von −2 bis 0, die in die Punkte einfließt, nicht ins Maximum.
- **Präsentation und Fachgespräch** 100 P über 5 Sektionen. Unterkriterien auf
  der Skala {1; ¾; ½; ¼; 0}; vorgeschlagen wird `round(max · Mittelwert)`, die
  Sektionspunkte setzt der Prüfer.
- **Note** aus der Tabelle der Vorlage, Grenzfälle bei 91, 80, 66, 49, 29.
- **Gesamt** = (Teil 1 · 20 + Teil 2) / 100; Ergänzungsprüfung in genau einem
  Bereich, `round((2 · schriftlich + mündlich) / 3)`, mit und ohne angezeigt.

Gerundet wird wie Excel (halb weg von null), nicht wie Python.

## Katalog

`src/homepi_ihk/katalog/kriterien.json` und `noten.json` werden nicht von Hand
gepflegt. Sie stammen aus `TEMPLATE.xlsm` und wurden mit
`tools/extract_template.py` im ExamManager erzeugt. Ändert die IHK den Bogen:
dort neu erzeugen, hierher kopieren, Tests laufen lassen.

## Entwickeln

```bash
cd modules/ihk
uv run ptw . --now        # Unit-Tests im Watch-Modus
HOMEPI_TEST_DATABASE_URL='postgresql+asyncpg://app:app@127.0.0.1:15432/test' \
  uv run pytest -m 'not smoke' --cov
```

## Ausrollen

Neue Tabellen: `ihk_pruefungstage`, `ihk_prueflinge`, `ihk_dokumente`. Auf dem
Pi danach einmal `homepi schema anlegen` im Gateway-Container, dann das Recht
vergeben:

```bash
homepi benutzer recht <name> ihk verwalter
```
