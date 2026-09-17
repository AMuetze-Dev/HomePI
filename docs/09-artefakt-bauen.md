# 09 — Ein Artefakt bauen

Vom leeren Verzeichnis bis zur Kachel auf dem Pi. Warum ein Artefakt ein Modul
im Gateway ist und kein eigener Container, steht in
[06-artefakte.md](06-artefakte.md) — hier geht es nur ums Wie.

## Erzeugen

```bash
homepi new messwerte --titel "Messwerte" --beschreibung "Zahlen aus dem Haus"
```

| Option | Wirkung |
|---|---|
| `--modus service` | eigener Container statt Modul im Gateway |
| `--no-web` | ohne eigene Oberfläche — die generische Ansicht reicht zunächst |
| `--no-db` | ohne `modelle.py`, `speicher.py` und Integrationstests |
| `--titel` | Beschriftung der Kachel (Standard: aus dem Namen) |
| `--force` | vorhandene Dateien überschreiben |

Entsteht:

```
modules/messwerte/
  AGENTS.md                  der Auftrag - für Agenten die wichtigste Datei
  pyproject.toml             Entry Point homepi.module
  src/homepi_messwerte/
    __init__.py              modul = Modul(id=…, titel=…, router=…)
    schemas.py               Vertrag nach außen
    modelle.py               Tabellen (erben von homepi_core.Base)
    dienst.py                REINE Fachlogik
    speicher.py              DB-Zugriff
    router.py                HTTP
  tests/unit/                läuft immer, ohne DB
  tests/integration/         Marker `integration`

services/web/src/module/messwerte/
  api.ts  MesswerteSeite.tsx  MesswerteSeite.module.css  MesswerteSeite.test.tsx
```

Automatisch mit eingetragen:

- `services/gateway/pyproject.toml` → Abhängigkeit und `tool.uv.sources`
- `services/web/src/module/register.ts` → Import und Eintrag in `OBERFLAECHEN`

Der Gateway-Eintrag ist der Punkt, an dem es am häufigsten klemmt: ohne ihn
lädt niemand den Entry Point, und die Kachel fehlt kommentarlos.

## In Betrieb nehmen

```bash
cd services/gateway && uv sync    # Modul in die Umgebung holen
make dev
```

`http://localhost:5173` zeigt die Kachel, `http://localhost:18000/module`
listet das Artefakt mit `status: "bereit"`.

## Bauen

### Vertrag zuerst

`schemas.py`. Pydantic-Validierung wird automatisch zu `422` mit Feldnamen —
das Frontend kann sie unverändert anzeigen.

### Fachlogik testgetrieben

```bash
cd modules/messwerte && uv run ptw . --now
```

Rot, grün, aufräumen. Alles, was entscheidet, gehört in `dienst.py` und bleibt
rein. Sobald ein Test dort eine Datenbank braucht, ist die Logik an der
falschen Stelle.

### Persistenz

Tabellen in `modelle.py`, Zugriff in `speicher.py`. Integrationstests:

```bash
DATABASE_URL='postgresql+asyncpg://app:app@127.0.0.1:15432/test' uv run pytest -m ''
```

Die Datenbank heißt `test`, nicht `app`: die Tests legen Tabellen an und
löschen sie wieder.

### Endpunkte

`router.py`. Vier Regeln, alle schon einmal teuer gewesen:

1. `summary=` bei jedem Endpunkt — sonst bleibt er in der generischen Ansicht
   namenlos. Ein Test in der Vorlage prüft das.
2. Feste Pfade **vor** parametrisierten. Sonst liest FastAPI
   `/zusammenfassung` als UUID und antwortet `422`.
3. Fehler über eigene `ServiceError`-Klassen, nie `HTTPException` — nur so
   wird daraus `problem+json` mit brauchbarem Text.
4. Rückgabetypen annotieren, sonst fehlt das OpenAPI-Schema.

### Oberfläche

`api.ts` erweitern, dann die Seite. Bausteine aus `src/ui`, Werte aus
`src/styles/tokens.css`. Details: [08-design.md](08-design.md).

Braucht das Artefakt keine eigene Oberfläche, `--no-web` benutzen — die
generische Ansicht liest die Endpunkte aus dem Schema und ist damit immer
aktuell.

## An einem einzelnen Artefakt arbeiten

Mit wachsender Zahl an Artefakten will man nicht mehr alles laufen lassen.
Drei Ebenen lassen sich einzeln ansprechen:

```bash
make modul N=messwerte        # wo liegen die beiden Hälften?
make dev N=messwerte          # Gateway lädt NUR dieses Artefakt
make tdd-api P=modules/messwerte
make tdd-web N=messwerte      # vitest nur für dessen Oberfläche
make test-modul N=messwerte   # beide Hälften vollständig prüfen
```

`make dev N=…` setzt `HOMEPI_MODULE`. Die Auswahl greift **vor** dem Import:
ein übersprungenes Artefakt wird nicht geladen, sonst spart sie keine
Startzeit — und genau dafür ist sie da.

Zwei Nebenwirkungen, die im Alltag nützlich sind:

- Ein Artefakt, das gerade kaputt ist, steht beim Arbeiten am nächsten nicht
  im Weg. Es erscheint dann auch nicht als `status: "fehler"` — es ist
  schlicht nicht dabei.
- Die Startseite zeigt nur die ausgewählte Kachel. Das ist beim Entwickeln
  gewollt und in Produktion falsch, deshalb bleibt die Variable dort leer.

Das Gateway schreibt beim Start eine Warnung ins Log, solange die Auswahl
aktiv ist — sonst sucht man irgendwann, warum eine Kachel fehlt.

## Abnahme

```bash
cd modules/messwerte
uv run ruff format --check . && uv run ruff check . && uv run mypy
DATABASE_URL='postgresql+asyncpg://app:app@127.0.0.1:15432/test' uv run pytest -m ''

cd services/web
npx prettier --check src && npx eslint . && npm run typecheck && npm run test:coverage

make dev && make smoke
```

Die Coverage-Schwelle steht in der `pyproject.toml` des Artefakts
(`[tool.coverage.report] fail_under`), nicht in der CI — so gilt sie auch
lokal und muss beim Anlegen nirgends nachgetragen werden.

**Die CI findet neue Module von selbst.** Ihre Matrix wird aus
`packages/*`, `modules/*` und `services/gateway` erzeugt, nicht aufgezählt.
Ein Artefakt, an dessen Eintrag in `ci.yml` niemand gedacht hat, wäre sonst
ungeprüft.

## Ausrollen

```bash
git push
homepi deploy -s messwerte
```

Baut das arm64-Image über die Pipeline, der Pi zieht es. Danach steht die
Kachel dort.

## Wenn etwas fehlt

| Symptom | Ursache |
|---|---|
| Kachel fehlt | Entry Point falsch, oder Modul nicht als Abhängigkeit im Gateway — `uv sync` im Gateway vergessen? |
| `status: "fehler"` im Manifest | Import wirft. Grund steht in der Kachel und im Log |
| `422` statt Treffer | parametrisierte Route steht vor der festen |
| `RuntimeError: keine DATABASE_URL` | Unit-Test benutzt `DbSitzung` — das gehört nach `tests/integration/` |
| Endpunkt fehlt in generischer Ansicht | `summary=` oder Rückgabetyp fehlt |
| Tabelle fehlt nach Neustart | in Produktion ist `DB_SCHEMA_ANLEGEN=false`; dort braucht es eine Migration |
