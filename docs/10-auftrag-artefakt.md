# Auftrag: Artefakt bauen

Diese Datei ist als **alleinige Arbeitsanweisung** gedacht. Du brauchst keinen
weiteren Kontext, um sie auszuführen.

> **Übergabe an einen Agenten:**
> „Arbeite nach `docs/10-auftrag-artefakt.md`. Das Artefakt heißt `<kennung>`
> und soll: `<eine bis fünf Sätze, was es können muss>`."

---

## 0. Was du baust

HomePI ist eine selbst gehostete Anwendung auf einem Raspberry Pi. Ein
**Gateway** (FastAPI) lädt beliebig viele **Artefakte**; eine **Hülle** (React)
zeigt für jedes eine Kachel.

Ein Artefakt besteht aus zwei Hälften in zwei Bäumen:

```
modules/<kennung>/                    Backend, Python
services/web/src/module/<kennung>/    Frontend, TypeScript
```

Ein Artefakt ist **kein eigener Container**. Es meldet sich über einen Entry
Point `homepi.module` an und läuft im Gateway-Prozess mit. Zehn Artefakte sind
so ein Prozess (~250 MB) statt zehn Container (~2 GB) auf einem 16-GB-Pi.

**Du baust nie selbst:** FastAPI-App, CORS, Middleware, `/health`, `/info`,
Logging, Fehlerformat, Datenbank-Engine, Dockerfile, Compose-Fragment,
Deploy-Pipeline. Das kommt alles aus `homepi-core`. Wer davon etwas nachbaut,
hat die falsche Datei geöffnet.

---

## Befehle ohne `make`

`make` ist auf Windows nicht vorinstalliert. Fehlt es, benutze die rechte
Spalte — sie tut genau dasselbe.

| statt | nimm |
|---|---|
| `make dev` | `docker compose -f compose.dev.yml up -d --build --wait` |
| `make dev N=x` | `HOMEPI_MODULE=x docker compose -f compose.dev.yml up -d --build --wait` |
| `make dev-logs` | `docker compose -f compose.dev.yml logs -f` |
| `make artefakt N=x T="T"` | `uv run --project packages/homepi-core homepi new x --titel "T"` |
| `make tdd-api P=modules/x` | `cd modules/x && uv run ptw . --now` |
| `make tdd-web N=x` | `cd services/web && npm run test:watch -- src/module/x` |
| `make smoke` | `cd services/gateway && uv run pytest -m smoke` |

`make test-modul N=x` entspricht:

```bash
cd modules/x
uv run ruff format --check . && uv run ruff check . && uv run mypy
DATABASE_URL='postgresql+asyncpg://app:app@127.0.0.1:15432/test' uv run pytest -m 'not smoke' --cov
cd ../../services/web && npx vitest run src/module/x
```

---

## 1. Voraussetzungen prüfen

```bash
make dev
curl -sf http://127.0.0.1:18000/health
```

Antwortet das nicht mit `{"status":"ok",...}`, **hör hier auf** und melde das.
Ohne laufende Umgebung sind die Integrationstests wertlos.

| | Adresse |
|---|---|
| Frontend | http://localhost:5173 |
| API | http://localhost:18000 (`/docs` für Swagger) |
| Postgres | localhost:15432 — `app` / `app`, Datenbanken `app` und `test` |

---

## 2. Gerüst erzeugen

```bash
make artefakt N=<kennung> T="<Anzeigename>"
cd services/gateway && uv sync
make dev N=<kennung>
```

`make dev N=…` lädt **nur dieses** Artefakt — schnellerer Start, und ein
anderes kaputtes Artefakt steht nicht im Weg.

Einmalig ein Konto anlegen — Artefakte sind per Voreinstellung verschlossen,
ohne Konto siehst du weder die Kachel noch die API:

```bash
export DATABASE_URL='postgresql+asyncpg://app:app@127.0.0.1:15432/app'
cd packages/homepi-core
uv run homepi benutzer anlegen entwickler --artefakt <kennung> --rolle verwalter
```

Kontrolle (`-c` legt die Cookie-Datei an und benutzt sie):

```bash
curl -s -c kekse.txt -X POST http://127.0.0.1:18000/auth/anmelden   -H 'Content-Type: application/json'   -d '{"name":"entwickler","passwort":"<dein Passwort>"}'
curl -s -b kekse.txt http://127.0.0.1:18000/module
```

Dein Artefakt muss mit `"status": "bereit"` dastehen. Steht dort
`"status": "fehler"`, nennt das Feld `beschreibung` den Grund. Ist die Liste
leer, fehlt das Recht — nicht das Artefakt.

Erzeugt wurde:

```
modules/<kennung>/
  AGENTS.md          Kurzfassung dieser Datei, im Artefakt
  pyproject.toml     Entry Point homepi.module  ← nicht umbenennen
  src/homepi_<kennung>/
    __init__.py      modul = Modul(id=…, titel=…, router=…, zugang=…)
    schemas.py       Vertrag nach außen
    modelle.py       Tabellen
    dienst.py        REINE Fachlogik
    speicher.py      Datenbankzugriff
    router.py        HTTP
  tests/unit/        läuft immer, ohne Datenbank
  tests/integration/ Marker `integration`

services/web/src/module/<kennung>/
  api.ts  <Kennung>Seite.tsx  <Kennung>Seite.module.css  <Kennung>Seite.test.tsx
```

Gerüst und Verdrahtung stehen. **Alles, was jetzt folgt, ist Fachlichkeit.**

---

## 3. Die Schichtung ist bindend

| Datei | Darf | Darf nicht |
|---|---|---|
| `dienst.py` | entscheiden, rechnen, prüfen | Datenbank, `await`, I/O |
| `speicher.py` | lesen, schreiben, löschen | fachliche Fallunterscheidungen |
| `router.py` | übersetzen Anfrage ↔ Fachlichkeit | rechnen, entscheiden |

Der Grund ist messbar, nicht ästhetisch: Unit-Tests gegen `dienst.py` laufen in
Millisekunden. Rutscht eine Regel nach `speicher.py` oder `router.py`, braucht
ihr Test eine Datenbank — und ab da wird nicht mehr getestet, sondern geklickt.

**Prüffrage:** Lässt sich jede Regel ohne Datenbank testen? Wenn nein, sitzt sie
falsch.

---

## 4. Reihenfolge

### 4.1 Vertrag — `schemas.py`

Was geht rein, was kommt raus, welche Werte sind zulässig. Pydantic-Fehler
werden automatisch zu `422` mit Feldnamen; das Frontend zeigt sie unverändert.

Namen trimmen, bevor die Länge geprüft wird — sonst geht ein Name aus drei
Leerzeichen durch.

### 4.2 Fachlogik testgetrieben — `dienst.py`

```bash
cd modules/<kennung> && uv run ptw . --now
```

Pro Regel:

1. Test schreiben und **scheitern sehen**
2. einfachste Änderung, die ihn grün macht
3. aufräumen — Tests bleiben unverändert

Ein Test, den du nie hast scheitern sehen, prüft möglicherweise nichts.

Fachliche Fehler als eigene Klassen:

```python
from homepi_core import ServiceError

class EintragUnbekannt(ServiceError):
    status = 404
    title = "Eintrag unbekannt"
```

Nie `HTTPException` — nur über `ServiceError` wird daraus `problem+json` mit
einem Text, den die Oberfläche anzeigen kann.

### 4.3 Persistenz — `modelle.py`, `speicher.py`

Tabellen erben von `homepi_core.Base`; das Gateway legt sie beim Start an.

Eindeutigkeit prüft die **Datenbank**, nicht dein Code: eine Vorabprüfung wäre
ein Rennen zwischen zwei Anfragen. `IntegrityError` abfangen und in deinen
Fehler übersetzen.

```bash
DATABASE_URL='postgresql+asyncpg://app:app@127.0.0.1:15432/test' uv run pytest -m ''
```

Die Datenbank heißt **`test`**, nicht `app`. Die Tests legen Tabellen an und
löschen sie wieder.

### 4.4 Endpunkte — `router.py`

Vier Regeln, alle schon einmal teuer gewesen:

1. `summary=` bei **jedem** Endpunkt. Ohne bleibt er in der generischen Ansicht
   namenlos. Ein Test im Gerüst prüft das.
2. Feste Pfade **vor** parametrisierten. Sonst liest FastAPI
   `/zusammenfassung` als UUID und antwortet `422`.
3. Rückgabetypen annotieren, sonst fehlt das OpenAPI-Schema.
4. Datenbank über `DbSitzung` aus `homepi_core.deps` — eine Transaktion je
   Anfrage, Commit am Ende, Rollback bei Fehler.

### 4.5 Oberfläche — `api.ts`, `<Kennung>Seite.tsx`

```bash
make tdd-web N=<kennung>
```

**Nur Tokens**, keine festen Werte. Jede Farbe und jeder Abstand kommt aus
`services/web/src/styles/tokens.css`. Bausteine aus `src/ui`: `Knopf`, `Karte`,
`Feld`, `Etikett`, `Hinweis`, `Leerzustand`, `Platzhalter`.

Vier Zustände, alle Pflicht:

| Zustand | Was zu tun ist |
|---|---|
| lädt | `Platzhalter` in der Größe des echten Inhalts — kein Layoutsprung |
| leer | `Leerzustand`, der sagt, was als Nächstes zu tun ist |
| Fehler | Meldung des Backends **wörtlich**, nie „Fehler 409" |
| gefüllt | der Normalfall |

Ein Fehler bei einer Aktion darf die Liste **nicht** gegen eine Fehlerseite
austauschen, und ein fehlgeschlagenes Formular behält seine Eingabe.

Tests greifen über **Rollen und sichtbaren Text** zu, nie über CSS-Klassen. Ein
Test an `getByRole("heading")` überlebt jedes Refactoring des Markups und
schlägt fehl, wenn die Überschrift für einen Screenreader verschwindet.

---

## 5. Fertig ist es, wenn das alles grün ist

```bash
make test-modul N=<kennung>
```

Das führt aus: `ruff format --check`, `ruff check`, `mypy`, `pytest` inklusive
Integration mit Coverage-Schwelle, dann `vitest` für die Oberfläche.

Danach das Zusammenspiel:

```bash
make dev && make smoke
```

| Kriterium | Schwelle |
|---|---|
| Coverage Backend | `fail_under` aus `pyproject.toml` (Standard 85 %) |
| Coverage Frontend | 85 % Zeilen, 80 % Zweige |
| `mypy --strict` | keine Fehler |
| `GET /module` | Artefakt mit `status: "bereit"` (angemeldet) |
| `GET /<kennung>/` ohne Cookie | 401 — nicht 200 |
| Rauchtests | grün |

`make smoke` braucht dafür ein Konto, sonst überspringen sich die Tests, die
das Manifest auswerten:

```bash
HOMEPI_SMOKE_BENUTZER=entwickler HOMEPI_SMOKE_PASSWORT=… make smoke
```

### Was kein Werkzeug prüft

- [ ] Kein `TODO`, kein `pass`, keine leere Funktion mehr im Artefakt
- [ ] Kein `@pytest.mark.skip`, kein `it.skip`, kein auskommentierter Test
- [ ] Jeder Endpunkt hat mindestens einen Test für den Fehlerfall, nicht nur
      für den Erfolg
- [ ] Die vier Zustände der Oberfläche sind belegt
- [ ] Bei 375 px Breite ist alles erreichbar, ohne horizontal zu scrollen
- [ ] Die Fehlermeldungen sind für einen Menschen verständlich, nicht für einen
      Entwickler
- [ ] Der `zugang` des Moduls ist bewusst gesetzt. `GESCHUETZT` ist die
      Voreinstellung und in fast allen Fällen richtig. `OEFFENTLICH` nur, wenn
      das Artefakt wirklich jeden etwas angeht — es ist dann auch für jeden
      sichtbar

### Selbst nachsehen, nicht nur behaupten

Bevor du „fertig" meldest:

```bash
curl -s http://127.0.0.1:18000/<kennung>/          # liefert echte Daten?
curl -s http://127.0.0.1:18000/openapi.json | grep <kennung>
```

Öffne `http://localhost:5173/modul/<kennung>` und führe den vollen Durchlauf
aus — anlegen, ändern, entfernen, dazu einen Fehlerfall. Eine Oberfläche, die
nur im Test funktioniert, ist nicht fertig.

---

## 6. Wenn etwas fehlt

| Symptom | Ursache |
|---|---|
| Kachel fehlt | Entry Point falsch, oder `uv sync` im Gateway vergessen |
| `status: "fehler"` | Import wirft. Grund steht in `beschreibung` und im Log |
| `422` statt Treffer | parametrisierte Route steht vor der festen |
| `RuntimeError: keine DATABASE_URL` | Unit-Test benutzt `DbSitzung` — gehört nach `tests/integration/` |
| Endpunkt fehlt in generischer Ansicht | `summary=` oder Rückgabetyp fehlt |
| Frontend zeigt generische Ansicht statt deiner Seite | `id` in `register.ts` stimmt nicht mit der Modulkennung überein |
| Tabelle fehlt nach Neustart | in Produktion ist `DB_SCHEMA_ANLEGEN=false`; dort braucht es eine Migration |

Logs:

```bash
make dev-logs
```

---

## 7. Abgeben

```bash
git checkout -b feature/<kennung>
git add -A && git commit
git push -u origin feature/<kennung>
```

Nie direkt auf `main` oder `develop`. Ausrollen auf den Pi erst nach grüner CI:

```bash
homepi deploy -s <kennung>
```

---

## 8. Grenzen deines Auftrags

**Ändere nicht ohne Rückfrage:** `packages/homepi-core/`, `services/gateway/`,
`services/web/src/styles/`, `services/web/src/ui/`, `services/web/src/huelle/`,
`.github/workflows/`, `stacks/`.

Brauchst du dort etwas, ist das ein eigenes Thema — melde es, statt es
nebenbei mitzuerledigen.

**Senke keine Schwelle**, um einen Lauf grün zu bekommen. Wenn eine Schwelle
nicht erreichbar ist, sag warum.

**Melde ehrlich**, was nicht läuft. Ein „fertig" über nicht ausgeführten Tests
kostet mehr Zeit, als es spart.

---

## Weiterführend

| Frage | Datei |
|---|---|
| Warum Modul und nicht Container? | [06-artefakte.md](06-artefakte.md) |
| Lokale Umgebung, Fallstricke unter Windows | [07-lokale-entwicklung.md](07-lokale-entwicklung.md) |
| Designsystem, Tokens, Zugänglichkeit | [08-design.md](08-design.md) |
| Dasselbe ausführlicher | [09-artefakt-bauen.md](09-artefakt-bauen.md) |
| Wer darf das Artefakt sehen? | [11-anmeldung.md](11-anmeldung.md) |
