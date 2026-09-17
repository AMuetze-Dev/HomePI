# Artefakt „staffelpilot" — Auftrag für den Agenten

Dieses Artefakt ist **gefüllt und läuft**. Was es kann und warum es so
entschieden ist, steht in [README.md](README.md); dieser Text beschreibt, wie
hier gearbeitet wird und was noch aussteht.

Lies zuerst [`../../docs/06-artefakte.md`](../../docs/06-artefakte.md) — dort
steht, warum ein Artefakt ein Modul im Gateway ist und kein eigener Container —
und [`../../docs/12-testen.md`](../../docs/12-testen.md) für die Prüfebenen.

## Stand (17.09.2026)

Gebaut: Staffeln, Warteschlange mit Fälligkeit, Spielberichte und Befunde,
Abhaken, Einstellungen, Mannschaften mit geratenem Aufbau, Regelkatalog,
Vorgänge (Mahnung und Sportgerichtsantrag als Entwurf). 146 Tests, 100 %
Zeilen und Zweige; Oberfläche mit fünf Reitern, 265 Frontend-Tests.

Offen, in der Reihenfolge, in der es sich lohnt:

| | |
|---|---|
| **DFBnet-Prüfdienst** | eigener Container mit Playwright. Er füllt `POST /import`, `PUT /regeln` und `PUT /staffeln/{id}/mannschaften`. Das ist das größte fehlende Stück — ohne ihn kommen keine Daten herein |
| **Mahnung als PDF** | der Vordruck des Verbandes. Text und Felder stehen, das Formular fehlt. Vorlage: `D:/DevLibrary/StaffelPilot/src/core/mahnung.py` |
| **Ergebnisse eines Prüflaufs** | Fortschritt und Protokoll, solange der Dienst läuft |

**Zwei Zusagen sind nicht verhandelbar** und gehören in jede Änderung:

1. Ein Bericht wird erst abgehakt, wenn zu **jedem** Befund eine Entscheidung
   vorliegt.
2. **Es wird nichts verschickt.** Entwürfe entstehen aus Vorlagen, Wort für
   Wort vorhersagbar — kein erzeugter Text, kein Mailversand. „Versandt" hält
   fest, was ein Mensch getan hat.

---

## 1. Was bereits funktioniert

Nicht neu bauen, nicht umbauen:

| | |
|---|---|
| Anmeldung | Entry Point `homepi.module` in `pyproject.toml` → Gateway findet das Modul beim Start |
| Routing | Router hängt unter `/staffelpilot`; Traefik leitet `api.<domain>/staffelpilot` dorthin |
| Kachel | Startseite liest `GET /module` und zeigt „StaffelPilot" — ohne Frontend-Änderung |
| Health | `/health` und `/info` kommen aus `homepi-core` |
| Fehlerformat | Jeder Fehler wird RFC 9457 `problem+json`. Eigene Fehler erben von `ServiceError` |
| Logging | JSON in Produktion, Text lokal, `X-Request-ID` in jeder Zeile |
| DB-Sitzung | `DbSitzung` aus `homepi_core.deps` — eine Transaktion je Anfrage |
| Tabellen | erben von `homepi_core.Base`; das Gateway legt sie beim Start an |

**Du schreibst nie selbst:** FastAPI-App, CORS, Middleware, Health-Endpunkt,
Datenbank-Engine, Logging-Konfiguration, Dockerfile, Compose-Fragment.

---

## 2. Dateien und ihre Rolle

```
modules/staffelpilot/
  src/homepi_staffelpilot/
    __init__.py    Anmeldung: modul = Modul(id=..., titel=..., router=...)
    schemas.py     Pydantic: was rein- und rausgeht
    modelle.py     SQLAlchemy: Tabellen (löschen, wenn kein DB-Bedarf)
    dienst.py      REINE Fachlogik - keine DB, kein await, keine Fixtures
    speicher.py    DB-Zugriff - kein einziges if
    router.py      HTTP: übersetzt Anfrage ↔ Fachlichkeit, sonst nichts
  tests/
    unit/          läuft immer, ohne DB, Millisekunden
    integration/   Marker `integration`, braucht Postgres

services/web/src/module/staffelpilot/
  api.ts                 typisierter Zugriff auf das Backend
  StaffelpilotSeite.tsx    die Oberfläche
  StaffelpilotSeite.module.css
```

### Die Trennung ist nicht verhandelbar

`dienst.py` enthält die Entscheidungen und ist rein. `speicher.py` macht I/O
und entscheidet nichts. `router.py` übersetzt.

Der Grund ist messbar: Unit-Tests laufen dadurch in Millisekunden, und nur
deshalb benutzt man die rot-grün-Schleife wirklich. Sobald eine
Fallunterscheidung in `speicher.py` oder `router.py` rutscht, braucht ihr Test
eine Datenbank — und ab da wird nicht mehr getestet, sondern geklickt.

---

## 3. Ablauf

### 3.1 Vertrag zuerst

Schreibe `schemas.py`. Was geht rein, was kommt raus, welche Werte sind
zulässig. Pydantic-Validierung wird automatisch zu `422` mit Feldnamen.

### 3.2 Fachlogik testgetrieben

1. Test in `tests/unit/test_dienst.py` schreiben und **scheitern sehen**
2. einfachste Änderung in `dienst.py`, die ihn grün macht
3. aufräumen, Tests bleiben unverändert

```bash
make dev N=staffelpilot              # Gateway lädt nur dieses Artefakt
cd modules/staffelpilot && uv run ptw . --now
```

Für die Oberfläche in einem zweiten Fenster:

```bash
make tdd-web N=staffelpilot
```

### 3.3 Persistenz

Tabellen in `modelle.py` (erben von `Base`), Zugriff in `speicher.py`.
Integrationstests gegen die Datenbank `test`:

```bash
make dev                       # Umgebung läuft
cd modules/staffelpilot
DATABASE_URL='postgresql+asyncpg://app:app@127.0.0.1:15432/test' uv run pytest -m ''
```

### 3.4 Endpunkte

`router.py`. Regeln:

- `summary=` bei jedem Endpunkt — die generische Ansicht im Frontend zeigt ihn
- feste Pfade **vor** parametrisierte, sonst liest FastAPI `/zusammenfassung`
  als UUID und antwortet `422`
- Fehler über eigene `ServiceError`-Klassen, nie `HTTPException`
- Rückgabetypen annotieren, sonst fehlt das OpenAPI-Schema

### 3.5 Oberfläche

`api.ts` erweitern, dann die Seite. Zugriff über Rollen und sichtbaren Text,
nie über CSS-Klassen. Nur Tokens aus `src/styles/tokens.css` — kein fester
Farbwert, keine feste Pixelzahl. Bausteine aus `src/ui`:
`Knopf`, `Karte`, `Feld`, `Etikett`, `Hinweis`, `Leerzustand`, `Platzhalter`.

Details: [`../../docs/08-design.md`](../../docs/08-design.md).

---

## 4. Abnahmekriterien

Fertig ist das Artefakt, wenn **alles** davon zutrifft:

```bash
# Backend
cd modules/staffelpilot
uv run ruff format --check . && uv run ruff check . && uv run mypy
DATABASE_URL='postgresql+asyncpg://app:app@127.0.0.1:15432/test' uv run pytest -m ''

# Frontend
cd services/web
npx prettier --check src && npx eslint . && npm run typecheck && npm run test:coverage

# Zusammenspiel
make dev && make smoke
```

Kürzer, solange du nur an diesem Artefakt arbeitest:

```bash
make test-modul N=staffelpilot
```

| Kriterium | Schwelle |
|---|---|
| Coverage Backend | ≥ 85 % |
| Coverage Frontend | ≥ 85 % Zeilen, ≥ 80 % Zweige |
| `mypy --strict` | keine Fehler |
| `GET /module` | `staffelpilot` mit `status: "bereit"` |
| Rauchtests | grün |

Zusätzlich, was kein Werkzeug prüft:

- [ ] Jeder Ladezustand hat einen Platzhalter, keinen Layoutsprung
- [ ] Der Erstzustand erklärt, was als Nächstes zu tun ist
- [ ] Fehlermeldungen des Backends erreichen den Benutzer wörtlich, nicht als
      „Fehler 409"
- [ ] Ein fehlgeschlagenes Formular behält seine Eingabe
- [ ] Bei 375 px Breite ist alles erreichbar, ohne horizontal zu scrollen

---

## 5. Ausrollen

```bash
git commit && git push          # CI prüft
homepi deploy -s staffelpilot    # Pipeline baut arm64, Pi zieht
```

Die Kachel erscheint danach von selbst.

---

## 6. Häufige Fehler

| Symptom | Ursache |
|---|---|
| Kachel fehlt | Entry Point in `pyproject.toml` falsch, oder Modul nicht als Abhängigkeit im Gateway |
| `status: "fehler"` im Manifest | Import wirft. Grund steht in der Kachel und im Log |
| `422` statt Treffer | parametrisierte Route steht vor der festen |
| `RuntimeError: keine DATABASE_URL` | Unit-Test benutzt `DbSitzung`; das gehört in `tests/integration/` |
| Leere Tabelle nach Neustart | `DB_SCHEMA_ANLEGEN=false`. Lokal `true`, in Produktion braucht es eine Migration |
| Endpunkt fehlt in generischer Ansicht | `summary=` oder Rückgabetyp fehlt |
